"""Shared fixed-window limits; hashes avoid storing account names and IPs."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from math import ceil

from sqlalchemy import case, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.app.db.models import AuthRateLimit


def database_auth_limit(session: Session, key: str, limit: int, window_seconds: int) -> int | None:
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=window_seconds)
    key_hash = sha256(key.encode()).hexdigest()
    # All workers/restarts share this atomic counter. No select-then-insert race.
    statement = insert(AuthRateLimit).values(key_hash=key_hash, window_started_at=now, attempts=1)
    expired = AuthRateLimit.window_started_at <= cutoff
    counter = statement.on_conflict_do_update(
        index_elements=[AuthRateLimit.key_hash],
        set_={
            "attempts": case((expired, 1), else_=AuthRateLimit.attempts + 1),
            "window_started_at": case((expired, now), else_=AuthRateLimit.window_started_at),
        },
    ).returning(AuthRateLimit.attempts, AuthRateLimit.window_started_at)
    attempts, started = session.execute(counter).one()
    # Bound retention and clean up inactive keys without retaining identifiers.
    session.execute(
        delete(AuthRateLimit).where(AuthRateLimit.window_started_at < now - timedelta(hours=2))
    )
    session.commit()
    return (
        max(1, ceil((started + timedelta(seconds=window_seconds) - now).total_seconds()))
        if attempts > limit
        else None
    )
