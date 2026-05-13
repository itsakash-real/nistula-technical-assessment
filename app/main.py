"""
Application entry point.

Initialises the FastAPI app, registers routers, and exposes
metadata for Swagger/OpenAPI documentation at /docs and /redoc.
"""

from fastapi import FastAPI
from app.routes.webhook import router as webhook_router

app = FastAPI(
    title="Nistula Guest Message Handler",
    description="Unified webhook system for processing guest messages across channels.",
    version="1.0.0"
)

app.include_router(webhook_router, prefix="/webhook")


@app.get("/health")
def health_check():
    """Quick liveness check — confirms the server is running."""
    return {"status": "ok"}