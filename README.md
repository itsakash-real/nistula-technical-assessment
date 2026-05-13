# Nistula Guest Message Handler

A backend webhook system that receives guest messages from multiple channels, 
classifies intent, generates AI-drafted replies using Claude, scores confidence, 
and routes to auto-send, agent review, or escalation.

Built as part of the Nistula 48-hour technical assessment.

---

## Architecture Overview

Every inbound message travels through a fixed pipeline. Each step has one 
responsibility and hands off to the next:

```
POST /webhook/message
        ↓
Request Validation          Pydantic — rejects malformed payloads with 422
        ↓
Query Classification        Rule-based keyword matching → intent type
        ↓
Message Normalisation       Raw payload → unified internal schema + UUID
        ↓
Context Assembly            Property details injected from helpers.py
        ↓
AI Prompt Generation        Structured prompt built per query type
        ↓
Claude API Call             Wrapped in typed error handling + graceful fallback
        ↓
Confidence Scoring          Rule-based score 0.0–1.0 with documented logic
        ↓
Action Decision             auto_send / agent_review / escalate
        ↓
JSON Response               Typed, documented, Swagger-visible
```

The route file is intentionally thin — it only accepts, delegates, and 
returns. No business logic lives in the route layer.

---

## Folder Structure

```
nistula-technical-assessment/
│
├── app/
│   ├── main.py                    # FastAPI app, error handlers, router registration
│   │
│   ├── routes/
│   │   └── webhook.py             # Intake only — zero business logic
│   │
│   ├── services/
│   │   ├── normalizer.py          # payload → unified schema
│   │   ├── classifier.py          # message text → query_type
│   │   ├── claude_service.py      # prompt build + API call + fallback
│   │   ├── confidence.py          # explainable confidence scoring
│   │   └── action_router.py       # score + type → action decision
│   │
│   ├── models/
│   │   ├── request_models.py      # incoming webhook shape (Pydantic)
│   │   ├── unified_models.py      # internal contract between services
│   │   └── response_models.py     # outbound response shape
│   │
│   ├── config/
│   │   └── settings.py            # env vars loaded once, here only
│   │
│   └── utils/
│       ├── helpers.py             # property context + UUID generation
│       └── error_handlers.py      # global 422 and 500 handlers
│
├── tests/
│   ├── sample_payloads.json       # 9 test cases — 5 happy path, 4 error
│   └── run_tests.py               # test runner — no framework required
│
├── schema.sql                     # PostgreSQL schema — Part 2
├── thinking.md                    # Reasoning questions — Part 3
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Setup Instructions

**1. Clone the repository**
```bash
git clone https://github.com/YOUR_USERNAME/nistula-technical-assessment.git
cd nistula-technical-assessment
```

**2. Create and activate virtual environment**
```bash
python -m venv venv
source venv/bin/activate       # Mac/Linux
venv\Scripts\activate          # Windows
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Configure environment variables**
```bash
cp .env.example .env
```
Open `.env` and add your Anthropic API key:
```
ANTHROPIC_API_KEY=your_key_here
CLAUDE_MODEL=claude-sonnet-4-20250514
```

**5. Start the server**
```bash
uvicorn app.main:app --reload
```

**6. Verify it works**
```
http://localhost:8000/health     → {"status": "ok"}
http://localhost:8000/docs       → Swagger UI — interactive demo
http://localhost:8000/redoc      → ReDoc — clean documentation
```

---

## API Endpoint

### POST /webhook/message

Accepts a guest message from any supported channel and returns a 
classified, AI-drafted, confidence-scored response.

**Request:**
```json
{
  "source": "whatsapp",
  "guest_name": "Rahul Sharma",
  "message": "Is the villa available from April 20 to 24? What is the rate for 2 adults?",
  "timestamp": "2026-05-05T10:30:00Z",
  "booking_ref": "NIS-2024-0891",
  "property_id": "villa-b1"
}
```

Supported sources: `whatsapp`, `booking_com`, `airbnb`, `instagram`, `direct`

**Response:**
```json
{
  "message_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "query_type": "pre_sales_availability",
  "drafted_reply": "Hi Rahul! Great news — Villa B1 is available from April 20 to 24...",
  "confidence_score": 0.82,
  "action": "agent_review"
}
```

**Error response (422):**
```json
{
  "error": "Request validation failed",
  "details": [
    {
      "field": "body → source",
      "issue": "Input should be 'whatsapp', 'booking_com', 'airbnb', 'instagram' or 'direct'",
      "received": "telegram"
    }
  ],
  "hint": "Check field types, required fields, and enum values against the schema at /docs"
}
```

---

## Query Classification Logic

Classification is rule-based, not ML. Every decision is traceable to a 
keyword rule. Rules are evaluated in priority order — first match wins.

| Priority | Query Type | Trigger Keywords |
|----------|------------|-----------------|
| 1 (highest) | `complaint` | unhappy, unacceptable, refund, broken, no hot water, not working |
| 2 | `pre_sales_availability` | available, vacancy, dates, book, april, may |
| 3 | `pre_sales_pricing` | price, rate, cost, how much, per night, adults |
| 4 | `post_sales_checkin` | wifi, check-in, password, what time, arrival, key |
| 5 | `special_request` | early, transfer, airport, chef, birthday, arrange |
| 6 (fallback) | `general_enquiry` | pets, parking, pool, nearby, policy |

**Why rule-based over ML:**
Explainability matters more than marginal accuracy at this scale. A 
non-technical ops manager can read these rules, understand every 
classification decision, and update them without a model retraining cycle. 
ML would add maintenance overhead with no meaningful accuracy improvement 
for six known, well-defined intent categories.

**Known limitation:**
Multilingual messages fall through to `general_enquiry`. A Hindi message 
asking "क्या villa available है?" would not match English keywords. Language 
detection before classification is the first production improvement.

---

## Confidence Scoring Logic

Confidence measures how safe it is to send a reply without human review — 
not how good the reply is.

**Base scores by query type:**

| Query Type | Base Score | Rationale |
|------------|------------|-----------|
| `post_sales_checkin` | 0.95 | Exact facts available: WiFi password, check-in time |
| `pre_sales_availability` | 0.90 | Known from property context |
| `pre_sales_pricing` | 0.88 | Known rates, minor ambiguity on guest count |
| `special_request` | 0.75 | Requires ops confirmation — not fully automatable |
| `general_enquiry` | 0.72 | Catch-all category, variable precision |
| `complaint` | 0.40 | Always needs human eyes — hard floor, not a calculation |

**Modifiers:**

| Condition | Adjustment |
|-----------|------------|
| Multiple intents detected (e.g. availability + pricing) | −0.08 |
| Ambiguous phrasing (maybe, not sure, possibly) | −0.10 |

**Action mapping:**

| Score | Action |
|-------|--------|
| Complaint (any score) | `escalate` — bypasses scoring entirely |
| ≥ 0.85 | `auto_send` |
| 0.60 – 0.85 | `agent_review` |
| < 0.60 | `escalate` |

**Why complaints bypass scoring:**
A well-written complaint would naturally score high on confidence. But 
auto-sending a reply to a dissatisfied guest is never safe regardless of 
how clear the message is. Complaints are a hard business rule: always 
escalate, always review, always have a human own the resolution.

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Invalid source channel | 422 with field-level detail |
| Empty message or guest name | 422 with field-level detail |
| Missing required field | 422 with field-level detail |
| Bad timestamp format | 422 with field-level detail |
| Claude API authentication failure | Safe fallback reply — pipeline continues |
| Claude API rate limit | Safe fallback reply — pipeline continues |
| Claude API connection failure | Safe fallback reply — pipeline continues |
| Unexpected server error | 500 with safe message — internals never exposed |

**Fallback reply strategy:**
When the Claude API fails for any reason, the guest receives a holding 
reply ("Our team has received your message and will be in touch shortly"). 
The pipeline continues — confidence scores low, action routes to escalate, 
a human picks it up. The system never goes silent to a guest because the 
AI is unavailable.

---

## Running the Tests

Start the server first:
```bash
uvicorn app.main:app --reload
```

In a separate terminal:
```bash
python tests/run_tests.py
```

This runs all 9 test cases — 5 happy path scenarios and 4 deliberate error 
cases — and prints structured results with query type, confidence score, 
action, and reply preview for each.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key — never hardcoded |
| `CLAUDE_MODEL` | No | Defaults to `claude-sonnet-4-20250514` |

All environment variables are loaded once in `app/config/settings.py`. 
No other file reads from `.env` or imports `os` directly.

---

## Assumptions

**1. One property for this assessment.**
Property context is hardcoded in `utils/helpers.py`. The structure is 
intentionally a dict keyed by `property_id` — adding a second property 
requires one dict entry, not a code change. In production this would be 
a database lookup.

**2. booking_ref may be absent.**
Pre-sales inquiries often carry no booking reference. The field is 
`Optional[str]` in the request model. The classifier and AI service 
handle this gracefully — the prompt notes "likely a pre-sales enquiry" 
when no booking_ref is present.

**3. Synchronous Claude API call.**
The current implementation calls the Claude API synchronously within the 
request lifecycle. For high-volume production use, this would move to an 
async task queue (Celery + Redis) so the webhook returns immediately and 
AI processing happens in the background.

**4. No authentication on the webhook.**
The endpoint is open for this assessment. Production would require HMAC 
signature verification per channel (WhatsApp, Airbnb each provide their 
own signing mechanism).

---

## Future Improvements

These are not a wishlist — each one addresses a specific production gap:

**Conversation memory**
Each call is currently stateless. If a guest sends three related messages, 
each is classified independently. Including recent conversation history 
from the database in the Claude prompt would dramatically improve reply 
quality for multi-turn conversations. This is the highest-impact missing 
feature.

**Language detection before classification**
The keyword classifier breaks on non-English messages. A lightweight 
language detection step (langdetect) before classification, with 
translated keyword lists per language, would make the system work for 
the full range of guests at a North Goa property.

**Async processing with task queue**
Moving the Claude API call to a background worker (Celery + Redis) would 
allow the webhook to return a `202 Accepted` immediately and process 
asynchronously. Required above ~50 requests per minute.

**Dynamic confidence based on context completeness**
Currently confidence is static per query type. It should also reflect 
whether the property context actually contains an answer. A WiFi query 
when no WiFi password is stored should score lower than 0.95.

**HMAC signature verification**
Each channel (WhatsApp Business API, Airbnb, Booking.com) provides a 
signing secret for webhook verification. Production requires validating 
this signature before processing any payload.

**Sentiment analysis as a confidence modifier**
Running lightweight sentiment analysis on the message text would allow 
the confidence model to detect frustrated-but-not-complaining messages 
that deserve agent review even if they don't trigger complaint keywords.

**Rate limiting**
Per-property and per-source rate limits would prevent a misconfigured 
channel from flooding the system. FastAPI supports this via 
`slowapi` middleware.

---

## What I Would Challenge About This Design

The keyword classifier will produce false positives on complaint keywords 
used in non-complaint contexts. The static confidence scores do not account 
for whether the property context actually answers the question. The system 
has no conversation memory — each message is classified in isolation. And 
the on-call escalation path assumes a human exists to receive the 3am 
alert; the platform cannot fix an ops process that has not been defined. 
These are documented in detail in `thinking.md`.

---

## Database Schema

See `schema.sql` for the full PostgreSQL schema with inline design decision 
comments. Covers: unified guest identity across channels, conversation 
threading, full AI audit trail, and SLA-tracked escalations.

## Part 3 Thinking Questions

See `thinking.md` for the 3am scenario response, system design walkthrough, 
and pattern detection approach.