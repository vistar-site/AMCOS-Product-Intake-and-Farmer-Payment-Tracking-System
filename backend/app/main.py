"""Application entry point: builds the FastAPI app. No business logic lives here."""
import logging

from fastapi import FastAPI
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
app.include_router(api_router, prefix="/api/v1")
