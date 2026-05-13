"""
Confidence scoring service.

Produces a score between 0.0 and 1.0 representing how reliably
the system can handle this message without human intervention.

Design philosophy:
Confidence is not a measure of how good the AI reply is.
It is a measure of how safe it is to send that reply without
a human reviewing it first.

Scoring is deliberately rule-based, not ML-derived. This means:
- Every score can be explained to a non-technical team member
- Rules can be updated by ops without touching model training
- Audit trail is human-readable

Score bands and their business meaning:
  0.90 - 0.95 : Deterministic answer — exact property fact available
  0.85 - 0.90 : High confidence — clear single intent, known answer
  0.70 - 0.85 : Medium confidence — answerable but some ambiguity
  0.55 - 0.70 : Low confidence — unclear intent or multiple intents
  0.40        : Complaint — always needs human eyes regardless of content

Multi-intent penalty:
A message asking both availability and pricing is harder to answer
well than either alone. Confidence is reduced to reflect this.
"""

from app.models.unified_models import UnifiedMessage


# Base scores by query type.
# These represent ideal single-intent messages of each type.
BASE_SCORES = {
    "post_sales_checkin": 0.95,      # Exact facts: wifi password, check-in time
    "pre_sales_availability":  0.90, # Known from mock context: available April 20-24
    "pre_sales_pricing": 0.88,       # Known rates, but depends on guest count
    "special_request": 0.75,         # Requires ops confirmation — not auto-sendable
    "general_enquiry": 0.72,         # Answerable but catch-all category
    "complaint": 0.40,               # Always escalated — human review mandatory
}

# Keywords that signal multiple intents in one message.
# Each additional intent reduces confidence.
MULTI_INTENT_SIGNALS = [
    ["available", "rate"],
    ["available", "price"],
    ["check in", "wifi"],
    ["early", "transfer"],
    ["price", "availability"],
    ["book", "cost"],
]

# Keywords that signal genuine ambiguity.
AMBIGUITY_SIGNALS = [
    "maybe", "not sure", "thinking about", "possibly",
    "might", "could you", "wondering", "just checking"
]


def calculate_confidence(message: UnifiedMessage) -> float:
    """
    Returns a confidence score for the unified message.

    Applies base score for query type, then adjusts downward
    for multi-intent signals and ambiguity markers.
    """
    # Complaints always score 0.40 — business rule, not a calculation.
    # No modifier should ever push a complaint above agent_review threshold.
    if message.query_type == "complaint":
        return 0.40

    score = BASE_SCORES.get(message.query_type, 0.70)
    message_lower = message.message_text.lower()

    # Penalise multi-intent messages.
    # Each combination detected reduces confidence by 0.08.
    for signal_pair in MULTI_INTENT_SIGNALS:
        if all(term in message_lower for term in signal_pair):
            score -= 0.08
            # Only apply one multi-intent penalty — avoid over-penalising
            break

    # Penalise ambiguous phrasing.
    # Guest is uncertain, so we should be too.
    for signal in AMBIGUITY_SIGNALS:
        if signal in message_lower:
            score -= 0.10
            break

    # Clamp to valid range — modifiers should never produce
    # a score below 0.10 or above 1.0
    return round(max(0.10, min(1.0, score)), 2)