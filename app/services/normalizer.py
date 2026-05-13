"""
Normalizer service.

Converts any inbound payload into the unified message schema.
This is the first service called in the pipeline — it creates
the internal object that every other service depends on.

The query_type field is left empty here and filled by the
classifier in the next step. Separation of concerns.
"""

from app.models.request_models import InboundMessage
from app.models.unified_models import UnifiedMessage
from app.utils.helpers import generate_message_id


def normalize_message(payload: InboundMessage, query_type: str) -> UnifiedMessage:
    """
    Transforms a raw inbound payload into the unified internal schema.

    query_type is passed in from the classifier rather than computed
    here — normalizer handles shape, classifier handles meaning.
    """
    return UnifiedMessage(
        message_id=generate_message_id(),
        source=payload.source,
        guest_name=payload.guest_name,
        message_text=payload.message,
        timestamp=payload.timestamp,
        booking_ref=payload.booking_ref,
        property_id=payload.property_id,
        query_type=query_type
    )