"""Domain errors raised by services, translated to HTTP responses in one place.

Services don't know about HTTP; they raise e.g. NotFoundError("Farmer not found").
main.py registers a handler that turns every AppError into
{"detail": "...", "code": "..."} with the right status code.
"""
from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class NotFoundError(AppError):
    status_code, code = 404, "not_found"


class ConflictError(AppError):
    status_code, code = 409, "conflict"


class AuthenticationError(AppError):
    status_code, code = 401, "not_authenticated"


class PermissionDeniedError(AppError):
    status_code, code = 403, "permission_denied"


class ValidationFailedError(AppError):
    status_code, code = 422, "validation_failed"


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return JSONResponse({"detail": exc.detail, "code": exc.code}, status_code=exc.status_code, headers=headers)
