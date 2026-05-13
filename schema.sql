-- ============================================================
-- NISTULA UNIFIED MESSAGING PLATFORM — DATABASE SCHEMA
-- ============================================================
--
-- Design Philosophy:
-- This schema supports an omnichannel hospitality messaging
-- platform where the same guest may contact via WhatsApp,
-- Airbnb, Booking.com, Instagram, or direct channels.
--
-- Three core principles drove every decision:
--
-- 1. Channel independence
--    Guests are unified at the identity layer, not the
--    channel layer. A guest is a person, not a WhatsApp number.
--
-- 2. Full AI audit trail
--    Every AI decision is stored with enough context to
--    reconstruct exactly what happened and why. Required
--    for ops review, dispute resolution, and model improvement.
--
-- 3. Conversation threading
--    Messages belong to conversations. Conversations belong
--    to guests and reservations. This mirrors how hospitality
--    teams actually think about guest communication.
--
-- ============================================================


-- ============================================================
-- TABLE: properties
-- ============================================================
-- Stores villa and property data.
-- Kept separate so property context can evolve independently
-- of guest and messaging data.
-- ============================================================

CREATE TABLE properties (
    id                  VARCHAR(50) PRIMARY KEY,
    -- e.g. "villa-b1" — matches property_id in webhook payload

    name                VARCHAR(255) NOT NULL,
    location            VARCHAR(255),
    bedrooms            INTEGER NOT NULL DEFAULT 1,
    max_guests          INTEGER NOT NULL DEFAULT 2,
    private_pool        BOOLEAN DEFAULT FALSE,
    check_in_time       TIME DEFAULT '14:00:00',
    check_out_time      TIME DEFAULT '11:00:00',
    base_rate_inr       NUMERIC(10, 2),
    extra_guest_rate_inr NUMERIC(10, 2),
    wifi_password       VARCHAR(100),
    caretaker_hours     VARCHAR(100),
    chef_available      BOOLEAN DEFAULT FALSE,
    cancellation_policy TEXT,

    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE properties IS
    'Villa and property reference data. Source of truth for property context injected into AI prompts.';

COMMENT ON COLUMN properties.id IS
    'Human-readable slug matching the property_id field in webhook payloads. e.g. villa-b1';


-- ============================================================
-- TABLE: guests
-- ============================================================
-- One record per real-world guest, regardless of channel.
--
-- HARDEST DESIGN DECISION:
-- How do you unify a guest who contacts via WhatsApp and then
-- books via Airbnb? They will have different channel IDs and
-- may not share an email.
--
-- Decision: booking_ref is the unification anchor for known
-- guests. For pre-sales inquiries with no booking reference,
-- a provisional record is created with identity_verified=false.
-- Human ops must merge provisional records when the same guest
-- later makes a booking. This is honest about the limitation
-- rather than silently guessing wrong.
--
-- Alternative considered: phone number as primary identity.
-- Rejected because international number formatting creates
-- false duplicates (+91 9876543210 vs 09876543210).
-- ============================================================

CREATE TABLE guests (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name           VARCHAR(255) NOT NULL,
    email               VARCHAR(255),
    -- Nullable — WhatsApp and Instagram contacts often carry no email

    phone               VARCHAR(50),
    -- Stored normalised (E.164 format) to reduce duplicate risk
    -- e.g. +919876543210 not 09876543210

    preferred_channel   VARCHAR(50),
    -- The channel this guest most reliably uses

    identity_verified   BOOLEAN DEFAULT FALSE,
    -- FALSE for provisional pre-sales guests with no booking_ref.
    -- Human ops reviews and merges these when a booking is made.
    -- TRUE once guest is linked to at least one confirmed reservation.

    notes               TEXT,
    -- Internal ops notes — preferences, past issues, VIP flags

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT guests_email_check CHECK (
        email IS NULL OR email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
    )
);

COMMENT ON TABLE guests IS
    'Unified guest identity across all channels. One row per real-world person regardless of how many channels they use.';

COMMENT ON COLUMN guests.identity_verified IS
    'FALSE for provisional guest records created from pre-sales inquiries with no booking reference. Requires human review to merge with confirmed booking identity.';


-- ============================================================
-- TABLE: guest_channel_identities
-- ============================================================
-- Maps each channel-specific identifier to a unified guest.
-- A guest can have multiple channel identities — one per
-- platform they use to contact the property.
--
-- This table is what makes channel unification possible.
-- Instead of storing channel IDs on the guest record (which
-- would require nullable columns per channel), we normalise
-- them here. Adding a new channel requires no schema change.
-- ============================================================

CREATE TABLE guest_channel_identities (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_id            UUID NOT NULL REFERENCES guests(id) ON DELETE CASCADE,

    channel             VARCHAR(50) NOT NULL,
    -- e.g. whatsapp, airbnb, booking_com, instagram, direct

    channel_guest_id    VARCHAR(255) NOT NULL,
    -- The identifier this channel uses for the guest.
    -- WhatsApp: phone number
    -- Airbnb: airbnb user ID
    -- Booking.com: reservation ID or guest ID
    -- Instagram: @handle

    channel_display_name VARCHAR(255),
    -- Name as shown on that platform — may differ from guests.full_name

    created_at          TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (channel, channel_guest_id)
    -- One guest per channel per identifier.
    -- Prevents duplicate mappings for the same channel account.
);

COMMENT ON TABLE guest_channel_identities IS
    'Maps channel-specific identifiers to unified guest records. Enables the same guest to be recognised across WhatsApp, Airbnb, and other channels.';


-- ============================================================
-- TABLE: reservations
-- ============================================================
-- Booking records linked to guests and properties.
-- booking_ref is the primary business identifier — it appears
-- in webhook payloads and is used for guest unification.
-- ============================================================

CREATE TABLE reservations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_ref         VARCHAR(100) NOT NULL UNIQUE,
    -- e.g. NIS-2024-0891 — the business-facing reference

    guest_id            UUID NOT NULL REFERENCES guests(id),
    property_id         VARCHAR(50) NOT NULL REFERENCES properties(id),

    channel             VARCHAR(50) NOT NULL,
    -- Channel through which the booking was made

    check_in_date       DATE NOT NULL,
    check_out_date      DATE NOT NULL,
    num_guests          INTEGER NOT NULL DEFAULT 1,
    total_amount_inr    NUMERIC(12, 2),

    status              VARCHAR(50) NOT NULL DEFAULT 'confirmed',
    -- confirmed, cancelled, completed, no_show

    special_requests    TEXT,
    internal_notes      TEXT,

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_dates CHECK (check_out_date > check_in_date),
    CONSTRAINT valid_guest_count CHECK (num_guests > 0)
);

COMMENT ON TABLE reservations IS
    'Booking records. booking_ref is the anchor for guest identity unification — it is channel-independent and deterministic.';

CREATE INDEX idx_reservations_booking_ref ON reservations(booking_ref);
CREATE INDEX idx_reservations_guest_id ON reservations(guest_id);
CREATE INDEX idx_reservations_property_id ON reservations(property_id);
CREATE INDEX idx_reservations_check_in ON reservations(check_in_date);


-- ============================================================
-- TABLE: conversations
-- ============================================================
-- A conversation is a thread of messages between a guest
-- and the property team, scoped to a channel and optionally
-- linked to a reservation.
--
-- Why separate conversations from messages?
-- A single booking might generate multiple distinct threads:
-- pre-arrival logistics, an in-stay complaint, a post-stay
-- review request. Threading these as one conversation would
-- make ops review and AI context injection unmanageable.
-- ============================================================

CREATE TABLE conversations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_id            UUID NOT NULL REFERENCES guests(id),
    reservation_id      UUID REFERENCES reservations(id),
    -- Nullable — pre-sales conversations have no reservation yet

    property_id         VARCHAR(50) NOT NULL REFERENCES properties(id),
    channel             VARCHAR(50) NOT NULL,
    -- Channel this conversation is happening on

    status              VARCHAR(50) NOT NULL DEFAULT 'open',
    -- open, resolved, escalated, waiting_guest, waiting_team

    subject             VARCHAR(255),
    -- Optional human-readable label e.g. "Hot water complaint — May 7"

    opened_at           TIMESTAMPTZ DEFAULT NOW(),
    resolved_at         TIMESTAMPTZ,
    last_message_at     TIMESTAMPTZ DEFAULT NOW(),
    -- Denormalised for fast inbox sorting without a subquery

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE conversations IS
    'Conversation threads scoped to a guest, channel, and optionally a reservation. One booking can have multiple conversations for different topics.';

CREATE INDEX idx_conversations_guest_id ON conversations(guest_id);
CREATE INDEX idx_conversations_reservation_id ON conversations(reservation_id);
CREATE INDEX idx_conversations_status ON conversations(status);
CREATE INDEX idx_conversations_last_message ON conversations(last_message_at DESC);


-- ============================================================
-- TABLE: messages
-- ============================================================
-- Every inbound and outbound message across all channels.
-- This is the central fact table of the platform.
--
-- Design decision: inbound and outbound messages live in
-- the same table, distinguished by direction. Alternative
-- (separate tables) was rejected because it makes
-- conversation reconstruction require a UNION — expensive
-- and error-prone for the ops inbox view.
-- ============================================================

CREATE TABLE messages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- This is the message_id returned in the webhook response

    conversation_id     UUID NOT NULL REFERENCES conversations(id),
    guest_id            UUID NOT NULL REFERENCES guests(id),
    property_id         VARCHAR(50) NOT NULL REFERENCES properties(id),

    direction           VARCHAR(10) NOT NULL,
    -- inbound: guest → platform
    -- outbound: platform → guest

    channel             VARCHAR(50) NOT NULL,
    raw_content         TEXT NOT NULL,
    -- Exact message text as received or sent

    sent_at             TIMESTAMPTZ NOT NULL,
    -- For inbound: timestamp from payload. For outbound: time of send.

    delivery_status     VARCHAR(50) DEFAULT 'received',
    -- received, queued, sent, delivered, failed

    created_at          TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_direction CHECK (direction IN ('inbound', 'outbound')),
    CONSTRAINT valid_channel CHECK (
        channel IN ('whatsapp', 'booking_com', 'airbnb', 'instagram', 'direct')
    )
);

COMMENT ON TABLE messages IS
    'All inbound and outbound messages across every channel in one table. Direction field distinguishes guest messages from platform replies.';

CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_messages_guest_id ON messages(guest_id);
CREATE INDEX idx_messages_direction ON messages(direction);
CREATE INDEX idx_messages_sent_at ON messages(sent_at DESC);


-- ============================================================
-- TABLE: ai_message_metadata
-- ============================================================
-- AI audit trail — one record per inbound message that was
-- processed by the AI pipeline.
--
-- This table answers the question ops will always ask:
-- "What did the AI decide, why, and what happened next?"
--
-- Stored separately from messages because:
-- 1. Not every message is AI-processed (agent-written outbound
--    messages have no AI metadata)
-- 2. AI metadata has a very different shape from message content
-- 3. Keeping it separate means the messages table stays lean
--    and fast for inbox queries
--
-- agent_edited_reply captures what the agent actually sent
-- if they modified the AI draft. This is the ground truth
-- for model fine-tuning and quality review.
-- ============================================================

CREATE TABLE ai_message_metadata (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id          UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    -- Links to the inbound message that triggered AI processing

    query_type          VARCHAR(50) NOT NULL,
    -- Classification result: pre_sales_availability, complaint, etc.

    ai_drafted_reply    TEXT NOT NULL,
    -- The reply as generated by Claude — before any agent edits

    confidence_score    NUMERIC(4, 3) NOT NULL,
    -- 0.000 to 1.000 — stored with 3 decimal precision

    action_taken        VARCHAR(50) NOT NULL,
    -- auto_send, agent_review, escalate

    -- What actually happened after the action decision:
    agent_edited_reply  TEXT,
    -- If agent modified the draft, their version is stored here.
    -- NULL means the AI draft was sent unmodified or not yet actioned.

    final_reply_sent    TEXT,
    -- The exact text delivered to the guest.
    -- Populated once the reply is confirmed sent.

    reviewed_by_agent   UUID REFERENCES guests(id),
    -- Agent who reviewed/approved — references an internal user.
    -- In production this would reference a staff/users table.
    -- Using guest UUID here as a simplification for this assessment.

    reviewed_at         TIMESTAMPTZ,
    escalated_at        TIMESTAMPTZ,
    auto_sent_at        TIMESTAMPTZ,

    model_version       VARCHAR(100) DEFAULT 'claude-sonnet-4-20250514',
    -- Stored so quality regressions can be traced to model changes

    processing_time_ms  INTEGER,
    -- Time taken for the full AI pipeline — useful for SLA monitoring

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE ai_message_metadata IS
    'Full AI audit trail per inbound message. Stores classification, confidence score, action taken, original AI draft, and final sent reply. Required for ops review, dispute resolution, and model improvement.';

COMMENT ON COLUMN ai_message_metadata.agent_edited_reply IS
    'Populated when an agent modifies the AI draft before sending. The diff between ai_drafted_reply and agent_edited_reply is training signal for model improvement.';

COMMENT ON COLUMN ai_message_metadata.model_version IS
    'Claude model used to generate the reply. Stored to enable quality regression analysis when model versions change.';

CREATE INDEX idx_ai_metadata_message_id ON ai_message_metadata(message_id);
CREATE INDEX idx_ai_metadata_query_type ON ai_message_metadata(query_type);
CREATE INDEX idx_ai_metadata_action ON ai_message_metadata(action_taken);
CREATE INDEX idx_ai_metadata_confidence ON ai_message_metadata(confidence_score);
CREATE INDEX idx_ai_metadata_created ON ai_message_metadata(created_at DESC);


-- ============================================================
-- TABLE: escalations
-- ============================================================
-- Tracks escalated messages through to resolution.
-- Supports SLA monitoring and the 30-minute no-response rule.
--
-- Why a separate table and not just a status on messages?
-- Escalations have their own lifecycle — they are created,
-- assigned, actioned, and resolved independently of the
-- underlying message. Storing this on the message record
-- would mean updating a row every time the escalation
-- state changes, making audit history impossible.
-- ============================================================

CREATE TABLE escalations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id          UUID NOT NULL REFERENCES messages(id),
    conversation_id     UUID NOT NULL REFERENCES conversations(id),
    guest_id            UUID NOT NULL REFERENCES guests(id),
    property_id         VARCHAR(50) NOT NULL REFERENCES properties(id),

    reason              VARCHAR(100) NOT NULL,
    -- complaint, low_confidence, ai_failure, sla_breach

    severity            VARCHAR(20) NOT NULL DEFAULT 'medium',
    -- low, medium, high, critical

    status              VARCHAR(50) NOT NULL DEFAULT 'open',
    -- open, assigned, in_progress, resolved, closed

    assigned_to         VARCHAR(255),
    -- Agent or team assigned to handle this escalation

    escalated_at        TIMESTAMPTZ DEFAULT NOW(),
    first_response_at   TIMESTAMPTZ,
    -- When a human first responded after escalation

    resolved_at         TIMESTAMPTZ,
    resolution_notes    TEXT,

    sla_deadline        TIMESTAMPTZ,
    -- For 3am complaints: escalated_at + 30 minutes.
    -- System triggers alert if first_response_at is NULL
    -- after sla_deadline passes.

    sla_breached        BOOLEAN DEFAULT FALSE,
    -- TRUE if first_response_at > sla_deadline or NULL at deadline

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE escalations IS
    'Tracks escalated messages from creation to resolution. sla_deadline and sla_breached support the 30-minute response window for urgent issues.';

COMMENT ON COLUMN escalations.sla_deadline IS
    'Computed at escalation time based on severity. A 3am complaint gets escalated_at + 30 minutes. A background ops issue might get next business day.';

CREATE INDEX idx_escalations_status ON escalations(status);
CREATE INDEX idx_escalations_sla ON escalations(sla_deadline) WHERE sla_breached = FALSE;
CREATE INDEX idx_escalations_property ON escalations(property_id);
CREATE INDEX idx_escalations_severity ON escalations(severity);


-- ============================================================
-- VIEWS
-- ============================================================
-- Convenience views for common ops queries.
-- Not required but shows production thinking.
-- ============================================================

-- Active escalations past their SLA deadline
CREATE VIEW overdue_escalations AS
SELECT
    e.id,
    e.reason,
    e.severity,
    e.sla_deadline,
    e.escalated_at,
    g.full_name AS guest_name,
    p.name AS property_name,
    NOW() - e.sla_deadline AS overdue_by
FROM escalations e
JOIN guests g ON e.guest_id = g.id
JOIN properties p ON e.property_id = p.id
WHERE
    e.status NOT IN ('resolved', 'closed')
    AND e.sla_deadline < NOW()
    AND e.first_response_at IS NULL;

COMMENT ON VIEW overdue_escalations IS
    'Live view of escalations past their SLA deadline with no human response. Used by the ops alerting system.';


-- Complaint frequency by property — feeds the pattern detection
-- discussed in thinking.md (third hot water complaint scenario)
CREATE VIEW complaint_trends AS
SELECT
    m.property_id,
    p.name AS property_name,
    ai.query_type,
    DATE_TRUNC('month', m.sent_at) AS month,
    COUNT(*) AS complaint_count
FROM messages m
JOIN ai_message_metadata ai ON ai.message_id = m.id
JOIN properties p ON m.property_id = p.id
WHERE
    m.direction = 'inbound'
    AND ai.query_type = 'complaint'
GROUP BY
    m.property_id,
    p.name,
    ai.query_type,
    DATE_TRUNC('month', m.sent_at)
ORDER BY
    month DESC,
    complaint_count DESC;

COMMENT ON VIEW complaint_trends IS
    'Monthly complaint counts per property. Used to detect recurring issues — e.g. three hot water complaints at Villa B1 within two months triggers a preventive maintenance alert.';