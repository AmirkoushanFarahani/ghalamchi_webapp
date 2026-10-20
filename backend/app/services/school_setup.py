"""Explicit school provisioning for authenticated writes and startup, never GETs."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import SchoolExamPlan, SchoolInstitute, User
from backend.app.services.academic_years import ensure_initial_years
from backend.app.services.exam_pricing import install_exam_catalog


def initialize_school_workspace(session: Session, actor: User) -> None:
    if (
        actor.business_category != "EDUCATION"
        or actor.school_manager_id is not None
        or "EMPLOYEE" in actor.role_names
        or "school:manage" not in actor.permission_names
    ):
        return
    # Serialize first-time setup across concurrent logins. The caller commits.
    session.scalar(select(User.id).where(User.id == actor.id).with_for_update())
    schools = list(
        session.scalars(
            select(SchoolInstitute)
            .where(SchoolInstitute.manager_id == actor.id)
            .order_by(SchoolInstitute.created_at)
        )
    )
    if not schools:
        school = SchoolInstitute(manager_id=actor.id, name="آموزشگاه اول")
        session.add(school)
        session.flush()
        schools.append(school)
    active = [school for school in schools if school.is_active]
    if active and actor.active_school_institute_id not in {school.id for school in active}:
        actor.active_school_institute_id = active[0].id
    for school in active:
        ensure_initial_years(session, actor.id, school.id)
        exists = session.scalar(
            select(SchoolExamPlan.id)
            .where(SchoolExamPlan.school_institute_id == school.id)
            .limit(1)
        )
        if exists is None:
            install_exam_catalog(session, actor.id, school.id)
