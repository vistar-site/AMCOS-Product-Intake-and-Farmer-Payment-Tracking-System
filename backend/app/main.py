"""Application entry point: builds the FastAPI app. No business logic lives here."""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import AppError, app_error_handler

settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(
    title="AMCOS Produce & Payment API",
    version="0.2.0",
    # Hide interactive docs in production
    docs_url=None if settings.environment == "production" else "/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,  # explicit list, never "*" with cookies
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.add_exception_handler(AppError, app_error_handler)


@app.exception_handler(OperationalError)
async def database_unavailable(_: Request, exc: OperationalError) -> JSONResponse:
    # Database unreachable (network, or a suspended hosted DB waking up): one log line, a clear 503.
    logging.getLogger("app.db").error("Database unavailable: %s", str(exc.orig or exc).splitlines()[0])
    return JSONResponse({"detail": "Database temporarily unavailable. Please try again in a moment.",
                         "code": "database_unavailable"}, status_code=503)
app.include_router(api_router, prefix="/api/v1")
