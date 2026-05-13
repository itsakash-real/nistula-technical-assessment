"""
Query classifier service.

Classifies incoming guest messages into one of six intent types
using keyword matching. Rule-based classification was chosen
deliberately over ML for three reasons:

1. Explainability — every decision can be traced to a keyword rule.
2. Reliability — no model drift, no training data required.
3. Auditability — a non-technical ops team can read and update the rules.

Known limitation: brittle for multilingual guests. A Hindi message
asking "क्या villa available है?" would fall through to general_enquiry.
In production, a language detection step would run before classification.
This is documented in thinking.md as a known tradeoff.

Priority order matters: complaint is checked first because it must
always escalate regardless of other intent signals in the message.
"""


# Ordered by priority — first match wins.
# Complaint is first because it must always take precedence,
# even if the guest also asks a legitimate question in the same message.
CLASSIFICATION_RULES = [
    (
        "complaint",
        ["unhappy", "unacceptable", "refund", "complaint", "not working",
         "broken", "disgusting", "terrible", "awful", "worst", "angry",
         "disappointed", "no hot water", "no water", "no ac", "no wifi",
         "not acceptable", "want a refund", "demand", "3am", "emergency"]
    ),
    (
        "pre_sales_availability",
        ["available", "availability", "vacancy", "free", "dates",
         "april", "may", "june", "july", "august", "book", "booking",
         "when can", "is it open"]
    ),
    (
        "pre_sales_pricing",
        ["price", "rate", "cost", "how much", "per night", "charge",
         "fee", "pricing", "quote", "total", "adults", "persons", "people"]
    ),
    (
        "post_sales_checkin",
        ["check in", "check-in", "checkin", "check out", "checkout",
         "wifi", "wi-fi", "password", "what time", "arrival", "key",
         "access", "entry", "directions", "address", "caretaker"]
    ),
    (
        "special_request",
        ["early", "late", "transfer", "airport", "pickup", "drop",
         "arrange", "request", "special", "chef", "cook", "meal",
         "birthday", "anniversary", "decoration", "surprise"]
    ),
    (
        "general_enquiry",
        ["pets", "dog", "cat", "parking", "car", "pool", "gym",
         "beach", "nearby", "restaurant", "market", "policy", "rules"]
    ),
]


def classify_query(message_text: str) -> str:
    """
    Returns the query type for a given message.

    Iterates rules in priority order. First keyword match wins.
    Falls back to general_enquiry if nothing matches — safer
    than returning an error for an unrecognised message.
    """
    message_lower = message_text.lower()

    for query_type, keywords in CLASSIFICATION_RULES:
        if any(keyword in message_lower for keyword in keywords):
            return query_type

    # Safe fallback — unrecognised messages go to agent review
    # via the confidence score rather than crashing the pipeline.
    return "general_enquiry"