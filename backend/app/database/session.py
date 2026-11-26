"""Database engine and per-request sessions.

engine        = the connection pool to PostgreSQL (one per process)
SessionLocal  = factory that creates a Session (a unit of work / transaction)
get_db()      = FastAPI dependency: opens a session for one request, always closes it
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.database.core.config import get_settings

engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,                     # test each pooled connection before use
    pool_recycle=240,                       # replace connections before a hosted DB (e.g. Neon) drops idle ones
    connect_args={"connect_timeout": 15},   # allow a suspended serverless database time to wake up
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
