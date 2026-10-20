"""Academic-year provisioning is called only by authenticated writes/startup."""

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import SchoolAcademicYear


def ensure_initial_years(session: Session, owner_id: UUID, school_id: UUID) -> None:
    for name, start, end in (
        ("1405/1406", date(2026, 9, 23), date(2027, 6, 21)),
        ("1406/1407", date(2027, 9, 23), date(2028, 6, 20)),
    ):
        existing = session.scalar(
            select(SchoolAcademicYear.id).where(
                SchoolAcademicYear.school_institute_id == school_id,
                SchoolAcademicYear.name == name,
            )
        )
        if existing is None:
            session.add(
                SchoolAcademicYear(
                    workspace_owner_id=owner_id,
                    school_institute_id=school_id,
                    name=name,
                    starts_on=start,
                    ends_on=end,
                )
            )
    session.flush()
