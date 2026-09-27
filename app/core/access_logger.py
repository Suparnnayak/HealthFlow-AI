"""
Access Logger Middleware / Service

Records user data-read access for forecast and agent queries.
"""

from typing import Optional
from datetime import datetime, timezone
import json
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from sqlalchemy.orm import Session

from database.session import SessionLocal
from database.models import AccessLog
from app.auth.security import decode_access_token


def log_access(
    user_id: Optional[str],
    hospital_id: Optional[str],
    endpoint: str,
    query_params: Optional[dict] = None,
):
    """Write an access record to access_log table asynchronously or safely."""
    try:
        db: Session = SessionLocal()
        record = AccessLog(
            user_id=user_id,
            hospital_id=hospital_id,
            endpoint=endpoint,
            timestamp=datetime.now(timezone.utc),
            query_params=json.dumps(query_params) if query_params else None,
        )
        db.add(record)
        db.commit()
        db.close()
    except Exception as exc:
        # Never fail a request because access logging encountered an issue
        pass
