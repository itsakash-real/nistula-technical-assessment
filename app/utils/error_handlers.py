"""
Global error handlers.

Registered on the FastAPI app in main.py. Provides consistent,
clean error responses across the entire application.

Design decision: error responses always return the same shape.
This means downstream systems and agents can always parse the
error format without conditional logic.

We deliberately do NOT expose internal exception messages to the
response body in production scenarios — they leak implementation
details and can be a security surface. The detail field contains
only what is safe and useful for the caller.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """
    Handles Pydantic validation failures — wrong types, missing
    fields, invalid enum values.

    Returns 422 with a structured breakdown of what failed and why.
    This is more useful to callers than the default FastAPI format.
    """
    errors = []
    for error in exc.errors():
        errors.append({
            "field": " → ".join(str(loc) for loc in error["loc"]),
            "issue": error["msg"],
            "received": error.get("input")
        })

    return JSONResponse(
        status_code=422,
        content={
            "error": "Request validation failed",
            "details": errors,
            "hint": "Check field types, required fields, and enum values against the schema at /docs"
        }
    )


async def global_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """
    Catches any unhandled exception that escapes the route layer.

    Returns 500 with a safe, non-revealing message.
    In production, this handler would also:
    - Log the full traceback to an observability platform
    - Trigger an ops alert if error rate exceeds threshold
    - Increment an error counter metric
    """
    return JSONResponse(
        status_code=500,
        content={
            "error": "An unexpected error occurred",
            "message": "Our team has been notified. Please try again shortly.",
            "support": "If this persists, contact support with your request timestamp."
        }
    )