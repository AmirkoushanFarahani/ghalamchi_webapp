"""Export/import the local synthetic school demo without stored credentials.

Export writes JSON to stdout. Import reads the committed snapshot and requires
DEMO_IMPORT_PASSWORD. Import refuses to overwrite existing accounts or records.
"""

import argparse
import base64
import gzip
import json
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from backend.app.core.passwords import hash_password
from backend.app.db.bootstrap import seed_rbac
from backend.app.db.database import SessionLocal
from backend.app.db.models import (
    DiscountCode, EnrollmentCourse, EnrollmentPayment, Role, SchoolCost,
    SchoolCourse, SchoolExamPlan, SchoolInstitute, SchoolRegistrationFees,
    SchoolSpecialSupport, Student, StudentEnrollment, User,
)

MANAGER_EMAIL = "demo.school.manager2@example.com"
MODELS = (SchoolInstitute, SchoolCourse, DiscountCode, SchoolRegistrationFees,
          SchoolExamPlan, SchoolSpecialSupport, Student, StudentEnrollment,
          EnrollmentCourse, EnrollmentPayment, SchoolCost)
SNAPSHOT = Path(__file__).parent / "data" / "demo_database.json.gz.b64"


def export_demo() -> None:
    with SessionLocal() as session:
        manager = session.scalar(select(User).where(User.email == MANAGER_EMAIL))
        if manager is None:
            raise ValueError("Demo manager not found")
        users = [manager, *session.scalars(select(User).where(
            User.school_manager_id == manager.id,
            User.email.like("demo.school.%@example.com"),
        ).order_by(User.email))]
        users_by_id = {user.id: user for user in users}
        data = {"format_version": 1, "users": [{
            key: getattr(user, key) for key in (
                "id", "email", "first_name", "last_name", "business_category",
                "school_manager_id", "school_institute_id", "active_school_institute_id",
            )
        } | {"roles": user.role_names} for user in users], "tables": {}}
        students = list(session.scalars(select(Student).where(
            Student.workspace_owner_id == manager.id,
            (Student.national_id.like("910000%") | Student.national_id.like("920000%")),
            Student.notes.like("%آزمایشی%") | Student.national_id.in_(
                [f"910000000{i}" for i in range(1, 7)]
            ),
        )))
        student_ids = [student.id for student in students]
        enrollments = list(session.scalars(select(StudentEnrollment).where(
            StudentEnrollment.student_id.in_(student_ids)
        )))
        enrollment_ids = [row.id for row in enrollments]
        for model in MODELS:
            if model is SchoolInstitute:
                rows = session.scalars(select(model).where(model.manager_id == manager.id))
            elif model is Student:
                rows = students
            elif model is StudentEnrollment:
                rows = enrollments
            elif model in (EnrollmentCourse, EnrollmentPayment):
                rows = session.scalars(select(model).where(model.enrollment_id.in_(enrollment_ids)))
            elif model is SchoolCost:
                rows = session.scalars(select(model).where(
                    model.workspace_owner_id == manager.id, model.factor_number.like("GIRLS-COST-%")
                ))
            else:
                rows = session.scalars(select(model).where(model.workspace_owner_id == manager.id))
            records = []
            for row in rows:
                record = {column.name: getattr(row, column.name) for column in model.__table__.columns}
                # Do not export references to non-demo staff accounts.
                for field in ("created_by_id", "recorded_by_id"):
                    if field in record and record[field] not in users_by_id:
                        record[field] = manager.id
                records.append(record)
            data["tables"][model.__tablename__] = records
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def typed_values(model, record: dict) -> dict:
    result = {}
    for column in model.__table__.columns:
        value = record.get(column.name)
        if value is not None:
            datatype = column.type.python_type
            if datatype is UUID:
                value = UUID(value)
            elif datatype is Decimal:
                value = Decimal(value)
            elif datatype in (date, datetime):
                value = datatype.fromisoformat(value)
        result[column.name] = value
    return result


def import_demo() -> None:
    password = os.environ.get("DEMO_IMPORT_PASSWORD", "")
    if not 12 <= len(password) <= 128:
        raise ValueError("Set DEMO_IMPORT_PASSWORD to a new password of 12–128 characters")
    data = json.loads(gzip.decompress(base64.b64decode(SNAPSHOT.read_text(encoding="ascii"))))
    if data["format_version"] != 1:
        raise ValueError("Unsupported snapshot version")
    with SessionLocal.begin() as session:
        if session.scalar(select(User.id).where(User.email.in_([u["email"] for u in data["users"]]))):
            raise ValueError("Demo accounts already exist; no data was imported or overwritten")
        seed_rbac(session)
        users = []
        for record in data["users"]:
            values = {key: value for key, value in record.items() if key != "roles"}
            for key in ("id", "school_manager_id", "school_institute_id", "active_school_institute_id"):
                if values[key] is not None:
                    values[key] = UUID(values[key])
            pending_school = values.pop("school_institute_id")
            pending_active = values.pop("active_school_institute_id")
            user = User(**values, password_hash=hash_password(password), roles=[
                session.scalar(select(Role).where(Role.name == name)) for name in record["roles"]
            ])
            session.add(user)
            session.flush()
            users.append((user, pending_school, pending_active))
        for model in MODELS:
            for record in data["tables"][model.__tablename__]:
                if session.get(model, UUID(record["id"])) is not None:
                    raise ValueError("Snapshot ID already exists; import rolled back")
                session.add(model(**typed_values(model, record)))
            session.flush()
            if model is SchoolInstitute:
                for user, school_id, active_id in users:
                    user.school_institute_id = school_id
                    user.active_school_institute_id = active_id
                session.flush()
    print("Demo school database imported successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("export", "import"))
    args = parser.parse_args()
    export_demo() if args.operation == "export" else import_demo()
