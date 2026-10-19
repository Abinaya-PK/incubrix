from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int = 400,
                 retryable: bool = False, details: dict | None = None):
        self.code = code
        self.message = message
        self.status = status
        self.retryable = retryable
        self.details = details or {}


def error_body(code, message, retryable=False, details=None):
    return {"error": {"code": code, "message": message,
                      "retryable": retryable, "details": details or {}}}


async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status,
                        content=error_body(exc.code, exc.message, exc.retryable, exc.details))


async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422,
                        content=error_body("INVALID_REQUEST", "Request validation failed",
                                           False, {"errors": exc.errors()}))