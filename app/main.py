"""
Application entry point.

Initialises the FastAPI app, registers routers, and mounts
global error handlers. Swagger UI available at /docs,
ReDoc at /redoc — both serve as the interactive demo layer.
"""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from app.routes.webhook import router as webhook_router
from app.utils.error_handlers import (
    validation_exception_handler,
    global_exception_handler
)

app = FastAPI(
    title="Nistula Guest Message Handler",
    description=(
        "Unified webhook system for processing guest messages across "
        "WhatsApp, Airbnb, Booking.com, Instagram, and Direct channels. "
        "Classifies intent, generates AI-drafted replies, scores confidence, "
        "and routes to auto-send, agent review, or escalation."
    ),
    version="1.0.0",
    contact={
        "name": "Nistula Engineering",
    },
    license_info={
        "name": "Private — Assessment Submission"
    }
)

# Global error handlers — catch validation failures and unexpected errors
# with consistent, clean response shapes across the entire application.
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

app.include_router(webhook_router, prefix="/webhook", tags=["Webhook"])


@app.get("/health", tags=["System"])
def health_check():
    """
    Liveness check — confirms the server is running and reachable.
    In production this would also check DB connectivity and AI service status.
    """
    return {
        "status": "ok",
        "service": "nistula-guest-message-handler",
        "version": "1.0.0"
    }