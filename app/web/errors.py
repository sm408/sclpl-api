"""Error protocol and exception translation.

Defines domain exceptions and FastAPI exception handlers that translate
them into the standard {error: {code, message, ...}} JSON envelope.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# ── Domain exceptions ───────────────────────────────────────────────────


class ApiError(Exception):
    """Base for all API domain errors."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        field_errors: list[dict[str, str]] | None = None,
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(message or self.__class__.message)
        if code is not None:
            self.code = code
        self.field_errors = field_errors or []
        self.correlation_id = correlation_id or uuid.uuid4().hex[:12]


class NotFoundError(ApiError):
    status_code = 404
    code = "NOT_FOUND"
    message = "The requested resource was not found."


class ValidationError(ApiError):
    status_code = 422
    code = "VALIDATION_ERROR"
    message = "The request body failed validation."


class ConflictError(ApiError):
    status_code = 409
    code = "CONFLICT"
    message = "The request conflicts with the current state."


class BadRequestError(ApiError):
    status_code = 400
    code = "BAD_REQUEST"
    message = "The request was malformed or invalid."


class RateLimitError(ApiError):
    status_code = 429
    code = "RATE_LIMITED"
    message = "Too many requests. Please try again later."


class ServiceUnavailableError(ApiError):
    status_code = 503
    code = "SERVICE_UNAVAILABLE"
    message = "The service is temporarily unavailable."


# ── Exception handlers ──────────────────────────────────────────────────


def _build_error_response(
    status: int,
    code: str,
    message: str,
    *,
    field_errors: list[dict[str, str]] | None = None,
    correlation_id: str = "",
) -> JSONResponse:
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "fieldErrors": field_errors or [],
            "correlationId": correlation_id,
        }
    }
    return JSONResponse(status_code=status, content=body)


async def _api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    return _build_error_response(
        status=exc.status_code,
        code=exc.code,
        message=str(exc),
        field_errors=exc.field_errors,
        correlation_id=exc.correlation_id,
    )


async def _validation_error_handler(
    _request: Request, exc: Exception
) -> JSONResponse:
    """Handle Pydantic validation errors raised by FastAPI."""
    from pydantic import ValidationError as PydanticValidationError

    if isinstance(exc, PydanticValidationError):
        field_errors = []
        for err in exc.errors():
            loc = ".".join(str(part) for part in err.get("loc", []))
            field_errors.append(
                {"field": loc, "message": err.get("msg", "")}
            )
        cid = uuid.uuid4().hex[:12]
        return _build_error_response(
            status=422,
            code="VALIDATION_ERROR",
            message="The request body failed validation.",
            field_errors=field_errors,
            correlation_id=cid,
        )
    # Fallback for other validation-like errors
    cid = uuid.uuid4().hex[:12]
    logger.exception("Unhandled validation error")
    return _build_error_response(
        status=422,
        code="VALIDATION_ERROR",
        message=str(exc),
        correlation_id=cid,
    )


async def _generic_error_handler(
    _request: Request, exc: Exception
) -> JSONResponse:
    cid = uuid.uuid4().hex[:12]
    logger.exception("Unhandled error [%s]", cid)
    return _build_error_response(
        status=500,
        code="INTERNAL_ERROR",
        message="An unexpected error occurred.",
        correlation_id=cid,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Attach all error handlers to the FastAPI app."""
    app.add_exception_handler(ApiError, _api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _generic_error_handler)
