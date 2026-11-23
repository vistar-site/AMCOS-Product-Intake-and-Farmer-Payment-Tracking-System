"""Health check: proves the API runs AND can reach PostgreSQL."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    try:
        version = db.execute(text("SELECT version()")).scalar_one()
        return {"status": "ok", "database": "connected", "postgres": version.split(",")[0]}
    except Exception as exc:  # report, don't crash, so we can diagnose
        return {"status": "degraded", "database": "unreachable", "error": type(exc).__name__}
