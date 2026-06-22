"""Error protocol and exception translation.

Defines domain exceptions and FastAPI exception handlers that translate
them into the standard {error: {code, message, ...}} JSON envelope.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# ── Helpers ─────────────────────────────────────────────────────────────


def _get_correlation_id(request: Request) -> str:
    """Extract the correlation ID set by CorrelationIdMiddleware.

    Falls back to generating a new one if the middleware has not run
    (e.g. during unit tests that bypass middleware).
    """
    return getattr(request.state, "correlation_id", uuid.uuid4().hex[:12])


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
        self.correlation_id = correlation_id


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


async def _api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    cid = exc.correlation_id or _get_correlation_id(request)
    return _build_error_response(
        status=exc.status_code,
        code=exc.code,
        message=str(exc),
        field_errors=exc.field_errors,
        correlation_id=cid,
    )


async def _validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle FastAPI request validation errors (wraps Pydantic errors).

    Returns the spec's {error: {code, message, fieldErrors, correlationId}} envelope.
    """
    field_errors: list[dict[str, str]] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", []))
        field_errors.append({"field": loc, "message": err.get("msg", "")})
    cid = _get_correlation_id(request)
    return _build_error_response(
        status=422,
        code="VALIDATION_ERROR",
        message="The request body failed validation.",
        field_errors=field_errors,
        correlation_id=cid,
    )


async def _generic_error_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    cid = _get_correlation_id(request)
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
    app.add_exception_handler(RequestValidationError, _validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _generic_error_handler)
