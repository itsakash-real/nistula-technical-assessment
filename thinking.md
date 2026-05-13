# Thinking Questions — Nistula Technical Assessment

---

## Question A — The Immediate Response

**The actual message sent at 3am:**

> Hi Arjun, I'm really sorry — this is not the experience we want you to have, 
> especially with guests arriving in the morning. I've escalated this to our 
> property team right now and someone will be in touch within the next 
> 30 minutes with a resolution. We will make this right.

**Why this wording:**

Three things are happening simultaneously in that message: the guest is 
stressed, it's 3am, and they've already framed it as a refund demand. A 
defensive or procedural reply at that moment makes everything worse.

The message does three specific things deliberately:

First, it acknowledges the problem without hedging. "This is not the experience 
we want you to have" validates the complaint without admitting liability or 
triggering a legal exposure. "I'm really sorry" is human — not "we apologise 
for the inconvenience."

Second, it gives a concrete commitment with a number attached. "Within the next 
30 minutes" is a promise the system can monitor. Vague reassurances ("someone 
will be in touch soon") erode trust at 3am when the guest is already angry.

Third, it does not mention the refund. Not to avoid it — but because engaging 
with the refund in the first message, before the problem is even resolved, 
signals that the platform is more focused on the money than the guest. The 
refund conversation belongs to a human in daylight.

The complaint was classified as escalate immediately. The AI drafted the 
empathy layer. A human owns the resolution.

---

## Question B — The System Design

**What happens the moment this message arrives:**

**T+0 seconds — Message received**
The webhook receives the payload. The classifier detects complaint keywords 
("no hot water", "unacceptable", "refund"). Confidence score is set to 0.40 
regardless of content — complaints always floor at 0.40 by business rule. 
Action router returns `escalate` before the AI reply is even generated.

**T+0 to T+3 seconds — AI draft + escalation record created**
Claude generates the empathy-first reply drafted above. An escalation record 
is written to the `escalations` table with:
- `severity`: critical (3am + complaint + refund demand)
- `sla_deadline`: NOW() + 30 minutes
- `reason`: complaint
- `status`: open

**T+3 seconds — Notifications fire simultaneously**
The platform triggers three parallel notifications:

1. WhatsApp/SMS to the on-call property manager — not email, not a push 
   notification, not a dashboard alert. 3am means the channel must be loud 
   enough to wake someone up. The message includes the guest name, property, 
   and the exact complaint text.

2. Internal ops dashboard flags the escalation as critical — visible to 
   anyone monitoring overnight.

3. The AI-drafted reply is sent to the guest immediately — not held. The guest 
   gets an acknowledgement within seconds of sending their message, even at 3am. 
   This buys time for the human response without leaving the guest in silence.

**T+30 minutes — SLA check**
A scheduled job (cron or background worker) queries the `overdue_escalations` 
view. If `first_response_at` is still NULL and `sla_deadline` has passed:

- `sla_breached` is set to TRUE on the escalation record
- A second escalation fires to a senior manager — one level up from the 
  original on-call contact
- The ops dashboard escalation card turns red
- An internal log entry records the breach for morning ops review

**T+60 minutes — No response still**
If the escalation remains unresolved:
- The property owner is notified directly
- The guest receives a second message: "Our property manager is on their way 
  to the villa. We have not forgotten about you."
- The escalation severity is upgraded to `critical` if not already

**What gets logged throughout:**
Every state transition is timestamped in the escalations table. The morning 
ops review sees: when the complaint arrived, when the AI replied, when the 
human was notified, whether SLA was met, and what the resolution was. This 
creates accountability without needing anyone to write a report.

**The current system's gap:**
The caretaker is available 8am to 10pm. There is no documented on-call path 
for the 10pm to 8am window. The system as designed assumes an on-call human 
exists. In reality, Nistula needs to define: who is the on-call contact at 3am, 
what is their escalation path, and what compensation authority do they have. 
The platform can enforce an SLA but cannot invent an on-call rota that does 
not exist operationally. This is the real gap — and a platform cannot fix an 
ops process problem with code.

---

## Question C — The Learning

**What the system should do with the pattern:**

This is the third hot water complaint at Villa B1 in two months. The system 
already has the data — the `complaint_trends` view surfaces exactly this. The 
question is what happens with that data.

**What most systems do:** surface it on a dashboard and wait for someone to 
notice. This is not enough.

**The insight:** by the time a guest reports a problem, the system has already 
failed. The guest has become the sensor. Every complaint is evidence that a 
preventive check did not happen.

**What should actually be built:**

**Layer 1 — Automated pattern detection**
A background job queries `complaint_trends` weekly. When the same complaint 
category appears three or more times at the same property within 60 days, it 
triggers a maintenance alert — not a dashboard card, a direct notification to 
the property manager with the specific pattern: "Hot water complaints at Villa 
B1: 3 incidents in 47 days. Preventive inspection recommended."

**Layer 2 — Pre-arrival checklist**
24 hours before every check-in, the platform sends an automated checklist to 
the caretaker. After the third hot water complaint, "hot water system — test 
and confirm working" is added permanently to the Villa B1 checklist. The 
caretaker confirms via a simple reply or tap. If no confirmation is received 
6 hours before check-in, the property manager is alerted.

This is the real fix. The guest should never be the first person to discover 
the hot water is broken. The caretaker should be.

**Layer 3 — Maintenance ticket integration**
On the third complaint, the system automatically creates a maintenance ticket: 
"Recurring hot water failure — inspect boiler, pipes, and water heating system 
at Villa B1." This goes to whatever maintenance tracking system Nistula uses. 
The ticket is linked to all three complaint messages for context.

**Layer 4 — Guest follow-up**
The two guests who complained previously receive a proactive message before 
their next stay (if they rebook): "We've completed a full maintenance check 
at Villa B1 since your last visit. We look forward to welcoming you back." 
This turns a complaint into a trust signal.

**What I would build first:**
The pre-arrival checklist. It is the highest leverage intervention — it 
prevents the complaint from reaching the guest at all. Analytics dashboards 
tell you what went wrong. Checklists stop it from going wrong.

The pattern detection and maintenance ticketing are the second sprint. The 
guest follow-up is the third.

---

## Design Decisions I Made and Why

**1. Rule-based classifier over ML**

Keyword matching was chosen deliberately over a trained classifier. Three 
reasons:

- Explainability — every classification decision can be traced to a specific 
  keyword. A non-technical ops manager can read the rules and understand why 
  a message was classified as a complaint.
- No training data required — a production ML classifier needs labelled 
  historical data that does not exist for a new platform.
- Updateable by ops — when a new complaint pattern emerges ("not clean" was 
  not in the original rules), ops can add the keyword without a model retraining 
  cycle.

Known limitation: brittle for multilingual guests. A Hindi message asking 
"क्या villa available है?" would fall through to `general_enquiry`. In a real 
North Goa deployment, language detection (langdetect or similar) would run 
before classification, and keyword lists would be maintained per language. 
I am documenting this as a known tradeoff rather than ignoring it.

**2. booking_ref as the guest identity anchor**

The hardest schema decision was how to unify a guest who contacts via 
WhatsApp and later books via Airbnb.

- Email as the anchor fails — WhatsApp carries no email
- Phone as the anchor fails — international formatting creates false duplicates
- Channel ID as the anchor fails — siloes guests by platform

booking_ref is deterministic and verified by the reservation system. It is 
channel-independent. The tradeoff is honest: pre-booking inquiries from 
unknown guests create provisional records flagged `identity_verified = false`. 
A human must merge these when the guest later makes a booking. I chose to be 
explicit about this limitation rather than silently guess and get it wrong.

**3. Complaints bypass confidence scoring**

The complaint → escalate path is a hard business rule, not a soft threshold. 
A complaint with clear, confident language would score 0.90 on the confidence 
model — but it should never be auto-sent. The decision to always escalate 
complaints regardless of score was made because: the emotional and financial 
stakes of a wrong automated reply to a dissatisfied guest outweigh any 
efficiency gain from automation.

**4. AI fallback degrades gracefully, not loudly**

When the Claude API fails, the system returns a safe holding reply rather 
than a 500 error. The pipeline continues — confidence scores low, action 
routes to escalate, a human picks it up. The guest receives a message within 
seconds regardless of AI availability. This was a deliberate choice: an 
AI-powered platform that goes silent when the AI is unavailable is less 
reliable than a phone.

---

## What I Would Challenge About This Design

**The keyword classifier will break on edge cases.** A message like "I hope 
the villa is available — we had such a terrible experience last time at 
another property" would be classified as a complaint due to "terrible 
experience." In production, I would add a negation and context check — does 
the complaint language refer to this property specifically? This is a one-week 
improvement, not a full ML pipeline.

**The confidence scores are static per query type.** Right now a WiFi 
password query always starts at 0.95. In production, confidence should also 
account for whether the property context actually contains an answer. If the 
property record has no WiFi password stored, the score should drop 
automatically — the AI is going to guess or apologise, which is lower 
confidence than a deterministic answer.

**There is no conversation memory.** Each webhook call is stateless. If a 
guest sends three messages in a row — "Is the villa available?", "What about 
April 25?", "And the rate?" — each is classified independently with no 
awareness of the thread. In production, the Claude API call would include 
recent conversation history from the `messages` table, scoped to the current 
conversation_id. This changes the prompt structure significantly and is the 
most impactful missing feature in the current design.

**The on-call escalation path assumes humans exist.** The SLA monitoring 
works. The 30-minute alert fires. But the platform cannot manufacture an 
on-call rota. Nistula needs to define operationally who receives the 3am 
alert and what authority they have. The best escalation system in the world 
fails if the phone rings and nobody answers.

---

## What I Would Build in Sprint 2

- Conversation memory: include last 3 messages from the same 
  conversation_id in the Claude prompt. Right now each message 
  is classified in isolation — a guest asking a follow-up question 
  gets no context from their previous message.

- Pre-arrival checklist trigger: 24 hours before check-in, 
  automatically message the caretaker a checklist based on 
  known complaint patterns for that property. Hot water at 
  Villa B1 would be on that list by now.

- HMAC webhook verification: WhatsApp Business API and Airbnb 
  both provide signing secrets. Without verifying the signature, 
  any actor can POST to the webhook endpoint. One middleware 
  function fixes this.