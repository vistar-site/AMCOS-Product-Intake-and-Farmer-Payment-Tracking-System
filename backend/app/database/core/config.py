"""Application settings, read from environment variables (never hardcoded).

pydantic-settings validates the types: if DATABASE_URL is missing the app
refuses to start with a clear error, instead of failing later at random.
"""
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]

# Priority (highest first): real environment variables (Docker sets these),
# then backend/.env (local overrides, e.g. Neon URL), then the project-root .env.
ENV_FILES = (BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILES, extra="ignore")

    environment: str = "development"
    database_url: str
    secret_key: str
    access_token_expire_minutes: int = 15
    cors_origins: str = "http://localhost:5173"
    timezone: str = "Africa/Dar_es_Salaam"
    sms_provider: str = "mock"   # only "mock" is implemented; see app/integrations/sms/

    @field_validator("database_url")
    @classmethod
    def use_psycopg3_driver(cls, v: str) -> str:
        # Hosting providers (Vercel/Neon, Heroku...) hand out postgres:// or postgresql:// URLs,
        # which SQLAlchemy maps to psycopg2. This project ships psycopg (v3).
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    # Cached: settings are parsed once per process.
    return Settings()
