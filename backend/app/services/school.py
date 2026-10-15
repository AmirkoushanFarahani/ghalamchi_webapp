from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

from sqlalchemy import select, true
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.passwords import hash_password
from backend.app.db.models import (
    DiscountCode,
    EnrollmentClassChange,
    EnrollmentCourse,
    EnrollmentPayment,
    EnrollmentServiceAttendance,
    EnrollmentServiceCancellation,
    EnrollmentSupportChange,
    ExamPricingPeriod,
    Role,
    SchoolCost,
    SchoolCourse,
    SchoolExamPlan,
    SchoolInstitute,
    SchoolRegistrationFees,
    SchoolSpecialSupport,
    Student,
    StudentEnrollment,
    User,
)
from backend.app.repositories.audit import AuditRepository
from backend.app.schemas.school import (
    AttendanceCreate,
    ClassChangeCreate,
    CourseCreate,
    CourseUpdate,
    DiscountCodeCreate,
    EnrollmentPaymentCreate,
    ExamPlanUpdate,
    ExamPricingPeriodCreate,
    PaymentStatusUpdate,
    RefundAction,
    RegistrationFeesUpdate,
    SchoolCostCreate,
    SchoolInstituteCreate,
    SchoolSecretaryAssign,
    SchoolSecretaryCreate,
    SchoolSecretaryPasswordReset,
    SchoolSecretaryUpdate,
    ServiceCancellationCreate,
    SpecialSupportUpdate,
    StudentEnrollmentCreate,
    SupportChangeCreate,
)
from backend.app.services.exam_pricing import install_exam_catalog


class SchoolError(ValueError):
    pass


class SchoolConflictError(SchoolError):
    pass


class SchoolAccessError(PermissionError):
    pass


def workspace_id(actor: User) -> UUID:
    """Return the manager workspace shared by a manager and their employees."""
    return actor.school_manager_id or actor.id


class SchoolService:
    def __init__(self, session: Session, actor: User) -> None:
        self.session = session
        self.actor = actor
        self.workspace_owner_id = workspace_id(actor)
        self.school_institute_id = self._resolve_school_institute_id()

    def _resolve_school_institute_id(self) -> UUID:
        if self.actor.school_manager_id is not None:
            manager = self.session.get(User, self.actor.school_manager_id)
            if manager is None or not manager.is_active:
                raise SchoolAccessError("دسترسی آموزشگاه غیرفعال است.")
            school = self.session.scalar(
                select(SchoolInstitute).where(
                    SchoolInstitute.id == self.actor.school_institute_id,
                    SchoolInstitute.manager_id == self.workspace_owner_id,
                    SchoolInstitute.is_active.is_(True),
                )
            )
            if school is None:
                raise SchoolAccessError("مدیر باید آموزشگاه فعال شما را مشخص کند.")
            return school.id
        if "EMPLOYEE" in self.actor.role_names:
            raise SchoolAccessError("حساب منشی باید توسط مدیر به آموزشگاه متصل شود.")
        selected = self.actor.school_institute_id or self.actor.active_school_institute_id
        if selected is not None:
            school = self.session.scalar(
                select(SchoolInstitute).where(
                    SchoolInstitute.id == selected,
                    SchoolInstitute.manager_id == self.workspace_owner_id,
                    SchoolInstitute.is_active.is_(True),
                )
            )
            if school is not None:
                return school.id
        school = self.session.scalar(
            select(SchoolInstitute)
            .where(
                SchoolInstitute.manager_id == self.workspace_owner_id,
                SchoolInstitute.is_active.is_(True),
            )
            .order_by(SchoolInstitute.created_at)
        )
        if school is None:
            raise SchoolAccessError(
                "آموزشگاه فعالی ندارید؛ دوباره وارد حساب شوید یا با مدیر تماس بگیرید."
            )
        return school.id

    def _require_manager(self) -> None:
        if self.actor.school_manager_id is not None:
            raise SchoolError("Only the manager can manage institutes")

    def list_institutes(self) -> list[SchoolInstitute]:
        if self.actor.school_manager_id is not None:
            school = self.session.get(SchoolInstitute, self.school_institute_id)
            return [school] if school is not None else []
        return list(
            self.session.scalars(
                select(SchoolInstitute)
                .where(SchoolInstitute.manager_id == self.workspace_owner_id)
                .order_by(SchoolInstitute.created_at)
            )
        )

    def create_institute(self, data: SchoolInstituteCreate) -> SchoolInstitute:
        self._require_manager()
        # The product limit is two, so materializing this small manager-owned list is clearer
        # than a database-specific counting query.
        count = len(self.list_institutes())
        if count >= 2:
            raise SchoolConflictError("A manager can manage at most two schools or institutes")
        school = SchoolInstitute(manager_id=self.workspace_owner_id, name=data.name)
        self.session.add(school)
        try:
            self.session.flush()
            install_exam_catalog(self.session, self.workspace_owner_id, school.id)
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise SchoolConflictError("An institute with this name already exists") from exc
        return school

    def rename_institute(self, school_id: UUID, data: SchoolInstituteCreate) -> SchoolInstitute:
        self._require_manager()
        school = self.session.scalar(
            select(SchoolInstitute).where(
                SchoolInstitute.id == school_id,
                SchoolInstitute.manager_id == self.workspace_owner_id,
            )
        )
        if school is None:
            raise SchoolError("School or institute was not found")
        school.name = data.name
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise SchoolConflictError("An institute with this name already exists") from exc
        return school

    def select_institute(self, school_id: UUID) -> SchoolInstitute:
        self._require_manager()
        school = self.session.scalar(
            select(SchoolInstitute).where(
                SchoolInstitute.id == school_id,
                SchoolInstitute.manager_id == self.workspace_owner_id,
                SchoolInstitute.is_active.is_(True),
            )
        )
        if school is None:
            raise SchoolError("School or institute was not found")
        self.actor.active_school_institute_id = school.id
        self.session.commit()
        self.school_institute_id = school.id
        return school

    def assign_secretary(self, school_id: UUID, data: SchoolSecretaryAssign) -> SchoolInstitute:
        self._require_manager()
        school = self.session.scalar(
            select(SchoolInstitute).where(
                SchoolInstitute.id == school_id,
                SchoolInstitute.manager_id == self.workspace_owner_id,
            )
        )
        secretary = self.session.scalar(
            select(User).where(
                User.id == data.secretary_id,
                User.school_manager_id == self.workspace_owner_id,
                User.is_active.is_(True),
            )
        )
        if school is None or secretary is None:
            raise SchoolError("School or secretary was not found in this manager workspace")
        secretary.school_institute_id = school.id
        secretary.session_version += 1
        self.session.commit()
        return school

    def create_secretary(self, school_id: UUID, data: SchoolSecretaryCreate) -> User:
        self._require_manager()
        school = self.session.scalar(
            select(SchoolInstitute).where(
                SchoolInstitute.id == school_id,
                SchoolInstitute.manager_id == self.workspace_owner_id,
            )
        )
        employee_role = self.session.scalar(select(Role).where(Role.name == "EMPLOYEE"))
        if school is None:
            raise SchoolError("School or institute was not found")
        if employee_role is None:
            raise SchoolError("Employee role has not been initialized")
        secretary = User(
            email=str(data.email).casefold(),
            password_hash=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            business_category="EDUCATION",
            school_manager_id=self.workspace_owner_id,
            school_institute_id=school.id,
            roles=[employee_role],
        )
        self.session.add(secretary)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise SchoolConflictError("An account with this email already exists") from exc
        return secretary

    def list_secretaries(self, school_id: UUID) -> list[User]:
        self._require_manager()
        if (
            self.session.scalar(
                select(SchoolInstitute.id).where(
                    SchoolInstitute.id == school_id,
                    SchoolInstitute.manager_id == self.workspace_owner_id,
                )
            )
            is None
        ):
            raise SchoolError("School or institute was not found")
        return list(
            self.session.scalars(
                select(User)
                .where(
                    User.school_manager_id == self.workspace_owner_id,
                    User.school_institute_id == school_id,
                    User.roles.any(Role.name == "EMPLOYEE"),
                )
                .order_by(User.created_at, User.id)
            )
        )

    def _managed_secretary(self, school_id: UUID, secretary_id: UUID) -> User:
        self._require_manager()
        school = self.session.scalar(
            select(SchoolInstitute.id).where(
                SchoolInstitute.id == school_id,
                SchoolInstitute.manager_id == self.workspace_owner_id,
            )
        )
        secretary = self.session.scalar(
            select(User)
            .where(
                User.id == secretary_id,
                User.school_manager_id == self.workspace_owner_id,
                User.school_institute_id == school_id,
                User.roles.any(Role.name == "EMPLOYEE"),
            )
            .with_for_update()
        )
        if school is None or secretary is None:
            raise SchoolError("School or secretary was not found in this manager workspace")
        return secretary

    def update_secretary(
        self, school_id: UUID, secretary_id: UUID, data: SchoolSecretaryUpdate
    ) -> User:
        secretary = self._managed_secretary(school_id, secretary_id)
        secretary.first_name = data.first_name
        secretary.last_name = data.last_name
        secretary.email = str(data.email).casefold()
        secretary.session_version += 1
        AuditRepository(self.session).record(
            action="school.secretary.updated",
            resource_type="user",
            resource_id=str(secretary.id),
            actor_id=self.actor.id,
            success=True,
            details={"school_institute_id": str(school_id)},
        )
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise SchoolConflictError("An account with this email already exists") from exc
        return secretary

    def set_secretary_status(self, school_id: UUID, secretary_id: UUID, is_active: bool) -> User:
        secretary = self._managed_secretary(school_id, secretary_id)
        secretary.is_active = is_active
        secretary.session_version += 1
        AuditRepository(self.session).record(
            action="school.secretary.status_changed",
            resource_type="user",
            resource_id=str(secretary.id),
            actor_id=self.actor.id,
            success=True,
            details={"school_institute_id": str(school_id), "is_active": is_active},
        )
        self.session.commit()
        return secretary

    def reset_secretary_password(
        self, school_id: UUID, secretary_id: UUID, data: SchoolSecretaryPasswordReset
    ) -> None:
        secretary = self._managed_secretary(school_id, secretary_id)
        secretary.password_hash = hash_password(data.password)
        secretary.session_version += 1
        AuditRepository(self.session).record(
            action="school.secretary.credentials_reset",
            resource_type="user",
            resource_id=str(secretary.id),
            actor_id=self.actor.id,
            success=True,
            details={"school_institute_id": str(school_id)},
        )
        self.session.commit()

    def comparison(self) -> list[dict[str, object]]:
        self._require_manager()
        today = date.today()
        result: list[dict[str, object]] = []
        for school in self.list_institutes():
            enrollments = list(
                self.session.scalars(
                    select(StudentEnrollment).where(
                        StudentEnrollment.workspace_owner_id == self.workspace_owner_id,
                        StudentEnrollment.school_institute_id == school.id,
                    )
                )
            )
            payments = list(
                self.session.scalars(
                    select(EnrollmentPayment).where(
                        EnrollmentPayment.workspace_owner_id == self.workspace_owner_id,
                        EnrollmentPayment.school_institute_id == school.id,
                    )
                )
            )
            costs = list(
                self.session.scalars(
                    select(SchoolCost).where(
                        SchoolCost.workspace_owner_id == self.workspace_owner_id,
                        SchoolCost.school_institute_id == school.id,
                    )
                )
            )
            registered = sum((row.total_amount for row in enrollments), Decimal("0"))
            received = sum((row.amount_paid for row in enrollments), Decimal("0"))
            outstanding = sum((row.balance_due for row in enrollments), Decimal("0"))
            due = sum(
                (
                    row.amount
                    for row in payments
                    if row.status == "PENDING"
                    and row.due_date is not None
                    and row.due_date <= today
                ),
                Decimal("0"),
            )
            result.append(
                {
                    "school_institute_id": school.id,
                    "school_name": school.name,
                    "student_count": sum(
                        1
                        for _ in self.session.scalars(
                            select(Student.id).where(Student.school_institute_id == school.id)
                        )
                    ),
                    "registered_tuition": registered,
                    "received_tuition": received,
                    "outstanding_tuition": outstanding,
                    "due_payments": due,
                    "costs": sum((row.amount for row in costs), Decimal("0")),
                    "net_cash": received - sum((row.amount for row in costs), Decimal("0")),
                }
            )
        return result

    def list_courses(
        self, grade: str | None = None, include_deleted: bool = False
    ) -> list[SchoolCourse]:
        query = select(SchoolCourse).where(
            SchoolCourse.workspace_owner_id == self.workspace_owner_id,
            SchoolCourse.school_institute_id == self.school_institute_id,
        )
        if grade is not None:
            query = query.where(SchoolCourse.grade == grade)
        if not include_deleted:
            query = query.where(SchoolCourse.is_deleted.is_(False))
        return list(self.session.scalars(query.order_by(SchoolCourse.grade, SchoolCourse.name)))

    def create_course(self, data: CourseCreate) -> SchoolCourse:
        course = SchoolCourse(
            workspace_owner_id=self.workspace_owner_id,
            school_institute_id=self.school_institute_id,
            **data.model_dump(),
        )
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
                SchoolCourse.school_institute_id == self.school_institute_id,
            )
        )
        if course is None or course.is_deleted:
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
                .where(
                    DiscountCode.workspace_owner_id == self.workspace_owner_id,
                    DiscountCode.school_institute_id == self.school_institute_id,
                )
                .order_by(DiscountCode.code)
            )
        )

    def create_discount(self, data: DiscountCodeCreate) -> DiscountCode:
        code = DiscountCode(
            workspace_owner_id=self.workspace_owner_id,
            school_institute_id=self.school_institute_id,
            **data.model_dump(),
        )
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
                SchoolRegistrationFees.workspace_owner_id == self.workspace_owner_id,
                SchoolRegistrationFees.school_institute_id == self.school_institute_id,
            )
        )
        if fees is None:
            return Decimal("0"), Decimal("0")
        return fees.book_price, fees.exam_price

    def update_registration_fees(self, data: RegistrationFeesUpdate) -> SchoolRegistrationFees:
        fees = self.session.scalar(
            select(SchoolRegistrationFees).where(
                SchoolRegistrationFees.workspace_owner_id == self.workspace_owner_id,
                SchoolRegistrationFees.school_institute_id == self.school_institute_id,
            )
        )
        if fees is None:
            fees = SchoolRegistrationFees(
                workspace_owner_id=self.workspace_owner_id,
                school_institute_id=self.school_institute_id,
            )
            self.session.add(fees)
        fees.book_price = data.book_price
        fees.exam_price = data.exam_price
        self.session.commit()
        return fees

    def list_exam_plans(
        self, grade: str | None = None, include_deleted: bool = False
    ) -> list[SchoolExamPlan]:
        query = select(SchoolExamPlan).where(
            SchoolExamPlan.workspace_owner_id == self.workspace_owner_id,
            SchoolExamPlan.school_institute_id == self.school_institute_id,
        )
        if grade is not None:
            query = query.where(SchoolExamPlan.grade == grade)
        if not include_deleted:
            query = query.where(SchoolExamPlan.is_deleted.is_(False))
        return list(
            self.session.scalars(
                query.order_by(
                    SchoolExamPlan.grade,
                    SchoolExamPlan.academic_track,
                    SchoolExamPlan.plan_code,
                    SchoolExamPlan.revision.desc(),
                )
            )
        )

    def list_exam_pricing_periods(self) -> list[ExamPricingPeriod]:
        return list(
            self.session.scalars(
                select(ExamPricingPeriod)
                .where(
                    ExamPricingPeriod.workspace_owner_id == self.workspace_owner_id,
                    ExamPricingPeriod.school_institute_id == self.school_institute_id,
                )
                .order_by(
                    ExamPricingPeriod.starts_on, ExamPricingPeriod.ends_on, ExamPricingPeriod.name
                )
            )
        )

    def create_exam_pricing_period(self, data: ExamPricingPeriodCreate) -> ExamPricingPeriod:
        self._require_manager()
        period = ExamPricingPeriod(
            workspace_owner_id=self.workspace_owner_id,
            school_institute_id=self.school_institute_id,
            **data.model_dump(),
        )
        self.session.add(period)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise SchoolConflictError(
                "یک بازه با این نام قبلاً در این آموزشگاه ثبت شده است."
            ) from exc
        return period

    def _lock_exam_catalog(self, data: ExamPlanUpdate) -> None:
        self._require_manager()
        self.session.scalar(
            select(SchoolInstitute)
            .where(
                SchoolInstitute.id == self.school_institute_id,
            )
            .with_for_update()
        )
        if data.pricing_period_id is not None:
            period = self.session.scalar(
                select(ExamPricingPeriod).where(
                    ExamPricingPeriod.id == data.pricing_period_id,
                    ExamPricingPeriod.school_institute_id == self.school_institute_id,
                    ExamPricingPeriod.workspace_owner_id == self.workspace_owner_id,
                )
            )
            if period is None:
                raise SchoolError("بازه قیمت انتخاب‌شده متعلق به این آموزشگاه نیست.")

    def _current_exam_plan(self, data: ExamPlanUpdate) -> SchoolExamPlan | None:
        return self.session.scalar(
            select(SchoolExamPlan).where(
                SchoolExamPlan.workspace_owner_id == self.workspace_owner_id,
                SchoolExamPlan.school_institute_id == self.school_institute_id,
                SchoolExamPlan.grade == data.grade,
                SchoolExamPlan.academic_track == data.academic_track,
                SchoolExamPlan.plan_code == data.plan_code,
                SchoolExamPlan.pricing_period_id == data.pricing_period_id,
                SchoolExamPlan.is_current.is_(True),
            )
        )

    def update_exam_plan(self, plan_id: UUID, data: ExamPlanUpdate) -> SchoolExamPlan:
        self._lock_exam_catalog(data)
        plan = self.session.scalar(
            select(SchoolExamPlan).where(
                SchoolExamPlan.id == plan_id,
                SchoolExamPlan.workspace_owner_id == self.workspace_owner_id,
                SchoolExamPlan.school_institute_id == self.school_institute_id,
            )
        )
        if plan is None or plan.is_deleted:
            raise SchoolError("Exam plan was not found")
        if "pricing_period_id" not in data.model_fields_set:
            data = data.model_copy(update={"pricing_period_id": plan.pricing_period_id})
        if not plan.is_current or (
            data.expected_revision is not None and plan.revision != data.expected_revision
        ):
            raise SchoolConflictError("قیمت قبلاً تغییر کرده است؛ صفحه را تازه‌سازی کنید.")
        # An existing price group has a stable identity. Another period/grade is
        # a new plan, so a price revision cannot move or erase its history.
        if (data.grade, data.academic_track, data.plan_code, data.pricing_period_id) != (
            plan.grade,
            plan.academic_track,
            plan.plan_code,
            plan.pricing_period_id,
        ):
            raise SchoolError(
                "برای تغییر پایه، کد یا بازه، از «طرح جدید از این قیمت» استفاده کنید."
            )
        plan.is_current = False
        replacement = SchoolExamPlan(
            workspace_owner_id=self.workspace_owner_id,
            school_institute_id=self.school_institute_id,
            revision=plan.revision + 1,
            **data.model_dump(exclude={"expected_revision"}),
        )
        self.session.add(replacement)
        AuditRepository(self.session).record(
            action="school.exam_price.revised",
            resource_type="school_exam_plan",
            resource_id=str(plan.id),
            actor_id=self.actor.id,
            success=True,
            details={
                "old_total": str(plan.exam_total),
                "new_total": str(data.exam_total),
                "revision": replacement.revision,
            },
        )
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise SchoolConflictError(
                "An exam plan with this grade, major, and plan code already exists"
            ) from exc
        return replacement

    def create_exam_plan(self, data: ExamPlanUpdate) -> SchoolExamPlan:
        self._lock_exam_catalog(data)
        if self._current_exam_plan(data) is not None:
            raise SchoolConflictError(
                "برای این پایه، رشته، کد و بازه قبلاً تعرفه ثبت شده است؛ آن را ویرایش کنید."
            )
        plan = SchoolExamPlan(
            workspace_owner_id=self.workspace_owner_id,
            school_institute_id=self.school_institute_id,
            **data.model_dump(exclude={"expected_revision"}),
        )
        self.session.add(plan)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise SchoolConflictError(
                "An exam plan with this grade, major, and plan code already exists"
            ) from exc
        return plan

    def restore_exam_plan(self, plan_id: UUID) -> SchoolExamPlan:
        self._require_manager()
        self.session.scalar(
            select(SchoolInstitute)
            .where(
                SchoolInstitute.id == self.school_institute_id,
            )
            .with_for_update()
        )
        old = self.session.scalar(
            select(SchoolExamPlan).where(
                SchoolExamPlan.id == plan_id,
                SchoolExamPlan.workspace_owner_id == self.workspace_owner_id,
                SchoolExamPlan.school_institute_id == self.school_institute_id,
            )
        )
        if old is None or old.is_deleted:
            raise SchoolError("تعرفه قبلی پیدا نشد.")
        data = ExamPlanUpdate(
            **{
                field: getattr(old, field)
                for field in ExamPlanUpdate.model_fields
                if field != "expected_revision"
            }
        ).model_copy(update={"is_active": True})
        current = self._current_exam_plan(data)
        if current is None:
            raise SchoolConflictError("نسخه فعلی این طرح پیدا نشد.")
        return self.update_exam_plan(current.id, data)

    def list_special_supports(self, include_deleted: bool = False) -> list[SchoolSpecialSupport]:
        return list(
            self.session.scalars(
                select(SchoolSpecialSupport)
                .where(
                    SchoolSpecialSupport.workspace_owner_id == self.workspace_owner_id,
                    SchoolSpecialSupport.school_institute_id == self.school_institute_id,
                    (SchoolSpecialSupport.is_deleted.is_(False) if not include_deleted else true()),
                )
                .order_by(SchoolSpecialSupport.name)
            )
        )

    def create_special_support(
        self, name: str, monthly_price: Decimal, seasonal_price: Decimal
    ) -> SchoolSpecialSupport:
        support = SchoolSpecialSupport(
            workspace_owner_id=self.workspace_owner_id,
            school_institute_id=self.school_institute_id,
            name=name,
            monthly_price=monthly_price,
            seasonal_price=seasonal_price,
        )
        self.session.add(support)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise SchoolConflictError("A special support with this name already exists") from exc
        return support

    def update_special_support(
        self, support_id: UUID, data: SpecialSupportUpdate
    ) -> SchoolSpecialSupport:
        support = self.session.scalar(
            select(SchoolSpecialSupport).where(
                SchoolSpecialSupport.id == support_id,
                SchoolSpecialSupport.workspace_owner_id == self.workspace_owner_id,
                SchoolSpecialSupport.school_institute_id == self.school_institute_id,
            )
        )
        if support is None or support.is_deleted:
            raise SchoolError("Special support was not found")
        for field, value in data.model_dump().items():
            setattr(support, field, value)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise SchoolConflictError("A special support with this name already exists") from exc
        return support

    def set_catalog_deleted(self, kind: str, item_id: UUID, deleted: bool) -> None:
        self._require_manager()
        # Serialize exam revisions and deletion against the same school lock.
        self.session.scalar(
            select(SchoolInstitute)
            .where(
                SchoolInstitute.id == self.school_institute_id,
            )
            .with_for_update()
        )
        models: dict[
            str, type[SchoolCourse] | type[SchoolSpecialSupport] | type[SchoolExamPlan]
        ] = {
            "courses": SchoolCourse,
            "special-supports": SchoolSpecialSupport,
            "exam-plans": SchoolExamPlan,
        }
        model = models[kind]
        item = self.session.scalar(
            select(model)
            .where(
                model.id == item_id,
                model.workspace_owner_id == self.workspace_owner_id,
                model.school_institute_id == self.school_institute_id,
            )
            .with_for_update()
        )
        if not isinstance(item, (SchoolCourse, SchoolSpecialSupport, SchoolExamPlan)):
            raise SchoolError("مورد انتخاب‌شده در این آموزشگاه پیدا نشد.")
        if isinstance(item, SchoolExamPlan):
            # Remove/restore a plan with its entire saved price history.
            versions = self.session.scalars(
                select(SchoolExamPlan).where(
                    SchoolExamPlan.workspace_owner_id == self.workspace_owner_id,
                    SchoolExamPlan.school_institute_id == self.school_institute_id,
                    SchoolExamPlan.pricing_period_id == item.pricing_period_id,
                    SchoolExamPlan.grade == item.grade,
                    SchoolExamPlan.academic_track == item.academic_track,
                    SchoolExamPlan.plan_code == item.plan_code,
                )
            )
            for version in versions:
                version.is_deleted = deleted
        else:
            item.is_deleted = deleted
        AuditRepository(self.session).record(
            action="school.catalog.deleted" if deleted else "school.catalog.restored",
            resource_type=model.__tablename__,
            resource_id=str(item.id),
            actor_id=self.actor.id,
            success=True,
            details={"kind": kind},
        )
        self.session.commit()

    def list_students(self) -> list[Student]:
        students = list(
            self.session.scalars(
                select(Student)
                .where(
                    Student.workspace_owner_id == self.workspace_owner_id,
                    Student.school_institute_id == self.school_institute_id,
                )
                .order_by(Student.full_name)
            )
        )
        for student in students:
            self._load_student_details(student)
        return students

    def list_costs(
        self, start_date: date | None = None, end_date: date | None = None
    ) -> list[SchoolCost]:
        query = select(SchoolCost).where(
            SchoolCost.workspace_owner_id == self.workspace_owner_id,
            SchoolCost.school_institute_id == self.school_institute_id,
        )
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
            school_institute_id=self.school_institute_id,
            created_by_id=self.actor.id,
            factor_number=(
                supplied_number or f"COST-{date.today():%Y%m%d}-{uuid4().hex[:8].upper()}"
            ),
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
                Student.id == student_id,
                Student.workspace_owner_id == self.workspace_owner_id,
                Student.school_institute_id == self.school_institute_id,
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
                        SchoolCourse.school_institute_id == self.school_institute_id,
                        SchoolCourse.id.in_(course_ids),
                        SchoolCourse.is_active.is_(True),
                        SchoolCourse.is_deleted.is_(False),
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
        special_support, special_support_name, special_support_period, special_support_price = (
            self._resolve_special_support(data)
        )
        book_price = (
            exam_plan.book_voucher_amount - exam_plan.book_voucher_discount
            if data.book_voucher_eligible and exam_plan is not None
            else Decimal("0")
        )
        exam_price = (
            exam_plan.exam_total if data.exam_registered and exam_plan is not None else Decimal("0")
        )
        subtotal = (
            sum((course.price for course in courses), Decimal("0"))
            + book_price
            + exam_price
            + special_support_price
        )
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
            school_institute_id=self.school_institute_id,
            created_by_id=self.actor.id,
            **data.model_dump(
                exclude={
                    "course_ids",
                    "discount_code",
                    "payments",
                    "registration_date",
                    "exam_plan_id",
                    "special_support",
                }
            ),
            registration_date=data.registration_date or date.today(),
        )
        self.session.add(student)
        self.session.flush()
        enrollment = StudentEnrollment(
            workspace_owner_id=self.workspace_owner_id,
            school_institute_id=self.school_institute_id,
            student_id=student.id,
            created_by_id=self.actor.id,
            discount_code_id=discount.id if discount else None,
            exam_plan_id=exam_plan.id if exam_plan else None,
            subtotal=subtotal,
            discount_amount=discount_amount,
            book_price=book_price,
            exam_price=exam_price,
            exam_plan_code=exam_plan.plan_code if exam_plan else None,
            exam_session_count=exam_plan.exam_count if exam_plan and data.exam_registered else 0,
            special_support_name=special_support_name,
            special_support_period=special_support_period,
            special_support_price=special_support_price,
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
                    instructor_name=course.instructor_name,
                    price=course.price,
                    session_count=course.session_count,
                )
                for course in courses
            ]
        )
        self.session.add_all(
            [
                EnrollmentPayment(
                    workspace_owner_id=self.workspace_owner_id,
                    school_institute_id=self.school_institute_id,
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
            .where(
                SchoolExamPlan.workspace_owner_id == self.workspace_owner_id,
                SchoolExamPlan.school_institute_id == self.school_institute_id,
            )
            .limit(1)
        )
        if exists is not None:
            return
        try:
            install_exam_catalog(self.session, self.workspace_owner_id, self.school_institute_id)
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
                SchoolExamPlan.school_institute_id == self.school_institute_id,
                SchoolExamPlan.is_active.is_(True),
                SchoolExamPlan.is_current.is_(True),
                SchoolExamPlan.is_deleted.is_(False),
            )
        )
        if plan is None:
            raise SchoolError("The selected exam plan is unavailable")
        if plan.grade != data.grade or plan.academic_track != data.academic_track:
            raise SchoolError(
                "The selected exam plan does not match this student's grade and major"
            )
        return plan

    def _resolve_special_support(
        self, data: StudentEnrollmentCreate
    ) -> tuple[SchoolSpecialSupport | None, str | None, str | None, Decimal]:
        if data.special_support is None:
            return None, None, None, Decimal("0")
        support = self.session.scalar(
            select(SchoolSpecialSupport).where(
                SchoolSpecialSupport.id == data.special_support.support_id,
                SchoolSpecialSupport.workspace_owner_id == self.workspace_owner_id,
                SchoolSpecialSupport.school_institute_id == self.school_institute_id,
                SchoolSpecialSupport.is_active.is_(True),
                SchoolSpecialSupport.is_deleted.is_(False),
            )
        )
        if support is None:
            raise SchoolError("The selected special support is unavailable")
        price = (
            support.seasonal_price
            if data.special_support.period == "SEASONAL"
            else support.monthly_price
        )
        return support, support.name, data.special_support.period, price

    def _locked_enrollment(self, student_id: UUID, enrollment_id: UUID) -> StudentEnrollment:
        enrollment = self.session.scalar(
            select(StudentEnrollment)
            .where(
                StudentEnrollment.id == enrollment_id,
                StudentEnrollment.student_id == student_id,
                StudentEnrollment.workspace_owner_id == self.workspace_owner_id,
                StudentEnrollment.school_institute_id == self.school_institute_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if enrollment is None:
            raise SchoolError("پرونده ثبت‌نام در این آموزشگاه پیدا نشد.")
        return enrollment

    def _refresh_balance(self, enrollment: StudentEnrollment) -> None:
        paid = sum(
            (row.amount for row in enrollment.payments if row.status == "PAID"), Decimal("0")
        )
        refunded = sum(
            (row.refund_amount for row in enrollment.class_changes if row.refund_status == "PAID"),
            Decimal("0"),
        )
        refunded += sum(
            (
                row.refund_amount
                for row in enrollment.service_cancellations
                if row.refund_status == "PAID"
            ),
            Decimal("0"),
        )
        enrollment.amount_paid = paid - refunded
        enrollment.balance_due = max(enrollment.total_amount - enrollment.amount_paid, Decimal("0"))
        enrollment.status = self._status(
            enrollment.total_amount, enrollment.amount_paid, enrollment.payments
        )

    def _append_payment(self, enrollment: StudentEnrollment, data: EnrollmentPaymentCreate) -> None:
        if data.amount > enrollment.balance_due:
            raise SchoolError("مبلغ پرداخت نمی‌تواند بیشتر از مانده شهریه باشد.")
        pending = sum(
            (p.amount for p in enrollment.payments if p.status == "PENDING"), Decimal("0")
        )
        if pending + data.amount > enrollment.balance_due:
            raise SchoolError(
                "برای این مانده قبلاً چک یا قسط ثبت شده است؛ ابتدا پرداخت جایگزین‌شده را لغو کنید."
            )
        enrollment.payments.append(
            EnrollmentPayment(
                workspace_owner_id=self.workspace_owner_id,
                school_institute_id=self.school_institute_id,
                recorded_by_id=self.actor.id,
                **data.model_dump(),
                status="PAID" if data.method in {"CASH", "BANK_TRANSFER"} else "PENDING",
            )
        )
        self._refresh_balance(enrollment)

    def change_class(
        self,
        student_id: UUID,
        enrollment_id: UUID,
        course_id: UUID,
        data: ClassChangeCreate,
    ) -> Student:
        enrollment = self._locked_enrollment(student_id, enrollment_id)
        if any(change.refund_status == "PENDING" for change in enrollment.class_changes) or any(
            cancellation.refund_status == "PENDING"
            for cancellation in enrollment.service_cancellations
        ):
            raise SchoolConflictError("ابتدا مدیر باید درخواست بازپرداخت قبلی را تعیین تکلیف کند.")
        old = next(
            (
                row
                for row in enrollment.courses
                if row.course_id == course_id and row.status == "ACTIVE"
            ),
            None,
        )
        target = self.session.scalar(
            select(SchoolCourse)
            .where(
                SchoolCourse.id == data.new_course_id,
                SchoolCourse.workspace_owner_id == self.workspace_owner_id,
                SchoolCourse.school_institute_id == self.school_institute_id,
                SchoolCourse.is_active.is_(True),
                SchoolCourse.is_deleted.is_(False),
            )
            .with_for_update()
        )
        if old is None or target is None:
            raise SchoolError("کلاس ثبت‌شده یا کلاس جایگزین در این آموزشگاه در دسترس نیست.")
        if target.grade != enrollment.student.grade:
            raise SchoolError("کلاس جایگزین باید مربوط به همان پایه دانش‌آموز باشد.")
        if any(row.course_id == target.id and row.status == "ACTIVE" for row in enrollment.courses):
            raise SchoolConflictError("این کلاس قبلاً در همین پرونده ثبت شده است.")
        if (
            old.price != data.expected_old_price
            or target.price != data.expected_new_price
            or enrollment.total_amount != data.expected_total
        ):
            raise SchoolConflictError(
                "قیمت یا پرونده تغییر کرده است؛ صفحه را تازه‌سازی و دوباره بررسی کنید."
            )
        subtotal = enrollment.subtotal - old.price + target.price
        # Preserve the negotiated discount amount; never re-read an edited/expired code.
        discount = min(enrollment.discount_amount, subtotal)
        new_total = subtotal - discount
        additional_due = max(
            new_total - max(enrollment.total_amount, enrollment.amount_paid), Decimal("0")
        )
        if data.payment is not None and data.payment.amount != additional_due:
            raise SchoolError("پرداخت تغییر کلاس باید دقیقاً برابر مابه‌التفاوت قابل پرداخت باشد.")
        change = EnrollmentClassChange(
            enrollment_id=enrollment.id,
            changed_by_id=self.actor.id,
            old_course_id=old.course_id,
            new_course_id=target.id,
            old_course_name=old.course_name,
            new_course_name=target.name,
            old_instructor_name=old.instructor_name,
            new_instructor_name=target.instructor_name,
            old_price=old.price,
            new_price=target.price,
            old_total=enrollment.total_amount,
            new_total=new_total,
            reason=data.reason,
            excess_handling=data.excess_handling,
            refund_amount=Decimal("0"),
            refund_status="NONE",
        )
        old.course_id, old.course_name, old.instructor_name, old.price = (
            target.id,
            target.name,
            target.instructor_name,
            target.price,
        )
        old.session_count = target.session_count
        enrollment.subtotal, enrollment.discount_amount, enrollment.total_amount = (
            subtotal,
            discount,
            new_total,
        )
        enrollment.class_changes.append(change)
        self._refresh_balance(enrollment)
        if data.payment is not None:
            self._append_payment(enrollment, data.payment)
        if data.excess_handling == "REFUND" and enrollment.credit_balance > 0:
            change.refund_amount = enrollment.credit_balance
            change.refund_status = "PENDING"
        AuditRepository(self.session).record(
            action="school.class.changed",
            resource_type="student_enrollment",
            resource_id=str(enrollment.id),
            actor_id=self.actor.id,
            success=True,
            details={
                "old_class": str(course_id),
                "new_class": str(target.id),
                "old_total": str(change.old_total),
                "new_total": str(new_total),
            },
        )
        self.session.commit()
        return self.get_student(student_id)

    def record_attendance(
        self, student_id: UUID, enrollment_id: UUID, data: AttendanceCreate
    ) -> Student:
        enrollment = self._locked_enrollment(student_id, enrollment_id)
        if data.service_type == "COURSE":
            if data.course_id is None:
                raise SchoolError("کلاس را انتخاب کنید.")
            course = next(
                (
                    row
                    for row in enrollment.courses
                    if row.course_id == data.course_id and row.status == "ACTIVE"
                ),
                None,
            )
            if course is None:
                raise SchoolError("کلاس فعال این دانش‌آموز پیدا نشد.")
            total_sessions, service_key = course.session_count, f"course:{course.course_id}"
        else:
            if not enrollment.exam_price or enrollment.exam_session_count <= 0:
                raise SchoolError("برای این پرونده آزمونِ دارای تعداد جلسه ثبت نشده است.")
            total_sessions, service_key = enrollment.exam_session_count, "exam"
        if data.session_number > total_sessions:
            raise SchoolError("شماره جلسه از تعداد جلسات ثبت‌شده بیشتر است.")
        duplicate = self.session.scalar(
            select(EnrollmentServiceAttendance.id).where(
                EnrollmentServiceAttendance.enrollment_id == enrollment.id,
                EnrollmentServiceAttendance.service_key == service_key,
                EnrollmentServiceAttendance.session_number == data.session_number,
            )
        )
        if duplicate is not None:
            raise SchoolConflictError("حضور این جلسه قبلاً ثبت شده است.")
        enrollment.attendance_records.append(
            EnrollmentServiceAttendance(
                course_id=data.course_id,
                recorded_by_id=self.actor.id,
                service_type=data.service_type,
                service_key=service_key,
                session_number=data.session_number,
                attended_on=data.attended_on,
                notes=data.notes,
            )
        )
        AuditRepository(self.session).record(
            action="school.attendance.recorded",
            resource_type="student_enrollment",
            resource_id=str(enrollment.id),
            actor_id=self.actor.id,
            success=True,
            details={"service": service_key, "session_number": data.session_number},
        )
        self.session.commit()
        return self.get_student(student_id)

    def cancel_service(
        self, student_id: UUID, enrollment_id: UUID, data: ServiceCancellationCreate
    ) -> Student:
        """Cancel one service while retaining an immutable financial/audit record."""
        enrollment = self._locked_enrollment(student_id, enrollment_id)
        if any(change.refund_status == "PENDING" for change in enrollment.class_changes) or any(
            row.refund_status == "PENDING" for row in enrollment.service_cancellations
        ):
            raise SchoolConflictError("ابتدا مدیر باید درخواست بازپرداخت قبلی را تعیین تکلیف کند.")
        service_key: str
        service_name: str
        original_price: Decimal
        total_sessions = 0
        if data.service_type == "COURSE":
            if data.course_id is None:
                raise SchoolError("کلاس را انتخاب کنید.")
            course = next(
                (
                    row
                    for row in enrollment.courses
                    if row.course_id == data.course_id and row.status == "ACTIVE"
                ),
                None,
            )
            if course is None:
                raise SchoolError("کلاس فعال برای لغو پیدا نشد.")
            if course.session_count <= 0:
                raise SchoolError("مدیر باید ابتدا تعداد جلسات این کلاس را در بخش کلاس‌ها ثبت کند.")
            service_key, service_name, original_price = (
                f"course:{course.course_id}",
                course.course_name,
                course.price,
            )
            total_sessions = course.session_count
        elif data.service_type == "EXAM":
            if enrollment.exam_price <= 0 or enrollment.exam_session_count <= 0:
                raise SchoolError("طرح آزمون فعال با تعداد آزمون مشخص برای لغو وجود ندارد.")
            service_key = "exam"
            service_name = f"طرح آزمون {enrollment.exam_plan_code or ''}".strip()
            original_price, total_sessions = enrollment.exam_price, enrollment.exam_session_count
        elif data.service_type == "BOOK":
            if enrollment.book_price <= 0:
                raise SchoolError("بن کتاب فعالی برای لغو وجود ندارد.")
            service_key, service_name, original_price = "book", "بن کتاب", enrollment.book_price
        else:
            if enrollment.special_support_price <= 0:
                raise SchoolError("پشتیبان ویژه فعالی برای لغو وجود ندارد.")
            service_key = "support"
            service_name = enrollment.special_support_name or "پشتیبان ویژه"
            original_price = enrollment.special_support_price
        if (
            original_price != data.expected_original_price
            or enrollment.total_amount != data.expected_total
        ):
            raise SchoolConflictError("مبلغ خدمت یا فاکتور تغییر کرده است؛ صفحه را تازه‌سازی کنید.")
        if any(row.service_key == service_key for row in enrollment.service_cancellations):
            raise SchoolConflictError("این خدمت قبلاً لغو شده است.")
        if data.service_type in {"BOOK", "SUPPORT"} and data.attended_sessions != 0:
            raise SchoolError("برای بن کتاب یا پشتیبان ویژه، تعداد جلسه باید صفر باشد.")
        attended = data.attended_sessions
        if attended > total_sessions:
            raise SchoolError("تعداد جلسات شرکت‌کرده نمی‌تواند از کل جلسات بیشتر باشد.")
        attendance_charge = (
            (original_price * Decimal(attended) / Decimal(total_sessions)).quantize(
                Decimal("0.01"), ROUND_HALF_UP
            )
            if total_sessions
            else Decimal("0")
        )
        cancellation_fee = (original_price * Decimal("0.10")).quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )
        retained = min(original_price, attendance_charge + cancellation_fee)
        old_total, prior_credit = enrollment.total_amount, enrollment.credit_balance
        subtotal = enrollment.subtotal - original_price + retained
        discount = min(enrollment.discount_amount, subtotal)
        new_total = subtotal - discount
        cancellation = EnrollmentServiceCancellation(
            enrollment_id=enrollment.id,
            requested_by_id=self.actor.id,
            course_id=data.course_id,
            service_type=data.service_type,
            service_key=service_key,
            service_name=service_name,
            original_price=original_price,
            total_sessions=total_sessions,
            attended_sessions=attended,
            attendance_charge=attendance_charge,
            cancellation_fee=cancellation_fee,
            retained_amount=retained,
            old_total=old_total,
            new_total=new_total,
            reason=data.reason,
            excess_handling=data.excess_handling,
            refund_amount=Decimal("0"),
            refund_status="NONE",
        )
        enrollment.subtotal, enrollment.discount_amount, enrollment.total_amount = (
            subtotal,
            discount,
            new_total,
        )
        if data.service_type == "COURSE":
            if data.course_id is None:
                raise SchoolError("کلاس را انتخاب کنید.")
            next(
                row for row in enrollment.courses if row.course_id == data.course_id
            ).status = "CANCELLED"
        elif data.service_type == "EXAM":
            enrollment.exam_price, enrollment.exam_session_count = Decimal("0"), 0
        elif data.service_type == "BOOK":
            enrollment.book_price = Decimal("0")
        else:
            enrollment.special_support_name = None
            enrollment.special_support_period = None
            enrollment.special_support_price = Decimal("0")
        enrollment.service_cancellations.append(cancellation)
        self._refresh_balance(enrollment)
        cancellation.refund_amount = min(
            max(enrollment.credit_balance - prior_credit, Decimal("0")),
            max(old_total - new_total, Decimal("0")),
        )
        if data.excess_handling == "REFUND" and cancellation.refund_amount > 0:
            cancellation.refund_status = "PENDING"
        AuditRepository(self.session).record(
            action="school.service.cancelled",
            resource_type="student_enrollment",
            resource_id=str(enrollment.id),
            actor_id=self.actor.id,
            success=True,
            details={
                "service": service_key,
                "attended": attended,
                "retained": str(retained),
                "refund": str(cancellation.refund_amount),
            },
        )
        self.session.commit()
        return self.get_student(student_id)

    def add_payment(
        self, student_id: UUID, enrollment_id: UUID, data: EnrollmentPaymentCreate
    ) -> Student:
        enrollment = self._locked_enrollment(student_id, enrollment_id)
        self._append_payment(enrollment, data)
        AuditRepository(self.session).record(
            action="school.payment.added",
            resource_type="student_enrollment",
            resource_id=str(enrollment.id),
            actor_id=self.actor.id,
            success=True,
            details={"amount": str(data.amount), "method": data.method},
        )
        self.session.commit()
        return self.get_student(student_id)

    def change_special_support(
        self, student_id: UUID, enrollment_id: UUID, data: SupportChangeCreate
    ) -> Student:
        enrollment = self._locked_enrollment(student_id, enrollment_id)
        if any(change.refund_status == "PENDING" for change in enrollment.class_changes) or any(
            row.refund_status == "PENDING" for row in enrollment.service_cancellations
        ):
            raise SchoolConflictError("ابتدا مدیر باید درخواست بازپرداخت قبلی را تعیین تکلیف کند.")
        support = self.session.scalar(
            select(SchoolSpecialSupport)
            .where(
                SchoolSpecialSupport.id == data.support_id,
                SchoolSpecialSupport.workspace_owner_id == self.workspace_owner_id,
                SchoolSpecialSupport.school_institute_id == self.school_institute_id,
                SchoolSpecialSupport.is_active.is_(True),
                SchoolSpecialSupport.is_deleted.is_(False),
            )
            .with_for_update()
        )
        if support is None:
            raise SchoolError("پشتیبان ویژه انتخاب‌شده فعال یا در دسترس نیست.")
        old_price = enrollment.special_support_price
        if old_price != data.expected_old_price or enrollment.total_amount != data.expected_total:
            raise SchoolConflictError(
                "قیمت پشتیبان یا فاکتور تغییر کرده است؛ صفحه را تازه‌سازی کنید."
            )
        new_price = support.seasonal_price if data.period == "SEASONAL" else support.monthly_price
        old_total = enrollment.total_amount
        subtotal = enrollment.subtotal - old_price + new_price
        discount = min(enrollment.discount_amount, subtotal)
        new_total = subtotal - discount
        change = EnrollmentSupportChange(
            enrollment_id=enrollment.id,
            changed_by_id=self.actor.id,
            old_name=enrollment.special_support_name,
            old_period=enrollment.special_support_period,
            old_price=old_price,
            new_name=support.name,
            new_period=data.period,
            new_price=new_price,
            old_total=old_total,
            new_total=new_total,
            reason=data.reason,
        )
        enrollment.subtotal = subtotal
        enrollment.discount_amount = discount
        enrollment.total_amount = new_total
        enrollment.special_support_name = support.name
        enrollment.special_support_period = data.period
        enrollment.special_support_price = new_price
        enrollment.support_changes.append(change)
        self._refresh_balance(enrollment)
        AuditRepository(self.session).record(
            action="school.support.changed",
            resource_type="student_enrollment",
            resource_id=str(enrollment.id),
            actor_id=self.actor.id,
            success=True,
            details={
                "old_price": str(old_price),
                "new_price": str(new_price),
                "old_total": str(old_total),
                "new_total": str(new_total),
            },
        )
        self.session.commit()
        return self.get_student(student_id)

    def process_service_cancellation_refund(
        self, student_id: UUID, enrollment_id: UUID, cancellation_id: UUID, data: RefundAction
    ) -> Student:
        self._require_manager()
        enrollment = self._locked_enrollment(student_id, enrollment_id)
        cancellation = next(
            (row for row in enrollment.service_cancellations if row.id == cancellation_id), None
        )
        if cancellation is None or cancellation.refund_status != "PENDING":
            raise SchoolConflictError(
                "درخواست بازپرداخت در انتظار تأیید پیدا نشد یا قبلاً انجام شده است."
            )
        if data.action == "KEEP_CREDIT":
            cancellation.refund_status = "CANCELLED"
        else:
            if cancellation.refund_amount > enrollment.credit_balance:
                raise SchoolConflictError("اعتبار فعلی برای بازپرداخت کافی نیست.")
            if data.paid_on is None or data.paid_on > date.today():
                raise SchoolError("تاریخ بازپرداخت انجام‌شده نمی‌تواند در آینده باشد.")
            cancellation.refund_status, cancellation.refund_method = "PAID", data.method
            cancellation.refunded_on, cancellation.refund_tracking_code = (
                data.paid_on,
                data.tracking_code,
            )
            cancellation.refunded_by_id = self.actor.id
        self._refresh_balance(enrollment)
        AuditRepository(self.session).record(
            action="school.service_cancellation_refund.updated",
            resource_type="student_enrollment",
            resource_id=str(enrollment.id),
            actor_id=self.actor.id,
            success=True,
            details={
                "cancellation_id": str(cancellation.id),
                "action": data.action,
                "amount": str(cancellation.refund_amount),
            },
        )
        self.session.commit()
        return self.get_student(student_id)

    def process_refund(
        self, student_id: UUID, enrollment_id: UUID, change_id: UUID, data: RefundAction
    ) -> Student:
        self._require_manager()
        enrollment = self._locked_enrollment(student_id, enrollment_id)
        change = next((row for row in enrollment.class_changes if row.id == change_id), None)
        if change is None or change.refund_status != "PENDING":
            raise SchoolConflictError(
                "درخواست بازپرداخت در انتظار تأیید پیدا نشد یا قبلاً انجام شده است."
            )
        if data.action == "KEEP_CREDIT":
            change.refund_status = "CANCELLED"
        else:
            if change.refund_amount > enrollment.credit_balance:
                raise SchoolConflictError(
                    "اعتبار فعلی برای بازپرداخت کافی نیست؛ پرونده را دوباره بررسی کنید."
                )
            if data.paid_on is None or data.paid_on > date.today():
                raise SchoolError("تاریخ بازپرداخت انجام‌شده نمی‌تواند در آینده باشد.")
            change.refund_status, change.refund_method = "PAID", data.method
            change.refunded_on, change.refund_tracking_code = data.paid_on, data.tracking_code
            change.refunded_by_id = self.actor.id
        self._refresh_balance(enrollment)
        AuditRepository(self.session).record(
            action="school.refund.updated",
            resource_type="student_enrollment",
            resource_id=str(enrollment.id),
            actor_id=self.actor.id,
            success=True,
            details={
                "change_id": str(change.id),
                "action": data.action,
                "amount": str(change.refund_amount),
            },
        )
        self.session.commit()
        return self.get_student(student_id)

    def update_payment_status(
        self, payment_id: UUID, data: PaymentStatusUpdate
    ) -> EnrollmentPayment:
        payment = self.session.scalar(
            select(EnrollmentPayment).where(
                EnrollmentPayment.id == payment_id,
                EnrollmentPayment.workspace_owner_id == self.workspace_owner_id,
                EnrollmentPayment.school_institute_id == self.school_institute_id,
            )
        )
        if payment is None:
            raise SchoolError("Payment was not found")
        student_id = self.session.scalar(
            select(StudentEnrollment.student_id).where(
                StudentEnrollment.id == payment.enrollment_id
            )
        )
        if student_id is None:
            raise SchoolError("Student was not found")
        enrollment = self._locked_enrollment(student_id, payment.enrollment_id)
        # Read again after the enrollment lock; class changes and all payments share this lock.
        payment = next(row for row in enrollment.payments if row.id == payment_id)
        if payment.status in {"PAID", "CANCELLED"}:
            raise SchoolConflictError("پرداخت وصول‌شده یا لغوشده قابل تغییر نیست.")
        if data.status == "PAID" and payment.amount > enrollment.balance_due:
            raise SchoolConflictError(
                "مبلغ این پرداخت بیشتر از مانده است؛ برنامه پرداخت را اصلاح کنید."
            )
        payment.status = data.status
        self._refresh_balance(enrollment)
        AuditRepository(self.session).record(
            action="school.payment.status_changed",
            resource_type="enrollment_payment",
            resource_id=str(payment.id),
            actor_id=self.actor.id,
            success=True,
            details={"status": data.status},
        )
        self.session.commit()
        return payment

    def _resolve_discount(self, supplied_code: str | None) -> DiscountCode | None:
        if not supplied_code:
            return None
        code = self.session.scalar(
            select(DiscountCode).where(
                DiscountCode.workspace_owner_id == self.workspace_owner_id,
                DiscountCode.school_institute_id == self.school_institute_id,
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
