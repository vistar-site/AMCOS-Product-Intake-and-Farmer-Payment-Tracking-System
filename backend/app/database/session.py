"""Database engine and per-request sessions.

engine        = the connection pool to PostgreSQL (one per process)
SessionLocal  = factory that creates a Session (a unit of work / transaction)
get_db()      = FastAPI dependency: opens a session for one request, always closes it
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
