"""
Outbound response model.

Defines the exact shape of what the webhook endpoint returns.
Every field here is intentional — reviewers and downstream
systems should be able to trust this contract completely.
"""

from pydantic import BaseModel, Field
from typing import Literal


ActionType = Literal["auto_send", "agent_review", "escalate"]


class MessageResponse(BaseModel):
    message_id: str = Field(
        ...,
        description="UUID generated at normalisation — ties this response to the inbound message."
    )
    query_type: str = Field(
        ...,
        description="Classified intent of the guest message."
    )
    drafted_reply: str = Field(
        ...,
        description="AI-generated reply ready for sending or agent review."
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in the drafted reply. Drives the action decision."
    )
    action: ActionType = Field(
        ...,
        description="auto_send: score above 0.85. agent_review: 0.60-0.85. escalate: below 0.60 or complaint."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "query_type": "pre_sales_availability",
                "drafted_reply": "Hi Rahul! Great news — Villa B1 is available from April 20 to 24...",
                "confidence_score": 0.91,
                "action": "auto_send"
            }
        }