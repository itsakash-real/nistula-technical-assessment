"""
Webhook route — intake only.

This file is intentionally thin. Its only job is to receive
the payload, validate its shape, and delegate to services.
No business logic lives here.
"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/message")
def handle_message():
    """Placeholder — full implementation in Phase 2."""
    return {"status": "webhook alive"}