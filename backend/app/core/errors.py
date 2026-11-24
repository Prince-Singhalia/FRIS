"""Application error types and exception handlers."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class FRISError(Exception):
    """Base error for the application."""

    def __init__(self, message: str, status_code: int = 500, detail: str | None = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail or message
        super().__init__(self.message)


class NotFoundError(FRISError):
    def __init__(self, entity: str, identifier: str | None = None):
        msg = f"{entity} not found"
        if identifier:
            msg = f"{entity} '{identifier}' not found"
        super().__init__(msg, status_code=404)


class ConflictError(FRISError):
    def __init__(self, message: str = "Resource conflict"):
        super().__init__(message, status_code=409)


class ForbiddenError(FRISError):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, status_code=403)


class UnauthorizedError(FRISError):
    def __init__(self, message: str = "Not authenticated"):
        super().__init__(message, status_code=401)


class ValidationError(FRISError):
    def __init__(self, message: str = "Validation error"):
        super().__init__(message, status_code=422)


class TenantAccessError(ForbiddenError):
    def __init__(self):
        super().__init__("Cross-tenant access denied")


async def fris_error_handler(request: Request, exc: FRISError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "detail": exc.detail},
    )
