from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.db.models import (
    DiscountCode,
    EnrollmentCourse,
    EnrollmentPayment,
    SchoolCost,
    SchoolCourse,
    SchoolExamPlan,
    SchoolRegistrationFees,
    Student,
    StudentEnrollment,
    User,
)
from backend.app.schemas.school import (
    CourseCreate,
    CourseUpdate,
    DiscountCodeCreate,
    ExamPlanUpdate,
    EnrollmentPaymentCreate,
    PaymentStatusUpdate,
    RegistrationFeesUpdate,
    SchoolCostCreate,
    StudentEnrollmentCreate,
)
from backend.app.services.school_exam_catalog import DEFAULT_EXAM_CATALOG, PLAN_CODES, decimal


class SchoolError(ValueError):
    pass


class SchoolConflictError(SchoolError):
    pass


def workspace_id(actor: User) -> UUID:
    """Return the manager workspace shared by a manager and their employees."""
    return actor.school_manager_id or actor.id


class SchoolService:
    def __init__(self, session: Session, actor: User) -> None:
        self.session = session
        self.actor = actor
        self.workspace_owner_id = workspace_id(actor)

    def list_courses(self, grade: str | None = None) -> list[SchoolCourse]:
        query = select(SchoolCourse).where(
            SchoolCourse.workspace_owner_id == self.workspace_owner_id
        )
        if grade is not None:
            query = query.where(SchoolCourse.grade == grade)
        return list(self.session.scalars(query.order_by(SchoolCourse.grade, SchoolCourse.name)))

    def create_course(self, data: CourseCreate) -> SchoolCourse:
        course = SchoolCourse(workspace_owner_id=self.workspace_owner_id, **data.model_dump())
        self.session.add(course)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise SchoolConflictError(
                "A course with this name already exists for this grade"
            ) from exc
        return course

    def update_course(self, course_id: UUID, data: CourseUpdate) -> SchoolCourse:
        course = self.session.scalar(
            select(SchoolCourse).where(
                SchoolCourse.id == course_id,
                SchoolCourse.workspace_owner_id == self.workspace_owner_id,
            )
        )
        if course is None:
            raise SchoolError("Course was not found")

        for field, value in data.model_dump().items():
            setattr(course, field, value)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise SchoolConflictError(
                "A course with this name already exists for this grade"
            ) from exc
        return course

    def list_discounts(self) -> list[DiscountCode]:
        return list(
            self.session.scalars(
                select(DiscountCode)
                .where(DiscountCode.workspace_owner_id == self.workspace_owner_id)
                .order_by(DiscountCode.code)
            )
        )

    def create_discount(self, data: DiscountCodeCreate) -> DiscountCode:
        code = DiscountCode(workspace_owner_id=self.workspace_owner_id, **data.model_dump())
        self.session.add(code)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise SchoolConflictError("This discount code already exists") from exc
        return code

    def registration_fees(self) -> tuple[Decimal, Decimal]:
        fees = self.session.scalar(
            select(SchoolRegistrationFees).where(
                SchoolRegistrationFees.workspace_owner_id == self.workspace_owner_id
            )
        )
        if fees is None:
            return Decimal("0"), Decimal("0")
        return fees.book_price, fees.exam_price

    def update_registration_fees(self, data: RegistrationFeesUpdate) -> SchoolRegistrationFees:
        fees = self.session.scalar(
            select(SchoolRegistrationFees).where(
                SchoolRegistrationFees.workspace_owner_id == self.workspace_owner_id
            )
        )
        if fees is None:
            fees = SchoolRegistrationFees(workspace_owner_id=self.workspace_owner_id)
            self.session.add(fees)
        fees.book_price = data.book_price
        fees.exam_price = data.exam_price
        self.session.commit()
        return fees

    def list_exam_plans(self, grade: str | None = None) -> list[SchoolExamPlan]:
        self._ensure_default_exam_plans()
        query = select(SchoolExamPlan).where(
            SchoolExamPlan.workspace_owner_id == self.workspace_owner_id
        )
        if grade is not None:
            query = query.where(SchoolExamPlan.grade == grade)
        return list(
            self.session.scalars(
                query.order_by(
                    SchoolExamPlan.grade,
                    SchoolExamPlan.academic_track,
                    SchoolExamPlan.plan_code,
                )
            )
        )

    def update_exam_plan(self, plan_id: UUID, data: ExamPlanUpdate) -> SchoolExamPlan:
        plan = self.session.scalar(
            select(SchoolExamPlan).where(
                SchoolExamPlan.id == plan_id,
                SchoolExamPlan.workspace_owner_id == self.workspace_owner_id,
            )
        )
        if plan is None:
            raise SchoolError("Exam plan was not found")

        for field, value in data.model_dump().items():
            setattr(plan, field, value)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise SchoolConflictError(
                "An exam plan with this grade, major, and plan code already exists"
            ) from exc
        return plan

    def list_students(self) -> list[Student]:
        students = list(
            self.session.scalars(
                select(Student)
                .where(Student.workspace_owner_id == self.workspace_owner_id)
                .order_by(Student.full_name)
            )
        )
        for student in students:
            self._load_student_details(student)
        return students

    def list_costs(
        self, start_date: date | None = None, end_date: date | None = None
    ) -> list[SchoolCost]:
        query = select(SchoolCost).where(SchoolCost.workspace_owner_id == self.workspace_owner_id)
        if start_date is not None:
            query = query.where(SchoolCost.cost_date >= start_date)
        if end_date is not None:
            query = query.where(SchoolCost.cost_date <= end_date)
        return list(
            self.session.scalars(
                query.order_by(SchoolCost.cost_date.desc(), SchoolCost.created_at.desc())
            )
        )

    def create_cost(self, data: SchoolCostCreate) -> SchoolCost:
        values = data.model_dump()
        supplied_number = values.pop("factor_number")
        cost = SchoolCost(
            workspace_owner_id=self.workspace_owner_id,
            created_by_id=self.actor.id,
            factor_number=(supplied_number or f"COST-{date.today():%Y%m%d}-{uuid4().hex[:8].upper()}"),
            **values,
        )
        self.session.add(cost)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise SchoolConflictError("A cost factor with this number already exists") from exc
        return cost

    def get_student(self, student_id: UUID) -> Student:
        student = self.session.scalar(
            select(Student).where(
                Student.id == student_id, Student.workspace_owner_id == self.workspace_owner_id
            )
        )
        if student is None:
            raise SchoolError("Student was not found")
        self._load_student_details(student)
        return student

    def create_enrollment(self, data: StudentEnrollmentCreate) -> Student:
        course_ids = list(dict.fromkeys(data.course_ids))
        courses = (
            list(
                self.session.scalars(
                    select(SchoolCourse).where(
                        SchoolCourse.workspace_owner_id == self.workspace_owner_id,
                        SchoolCourse.id.in_(course_ids),
                        SchoolCourse.is_active.is_(True),
                    )
                )
            )
            if course_ids
            else []
        )
        if len(courses) != len(course_ids):
            raise SchoolError("One or more selected courses are unavailable")
        if any(course.grade != data.grade for course in courses):
            raise SchoolError("Every selected course must match the student's grade")

        discount = self._resolve_discount(data.discount_code)
        exam_plan = self._resolve_exam_plan(data)
        book_price = (
            exam_plan.book_voucher_amount - exam_plan.book_voucher_discount
            if data.book_voucher_eligible and exam_plan is not None
            else Decimal("0")
        )
        exam_price = (
            exam_plan.exam_total if data.exam_registered and exam_plan is not None else Decimal("0")
        )
        subtotal = sum((course.price for course in courses), Decimal("0")) + book_price + exam_price
        discount_amount = (
            (subtotal * discount.percentage / Decimal("100")).quantize(
                Decimal("0.01"), ROUND_HALF_UP
            )
            if discount is not None
            else Decimal("0")
        )
        total = subtotal - discount_amount
        paid_amount = sum(
            (item.amount for item in data.payments if item.method in {"CASH", "BANK_TRANSFER"}),
            Decimal("0"),
        )
        if paid_amount > total:
            raise SchoolError("Immediate payments cannot exceed the enrollment total")

        student = Student(
            workspace_owner_id=self.workspace_owner_id,
            created_by_id=self.actor.id,
            **data.model_dump(
                exclude={
                    "course_ids",
                    "discount_code",
                    "payments",
                    "registration_date",
                    "exam_plan_id",
                }
            ),
            registration_date=data.registration_date or date.today(),
        )
        self.session.add(student)
        self.session.flush()
        enrollment = StudentEnrollment(
            workspace_owner_id=self.workspace_owner_id,
            student_id=student.id,
            created_by_id=self.actor.id,
            discount_code_id=discount.id if discount else None,
            exam_plan_id=exam_plan.id if exam_plan else None,
            subtotal=subtotal,
            discount_amount=discount_amount,
            book_price=book_price,
            exam_price=exam_price,
            exam_plan_code=exam_plan.plan_code if exam_plan else None,
            book_voucher_discount=(
                exam_plan.book_voucher_discount
                if data.book_voucher_eligible and exam_plan is not None
                else Decimal("0")
            ),
            total_amount=total,
            amount_paid=paid_amount,
            balance_due=total - paid_amount,
            status=self._status(total, paid_amount, data.payments),
        )
        self.session.add(enrollment)
        self.session.flush()
        self.session.add_all(
            [
                EnrollmentCourse(
                    enrollment_id=enrollment.id,
                    course_id=course.id,
                    course_name=course.name,
                    price=course.price,
                )
                for course in courses
            ]
        )
        self.session.add_all(
            [
                EnrollmentPayment(
                    workspace_owner_id=self.workspace_owner_id,
                    enrollment_id=enrollment.id,
                    recorded_by_id=self.actor.id,
                    amount=item.amount,
                    method=item.method,
                    due_date=item.due_date,
                    tracking_code=item.tracking_code,
                    sayad_id=item.sayad_id,
                    status="PAID" if item.method in {"CASH", "BANK_TRANSFER"} else "PENDING",
                )
                for item in data.payments
            ]
        )
        if discount is not None:
            discount.uses_count += 1
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise SchoolConflictError("A student with this national ID already exists") from exc
        self._load_student_details(student)
        return student

    def _ensure_default_exam_plans(self) -> None:
        exists = self.session.scalar(
            select(SchoolExamPlan.id)
            .where(SchoolExamPlan.workspace_owner_id == self.workspace_owner_id)
            .limit(1)
        )
        if exists is not None:
            return
        plans: list[SchoolExamPlan] = []
        for grade, track, book_amount, book_discount, price_sets in DEFAULT_EXAM_CATALOG:
            for code, (count, unit_price, total) in zip(PLAN_CODES, price_sets, strict=True):
                plans.append(
                    SchoolExamPlan(
                        workspace_owner_id=self.workspace_owner_id,
                        grade=grade,
                        academic_track=track,
                        plan_code=code,
                        exam_count=count,
                        exam_unit_price=decimal(unit_price),
                        exam_total=decimal(total),
                        book_voucher_amount=decimal(book_amount),
                        book_voucher_discount=decimal(book_discount),
                    )
                )
        self.session.add_all(plans)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()

    def _resolve_exam_plan(self, data: StudentEnrollmentCreate) -> SchoolExamPlan | None:
        if not data.exam_registered and not data.book_voucher_eligible:
            return None
        if data.exam_plan_id is None:
            raise SchoolError("Select an exam plan before adding exams or books")
        self._ensure_default_exam_plans()
        plan = self.session.scalar(
            select(SchoolExamPlan).where(
                SchoolExamPlan.id == data.exam_plan_id,
                SchoolExamPlan.workspace_owner_id == self.workspace_owner_id,
                SchoolExamPlan.is_active.is_(True),
            )
        )
        if plan is None:
            raise SchoolError("The selected exam plan is unavailable")
        if plan.grade != data.grade or plan.academic_track != data.academic_track:
            raise SchoolError(
                "The selected exam plan does not match this student's grade and major"
            )
        return plan

    def update_payment_status(
        self, payment_id: UUID, data: PaymentStatusUpdate
    ) -> EnrollmentPayment:
        payment = self.session.scalar(
            select(EnrollmentPayment).where(
                EnrollmentPayment.id == payment_id,
                EnrollmentPayment.workspace_owner_id == self.workspace_owner_id,
            )
        )
        if payment is None:
            raise SchoolError("Payment was not found")
        if payment.status == "PAID":
            raise SchoolConflictError("A paid payment cannot be changed")
        payment.status = data.status
        enrollment = self.session.get(StudentEnrollment, payment.enrollment_id)
        assert enrollment is not None
        payments = list(
            self.session.scalars(
                select(EnrollmentPayment).where(EnrollmentPayment.enrollment_id == enrollment.id)
            )
        )
        paid = sum((row.amount for row in payments if row.status == "PAID"), Decimal("0"))
        if paid > enrollment.total_amount:
            raise SchoolError("Payments cannot exceed the enrollment total")
        enrollment.amount_paid = paid
        enrollment.balance_due = enrollment.total_amount - paid
        enrollment.status = self._status(enrollment.total_amount, paid, payments)
        self.session.commit()
        return payment

    def _resolve_discount(self, supplied_code: str | None) -> DiscountCode | None:
        if not supplied_code:
            return None
        code = self.session.scalar(
            select(DiscountCode).where(
                DiscountCode.workspace_owner_id == self.workspace_owner_id,
                DiscountCode.code == supplied_code.strip().upper(),
            )
        )
        if code is None or not code.is_active:
            raise SchoolError("The discount code is invalid or inactive")
        if code.expires_on is not None and code.expires_on < date.today():
            raise SchoolError("The discount code has expired")
        if code.max_uses is not None and code.uses_count >= code.max_uses:
            raise SchoolError("The discount code has reached its use limit")
        return code

    @staticmethod
    def _status(
        total: Decimal,
        paid: Decimal,
        payments: list[EnrollmentPaymentCreate] | list[EnrollmentPayment],
    ) -> str:
        if paid >= total:
            return "PAID"
        overdue = any(
            getattr(item, "status", "PENDING") == "PENDING"
            and item.due_date is not None
            and item.due_date < date.today()
            for item in payments
        )
        if overdue:
            return "OVERDUE"
        return "PARTIALLY_PAID" if paid > 0 else "UNPAID"

    def _load_student_details(self, student: Student) -> None:
        # Relationships are select-in loaded; this explicit read gives deterministic
        # newest-first enrolments for the API response.
        student.enrollments = list(
            self.session.scalars(
                select(StudentEnrollment)
                .where(StudentEnrollment.student_id == student.id)
                .order_by(StudentEnrollment.created_at.desc())
            )
        )
