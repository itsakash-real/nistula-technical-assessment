# Thinking Questions — Nistula Technical Assessment

---

## Question A — The Immediate Response

**The message sent at 3am:**

> Hi Arjun, I'm really sorry — this is not the experience we want you to have. I've escalated this to our property team and someone will be in touch within 30 minutes. We will make this right.

It validates frustration without admitting liability. "Within 30 minutes" is a concrete, monitorable commitment — not vague reassurance. The refund isn't mentioned because engaging with money before resolving the problem signals wrong priorities. That conversation belongs to a human in daylight.

---

## Question B — The System Design

Classifier detects complaint keywords ("no hot water", "unacceptable", "refund"). Confidence floors at 0.40 — complaints bypass scoring. Action: `escalate`.

**T+0–3s:** Claude drafts an empathy-first reply. Escalation record created with severity `critical` and `sla_deadline = NOW() + 30 minutes`. The AI reply is sent to the guest immediately — no silence.

**Notifications fire simultaneously:**
- WhatsApp/SMS to on-call property manager — not email. 3am requires a channel loud enough to wake someone.
- Ops dashboard flags the escalation as critical.

**Logged:** Classification, AI draft, confidence score, action taken, escalation creation — all timestamped in `ai_message_metadata` and `escalations` tables.

**T+30min, no human response:** Background job checks `overdue_escalations` view. If `first_response_at` is NULL: `sla_breached` set to TRUE, second alert fires to senior manager, dashboard escalation card turns red.

**The gap:** Caretaker works 8am–10pm. No documented overnight on-call exists. The platform enforces the SLA but cannot invent an ops process that doesn't exist operationally.

---

## Question C — The Learning

Third hot water complaint at Villa B1 in two months. The `complaint_trends` view already surfaces this pattern.

**What gets built:**

1. **Pattern detection:** Weekly background job flags 3+ same-type complaints at one property within 60 days. Sends a direct notification to the property manager — not a dashboard card.

2. **Pre-arrival checklist:** 24 hours before every check-in, the caretaker receives an automated checklist. After the third hot water complaint, "test hot water system" is permanently added to Villa B1's list. No confirmation 6 hours before check-in triggers a property manager alert.

3. **Maintenance ticket:** Auto-created on the third complaint, linked to all three complaint messages for context.

The pre-arrival checklist is the highest-leverage fix — it prevents the guest from ever discovering the problem. The guest should never be the sensor.