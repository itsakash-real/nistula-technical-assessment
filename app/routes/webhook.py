"""
Webhook route — intake and delegation only.

This file is intentionally minimal. Its responsibilities are:
1. Accept the incoming payload
2. Validate shape via Pydantic (automatic)
3. Delegate to services in the correct order
4. Return the shaped response

No business logic lives here. If you find yourself writing
conditional logic in this file, it belongs in a service instead.
"""

from fastapi import APIRouter, HTTPException
from app.models.request_models import InboundMessage
from app.models.response_models import MessageResponse
from app.services.classifier import classify_query
from app.services.normalizer import normalize_message
from app.services.claude_service import generate_reply
from app.services.confidence import calculate_confidence
from app.services.action_router import determine_action

router = APIRouter()


@router.post(
    "/message",
    response_model=MessageResponse,
    summary="Process an inbound guest message",
    description="Accepts a guest message from any supported channel, classifies intent, generates an AI reply, and returns a confidence-scored response with a recommended action."
)
async def handle_message(payload: InboundMessage):
    """
    Full message processing pipeline.

    Payload → Classify → Normalise → AI Reply → Score → Action → Response
    """
    try:
        # Step 1: Classify intent from raw message text
        query_type = classify_query(payload.message)

        # Step 2: Normalise into unified internal schema
        unified = normalize_message(payload, query_type)

        # Step 3: Generate AI reply using property context
        drafted_reply = await generate_reply(unified)

        # Step 4: Score confidence based on query type and context
        confidence_score = calculate_confidence(unified)

        # Step 5: Determine action based on score and query type
        action = determine_action(confidence_score, query_type)

        return MessageResponse(
            message_id=unified.message_id,
            query_type=unified.query_type,
            drafted_reply=drafted_reply,
            confidence_score=confidence_score,
            action=action
        )

    except Exception as e:
        # Catches unexpected failures without exposing internals.
        # Claude API failures have their own handling in claude_service.py.
        raise HTTPException(
            status_code=500,
            detail=f"Message processing failed: {str(e)}"
        )