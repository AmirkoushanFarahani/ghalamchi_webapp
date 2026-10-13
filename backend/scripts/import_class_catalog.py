"""Import the supplied class.xlsx catalog into an explicitly selected manager school.

Run with --manager-email and --school-name; defaults to a dry run.
Add --apply to commit. Re-running skips unchanged records. Existing enrollments
retain their course-price snapshots, and unrelated courses are preserved.
"""

import argparse
import json
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from backend.app.db.database import SessionLocal
from backend.app.db.models import SchoolCourse, SchoolInstitute, User
from backend.app.schemas.school import CourseCreate

GRADES = {
    "دوم": "GRADE_2", "سوم": "GRADE_3", "چهارم": "GRADE_4",
    "پنجم": "GRADE_5", "ششم": "GRADE_6", "هفتم": "GRADE_7",
    "هشتم": "GRADE_8", "نهم": "GRADE_9", "دهم": "GRADE_10",
    "یازدهم": "GRADE_11", "دوازدهم": "GRADE_12",
}


def catalog() -> list[CourseCreate]:
    rows = json.loads((Path(__file__).parent / "data" / "class_catalog.json").read_text(encoding="utf-8"))
    courses = [CourseCreate(
        # Grade/major and teacher distinguish parallel classes within a grade.
        name=f"{row['subject']} — {row['level']} — {row['instructor_name']}",
        instructor_name=row["instructor_name"],
        grade=GRADES[row["level"].split()[0]],
        price=Decimal(row["price"]),
    ) for row in rows]
    if len({(row.grade, row.name) for row in courses}) != len(courses):
        raise ValueError("Duplicate class catalog keys")
    return courses


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manager-email", required=True)
    parser.add_argument("--school-name", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    rows = catalog()
    with SessionLocal() as session:
        manager = session.scalar(select(User).where(User.email == args.manager_email))
        if manager is None or manager.school_manager_id is not None:
            raise ValueError("Manager account not found")
        school = session.scalar(select(SchoolInstitute).where(
            SchoolInstitute.manager_id == manager.id, SchoolInstitute.name == args.school_name,
        ))
        if school is None:
            raise ValueError("School not found in this manager workspace")
        existing = {(row.grade, row.name): row for row in session.scalars(select(SchoolCourse).where(
            SchoolCourse.workspace_owner_id == manager.id,
            SchoolCourse.school_institute_id == school.id,
        ))}
        created = updated = unchanged = 0
        for data in rows:
            course = existing.get((data.grade, data.name))
            if course is None:
                session.add(SchoolCourse(workspace_owner_id=manager.id,
                                         school_institute_id=school.id, **data.model_dump()))
                created += 1
            elif course.price != data.price or course.instructor_name != data.instructor_name:
                course.price = data.price
                course.instructor_name = data.instructor_name
                updated += 1
            else:
                unchanged += 1
        if args.apply:
            session.commit()
        else:
            session.rollback()
        print(json.dumps({"school": school.name, "applied": args.apply,
                          "created": created, "updated": updated, "unchanged": unchanged},
                         ensure_ascii=False))


if __name__ == "__main__":
    main()
