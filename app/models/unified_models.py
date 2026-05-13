"""
Unified message schema — the internal contract.

Every inbound message, regardless of source channel, is
normalised into this shape before any service touches it.
This decouples channel-specific quirks from business logic.
"""

from pydantic import BaseModel
from typing import Literal, Optional
from datetime import datetime


QueryType = Literal[
    "pre_sales_availability",
    "pre_sales_pricing",
    "post_sales_checkin",
    "special_request",
    "complaint",
    "general_enquiry"
]


class UnifiedMessage(BaseModel):
    message_id: str
    source: str
    guest_name: str
    message_text: str
    timestamp: datetime
    booking_ref: Optional[str]
    property_id: str
    query_type: QueryType