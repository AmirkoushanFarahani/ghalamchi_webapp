"""Explicit idempotent setup after migrations; never initialize through a GET."""

from backend.app.db.database import SessionLocal
from backend.app.db.models import User
from backend.app.services.school_setup import initialize_school_workspace
from sqlalchemy import select


def main() -> None:
    with SessionLocal.begin() as session:
        for user in session.scalars(select(User).where(User.is_active.is_(True))):
            initialize_school_workspace(session, user)
    print("School workspace initialization completed; existing prices preserved")


if __name__ == "__main__":
    main()
