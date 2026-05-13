"""
Action router service.

Maps a confidence score and query type to one of three actions:
  auto_send    — reply is sent to guest immediately without review
  agent_review — reply is drafted and queued for agent approval
  escalate     — message is flagged for urgent human handling

Routing rules are explicit business decisions, not magic numbers.
Each threshold exists for a reason documented below.

Threshold rationale:
  0.85+ → auto_send
    High enough confidence that sending without review is safe.
    Incorrect auto-sends at this level are rare and low-stakes.

  0.60–0.85 → agent_review
    System has a reasonable answer but human confirmation
    adds value. Agent sees the draft and approves or edits.

  Below 0.60 → escalate
    Confidence too low to risk an automated response.
    Better to have a human handle it than send a wrong reply.

  complaint → always escalate
    Regardless of score. Complaints involve emotional guests
    and potential refunds — never appropriate for automation.
    This is a hard business rule, not a soft threshold.
"""


def determine_action(confidence_score: float, query_type: str) -> str:
    """
    Returns the recommended action for a processed message.

    Complaint check runs before score check — query type
    takes absolute precedence over confidence for complaints.
    """
    # Complaints are always escalated to ensure human review
    # for sensitive guest situations involving dissatisfaction.
    if query_type == "complaint":
        return "escalate"

    if confidence_score >= 0.85:
        return "auto_send"

    if confidence_score >= 0.60:
        return "agent_review"

    # Score below 0.60 — system is not confident enough to act.
    # Escalate rather than risk a wrong or incomplete reply.
    return "escalate"