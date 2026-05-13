"""
Claude AI service.

Responsible for three things only:
1. Building a structured, context-rich prompt
2. Calling the Claude API
3. Returning the drafted reply — or failing gracefully

Prompt design decisions:
- Property context is injected as structured text, not JSON.
  Structured prose performs more reliably in Claude prompts.
- Query type is explicitly named so Claude calibrates tone.
  A complaint needs empathy. A pricing query needs precision.
- Tone instructions are explicit, not assumed. "Warm but concise"
  is more reliable than hoping the model infers it.
- System prompt and user prompt are separated deliberately —
  system sets behaviour, user provides the specific message.
"""

import anthropic
from app.models.unified_models import UnifiedMessage
from app.utils.helpers import get_property_context, format_property_for_prompt
from app.config.settings import ANTHROPIC_API_KEY, CLAUDE_MODEL


# Initialised once at module level — not per request.
# Creating a new client on every call is wasteful and slower.
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


SYSTEM_PROMPT = """
You are a warm, professional hospitality assistant for Nistula Villas.

Your role is to draft replies to guest messages. Every reply must:
- Address the guest by their first name
- Be warm but concise — no more than 4-5 sentences unless the question demands more
- Be factually accurate using only the property details provided
- Never invent information that isn't in the property context
- Match tone to the query type:
    * Availability / pricing: friendly and informative
    * Check-in / logistics: clear and reassuring
    * Special requests: warm and accommodating
    * Complaints: empathetic first, solution-focused second — never defensive
    * General enquiry: helpful and inviting

If you do not have enough information to answer a specific question,
say so honestly and offer to connect the guest with the team directly.
Never guess or fabricate details.
""".strip()


def build_user_prompt(message: UnifiedMessage, property_context: str) -> str:
    """
    Constructs the user-facing prompt passed to Claude.

    Separating prompt construction from the API call makes
    this independently testable and easier to iterate on.
    """
    # Extract first name for natural address in the reply
    first_name = message.guest_name.split()[0]

    return f"""
Guest Name: {first_name}
Channel: {message.source}
Query Type: {message.query_type}
Booking Reference: {message.booking_ref or 'Not provided — likely a pre-sales enquiry'}

Property Details:
{property_context}

Guest Message:
{message.message_text}

Draft a reply to this guest message. Follow the tone guidelines
for the query type above. Address the guest as {first_name}.
""".strip()


async def generate_reply(message: UnifiedMessage) -> str:
    """
    Calls the Claude API and returns a drafted guest reply.

    Error handling strategy:
    - API failures return a safe fallback string, not a crash.
    - The pipeline continues — confidence scoring will produce
      a low score and the action router will escalate.
    - This means the system degrades gracefully under AI failure
      rather than taking down the entire webhook.
    """
    try:
        property_context_dict = get_property_context(message.property_id)
        property_context_str = format_property_for_prompt(property_context_dict)
        user_prompt = build_user_prompt(message, property_context_str)

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        return response.content[0].text

    except anthropic.AuthenticationError:
        # API key is invalid or expired — surface clearly for ops team
        return _fallback_reply(message, reason="authentication")

    except anthropic.RateLimitError:
        # Too many requests — system should retry with backoff in production
        return _fallback_reply(message, reason="rate_limit")

    except anthropic.APIConnectionError:
        # Network failure — not a code error, log and degrade gracefully
        return _fallback_reply(message, reason="connection")

    except Exception:
        # Unexpected failure — do not expose internal errors to response
        return _fallback_reply(message, reason="unknown")


def _fallback_reply(message: UnifiedMessage, reason: str) -> str:
    """
    Returns a safe, human-readable fallback when the AI call fails.

    The guest still receives a response. The action router will
    escalate this for human handling because confidence will be low.
    Logging the reason here would feed the ops alerting system
    in a production environment.
    """
    first_name = message.guest_name.split()[0]

    return (
        f"Hi {first_name}, thank you for reaching out. "
        f"Our team has received your message and will get back to you shortly. "
        f"We appreciate your patience."
    )