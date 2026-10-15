"""Append the bundled examsheet.xlsx pricing to every institute of one manager."""

import argparse

from backend.app.db.database import SessionLocal
from backend.app.db.models import SchoolInstitute, User
from backend.app.services.exam_pricing import install_exam_catalog
from sqlalchemy import select


def import_for_manager(email: str) -> int:
    with SessionLocal.begin() as session:
        manager = session.scalar(
            select(User).where(User.email == email, User.school_manager_id.is_(None))
        )
        if manager is None:
            raise ValueError("Manager account was not found; no data was changed")
        schools = list(
            session.scalars(select(SchoolInstitute).where(SchoolInstitute.manager_id == manager.id))
        )
        if not schools:
            raise ValueError("Manager has no institutes; no data was changed")
        total = 0
        for school in schools:
            added = install_exam_catalog(session, manager.id, school.id)
            total += added
            print(
                f"{school.name}: {added} new exam prices; previous prices and students preserved."
            )
    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manager-email", required=True)
    args = parser.parse_args()
    import_for_manager(args.manager_email)
