"""
Incoming webhook payload model.

Defines and validates the shape of every inbound guest message
before it touches any business logic. If the payload doesn't
match this shape, FastAPI returns a 422 automatically — no
manual validation code needed.
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime


class InboundMessage(BaseModel):
    source: Literal["whatsapp", "booking_com", "airbnb", "instagram", "direct"] = Field(
        ...,
        description="The channel this message arrived from."
    )
    guest_name: str = Field(
        ...,
        min_length=1,
        description="Full name of the guest as provided by the channel."
    )
    message: str = Field(
        ...,
        min_length=1,
        description="Raw message text from the guest."
    )
    timestamp: datetime = Field(
        ...,
        description="ISO 8601 timestamp of when the message was sent."
    )
    booking_ref: Optional[str] = Field(
        default=None,
        description="Booking reference if available. Pre-sales enquiries may not have one."
    )
    property_id: str = Field(
        ...,
        description="Identifier of the property this message relates to."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "source": "whatsapp",
                "guest_name": "Rahul Sharma",
                "message": "Is the villa available from April 20 to 24? What is the rate for 2 adults?",
                "timestamp": "2026-05-05T10:30:00Z",
                "booking_ref": "NIS-2024-0891",
                "property_id": "villa-b1"
            }
        }