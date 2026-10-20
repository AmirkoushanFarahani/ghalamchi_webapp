from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

GRADE_CHECK = (
    "grade IN ('GRADE_1','GRADE_2','GRADE_3','GRADE_4','GRADE_5','GRADE_6',"
    "'GRADE_7','GRADE_8','GRADE_9','GRADE_10','GRADE_11','GRADE_12')"
)


class SchoolInstitute(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "school_institutes"
    __table_args__ = (
        UniqueConstraint("manager_id", "name", name="uq_school_institute_manager_name"),
    )

    manager_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class SchoolAcademicYear(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "school_academic_years"
    __table_args__ = (
        UniqueConstraint("school_institute_id", "name", name="uq_academic_year_school_name"),
        CheckConstraint("starts_on <= ends_on", name="valid_academic_year_dates"),
    )
    workspace_owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    school_institute_id: Mapped[UUID] = mapped_column(
        ForeignKey("school_institutes.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(9))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)


class SchoolCourse(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "school_courses"
    __table_args__ = (
        UniqueConstraint(
            "workspace_owner_id",
            "school_institute_id",
            "academic_year",
            "name",
            "grade",
            name="uq_school_course_workspace_name_grade",
        ),
        CheckConstraint(GRADE_CHECK, name="valid_school_course_grade"),
        CheckConstraint("price >= 0", name="nonnegative_school_course_price"),
        CheckConstraint("session_count >= 0", name="nonnegative_school_course_session_count"),
    )

    workspace_owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    school_institute_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("school_institutes.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    academic_year: Mapped[str] = mapped_column(
        String(9), default="1405/1406", server_default="1405/1406", index=True
    )
    instructor_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    grade: Mapped[str] = mapped_column(String(20), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    session_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class DiscountCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "school_discount_codes"
    __table_args__ = (
        UniqueConstraint(
            "workspace_owner_id",
            "school_institute_id",
            "code",
            name="uq_school_discount_workspace_code",
        ),
        CheckConstraint(
            "percentage > 0 AND percentage <= 100", name="valid_school_discount_percentage"
        ),
        CheckConstraint("max_uses IS NULL OR max_uses > 0", name="valid_school_discount_max_uses"),
    )

    workspace_owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    school_institute_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("school_institutes.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(50))
    percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uses_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class SchoolRegistrationFees(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Manager-controlled prices for optional registration services."""

    __tablename__ = "school_registration_fees"
    __table_args__ = (
        UniqueConstraint(
            "workspace_owner_id",
            "school_institute_id",
            name="uq_school_registration_fees_workspace",
        ),
        CheckConstraint("book_price >= 0", name="nonnegative_school_book_price"),
        CheckConstraint("exam_price >= 0", name="nonnegative_school_exam_price"),
    )

    workspace_owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    school_institute_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("school_institutes.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    book_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0"
    )
    exam_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0"
    )


class ExamPricingPeriod(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "school_exam_pricing_periods"
    __table_args__ = (
        UniqueConstraint(
            "school_institute_id", "academic_year", "name", name="uq_exam_period_school_name"
        ),
        CheckConstraint(
            "starts_on IS NULL OR ends_on IS NULL OR starts_on <= ends_on",
            name="valid_exam_pricing_period_dates",
        ),
    )

    workspace_owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    school_institute_id: Mapped[UUID] = mapped_column(
        ForeignKey("school_institutes.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    academic_year: Mapped[str] = mapped_column(
        String(9), default="1405/1406", server_default="1405/1406", index=True
    )
    starts_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)


class SchoolExamPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Manager-owned exam and book-voucher pricing for a grade and major."""

    __tablename__ = "school_exam_plans"
    __table_args__ = (
        UniqueConstraint(
            "workspace_owner_id",
            "school_institute_id",
            "academic_year",
            "grade",
            "academic_track",
            "plan_code",
            "pricing_period_id",
            "revision",
            name="uq_school_exam_plan_period_revision",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(GRADE_CHECK, name="valid_school_exam_plan_grade"),
        CheckConstraint("exam_count > 0", name="positive_school_exam_plan_count"),
        CheckConstraint("exam_unit_price >= 0", name="nonnegative_school_exam_plan_unit_price"),
        CheckConstraint("exam_total >= 0", name="nonnegative_school_exam_plan_total"),
        CheckConstraint(
            "book_voucher_amount >= 0", name="nonnegative_school_exam_plan_book_amount"
        ),
        CheckConstraint(
            "book_voucher_discount >= 0", name="nonnegative_school_exam_plan_book_discount"
        ),
        CheckConstraint(
            "book_voucher_discount <= book_voucher_amount",
            name="school_exam_plan_discount_within_book_amount",
        ),
    )

    workspace_owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    school_institute_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("school_institutes.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    grade: Mapped[str] = mapped_column(String(20), index=True)
    academic_year: Mapped[str] = mapped_column(
        String(9), default="1405/1406", server_default="1405/1406", index=True
    )
    academic_track: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    plan_code: Mapped[str] = mapped_column(String(30))
    pricing_period_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("school_exam_pricing_periods.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    exam_count: Mapped[int] = mapped_column(Integer)
    exam_unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    exam_total: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    book_voucher_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    book_voucher_discount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class SchoolSpecialSupport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Manager-defined special support (پشتیبان ویژه) pricing catalog."""

    __tablename__ = "school_special_supports"
    __table_args__ = (
        UniqueConstraint(
            "workspace_owner_id",
            "school_institute_id",
            "name",
            name="uq_school_special_support_workspace_name",
        ),
        CheckConstraint("monthly_price >= 0", name="nonnegative_school_special_support_monthly"),
        CheckConstraint("seasonal_price >= 0", name="nonnegative_school_special_support_seasonal"),
    )

    workspace_owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    school_institute_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("school_institutes.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    monthly_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0"
    )
    seasonal_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class Student(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint(
            "workspace_owner_id",
            "school_institute_id",
            "national_id",
            name="uq_student_workspace_national_id",
        ),
        CheckConstraint(GRADE_CHECK, name="valid_student_grade"),
    )

    workspace_owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    school_institute_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("school_institutes.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    full_name: Mapped[str] = mapped_column(String(200))
    national_id: Mapped[str] = mapped_column(String(20))
    student_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    birth_date: Mapped[date] = mapped_column(Date)
    registration_date: Mapped[date] = mapped_column(
        Date, default=date.today, server_default="CURRENT_DATE"
    )
    first_exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    grade: Mapped[str] = mapped_column(String(20), index=True)
    academic_track: Mapped[str | None] = mapped_column(String(100), nullable=True)
    book_voucher_eligible: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    exam_registered: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    guardian_full_name: Mapped[str] = mapped_column(String(200))
    guardian_phone: Mapped[str] = mapped_column(String(32))
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    previous_school: Mapped[str | None] = mapped_column(String(200), nullable=True)
    emergency_contact: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    enrollments: Mapped[list["StudentEnrollment"]] = relationship(
        back_populates="student", cascade="all, delete-orphan", lazy="selectin"
    )


class StudentEnrollment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "student_enrollments"
    __table_args__ = (
        CheckConstraint(
            "subtotal >= 0 AND discount_amount >= 0 AND total_amount >= 0 "
            "AND amount_paid >= 0 AND balance_due >= 0",
            name="nonnegative_enrollment_amounts",
        ),
        CheckConstraint(
            "status IN ('UNPAID','PARTIALLY_PAID','PAID','OVERDUE')", name="valid_enrollment_status"
        ),
    )

    workspace_owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    academic_year: Mapped[str] = mapped_column(
        String(9), default="1405/1406", server_default="1405/1406", index=True
    )
    grade: Mapped[str | None] = mapped_column(String(20), nullable=True)
    academic_track: Mapped[str | None] = mapped_column(String(100), nullable=True)
    registration_date: Mapped[date] = mapped_column(
        Date, default=date.today, server_default="CURRENT_DATE"
    )
    school_institute_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("school_institutes.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), index=True
    )
    created_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    discount_code_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("school_discount_codes.id", ondelete="RESTRICT"), nullable=True
    )
    exam_plan_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("school_exam_plans.id", ondelete="RESTRICT"), nullable=True
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, server_default="0")
    book_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, server_default="0")
    exam_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, server_default="0")
    exam_plan_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # These are immutable pricing/attendance inputs for the registration, not live catalog data.
    exam_session_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    special_support_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    special_support_period: Mapped[str | None] = mapped_column(String(20), nullable=True)
    special_support_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=0, server_default="0"
    )
    book_voucher_discount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=0, server_default="0"
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, server_default="0")
    balance_due: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(String(20), default="UNPAID", server_default="UNPAID")
    student: Mapped[Student] = relationship(back_populates="enrollments")
    courses: Mapped[list["EnrollmentCourse"]] = relationship(
        back_populates="enrollment", cascade="all, delete-orphan", lazy="selectin"
    )
    payments: Mapped[list["EnrollmentPayment"]] = relationship(
        back_populates="enrollment", cascade="all, delete-orphan", lazy="selectin"
    )
    class_changes: Mapped[list["EnrollmentClassChange"]] = relationship(
        back_populates="enrollment",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="EnrollmentClassChange.created_at",
    )
    attendance_records: Mapped[list["EnrollmentServiceAttendance"]] = relationship(
        back_populates="enrollment", cascade="all, delete-orphan", lazy="selectin"
    )
    service_cancellations: Mapped[list["EnrollmentServiceCancellation"]] = relationship(
        back_populates="enrollment",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="EnrollmentServiceCancellation.created_at",
    )
    support_changes: Mapped[list["EnrollmentSupportChange"]] = relationship(
        back_populates="enrollment",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="EnrollmentSupportChange.created_at",
    )

    @property
    def credit_balance(self) -> Decimal:
        return max(self.amount_paid - self.total_amount, Decimal("0"))


class EnrollmentCourse(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "enrollment_courses"
    __table_args__ = (UniqueConstraint("enrollment_id", "course_id", name="uq_enrollment_course"),)

    enrollment_id: Mapped[UUID] = mapped_column(
        ForeignKey("student_enrollments.id", ondelete="CASCADE"), index=True
    )
    course_id: Mapped[UUID] = mapped_column(ForeignKey("school_courses.id", ondelete="RESTRICT"))
    course_name: Mapped[str] = mapped_column(String(200))
    instructor_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    session_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", server_default="ACTIVE")
    enrollment: Mapped[StudentEnrollment] = relationship(back_populates="courses")


class EnrollmentPayment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "enrollment_payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="positive_enrollment_payment_amount"),
        CheckConstraint(
            "method IN ('CASH','BANK_TRANSFER','CHECK','INSTALLMENT')",
            name="valid_enrollment_payment_method",
        ),
        CheckConstraint(
            "status IN ('PENDING','PAID','BOUNCED','CANCELLED')",
            name="valid_enrollment_payment_status",
        ),
        Index("ix_enrollment_payment_due_date", "due_date"),
    )

    workspace_owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    school_institute_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("school_institutes.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    enrollment_id: Mapped[UUID] = mapped_column(
        ForeignKey("student_enrollments.id", ondelete="CASCADE"), index=True
    )
    recorded_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    method: Mapped[str] = mapped_column(String(20))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    tracking_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sayad_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", server_default="PENDING")
    enrollment: Mapped[StudentEnrollment] = relationship(back_populates="payments")


class EnrollmentClassChange(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable class/price snapshots and a separately confirmed refund request."""

    __tablename__ = "enrollment_class_changes"
    __table_args__ = (
        CheckConstraint("refund_amount >= 0", name="nonnegative_class_change_refund"),
        CheckConstraint(
            "excess_handling IN ('CREDIT','REFUND')", name="valid_class_change_excess_handling"
        ),
        CheckConstraint(
            "refund_status IN ('NONE','PENDING','PAID','CANCELLED')",
            name="valid_class_change_refund_status",
        ),
        CheckConstraint(
            "refund_method IS NULL OR refund_method IN ('CASH','BANK_TRANSFER')",
            name="valid_class_change_refund_method",
        ),
    )
    enrollment_id: Mapped[UUID] = mapped_column(
        ForeignKey("student_enrollments.id", ondelete="CASCADE"), index=True
    )
    changed_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    old_course_id: Mapped[UUID] = mapped_column(
        ForeignKey("school_courses.id", ondelete="RESTRICT")
    )
    new_course_id: Mapped[UUID] = mapped_column(
        ForeignKey("school_courses.id", ondelete="RESTRICT")
    )
    old_course_name: Mapped[str] = mapped_column(String(200))
    new_course_name: Mapped[str] = mapped_column(String(200))
    old_instructor_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    new_instructor_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    old_price: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    new_price: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    old_total: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    new_total: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    reason: Mapped[str] = mapped_column(String(500))
    excess_handling: Mapped[str] = mapped_column(String(10))
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, server_default="0")
    refund_status: Mapped[str] = mapped_column(String(10), default="NONE", server_default="NONE")
    refund_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    refunded_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    refund_tracking_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    refunded_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    enrollment: Mapped[StudentEnrollment] = relationship(back_populates="class_changes")


class EnrollmentServiceAttendance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One immutable attendance record for a billable class or exam session."""

    __tablename__ = "enrollment_service_attendance"
    __table_args__ = (
        UniqueConstraint(
            "enrollment_id",
            "service_key",
            "session_number",
            name="uq_enrollment_service_attendance_session",
        ),
        CheckConstraint("service_type IN ('COURSE','EXAM')", name="valid_attendance_service_type"),
        CheckConstraint("session_number > 0", name="positive_attendance_session_number"),
    )

    enrollment_id: Mapped[UUID] = mapped_column(
        ForeignKey("student_enrollments.id", ondelete="CASCADE"), index=True
    )
    course_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("school_courses.id", ondelete="RESTRICT"), nullable=True
    )
    recorded_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    service_type: Mapped[str] = mapped_column(String(20))
    service_key: Mapped[str] = mapped_column(String(80))
    session_number: Mapped[int] = mapped_column(Integer)
    attended_on: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    enrollment: Mapped[StudentEnrollment] = relationship(back_populates="attendance_records")


class EnrollmentServiceCancellation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A service cancellation is an accounting event, never a destructive delete."""

    __tablename__ = "enrollment_service_cancellations"
    __table_args__ = (
        UniqueConstraint("enrollment_id", "service_key", name="uq_enrollment_service_cancellation"),
        CheckConstraint(
            "service_type IN ('COURSE','EXAM','BOOK','SUPPORT')",
            name="valid_cancellation_service_type",
        ),
        CheckConstraint(
            "total_sessions >= 0 AND attended_sessions >= 0",
            name="nonnegative_cancellation_sessions",
        ),
        CheckConstraint(
            "attended_sessions <= total_sessions", name="cancellation_sessions_within_total"
        ),
        CheckConstraint(
            "original_price >= 0 AND attendance_charge >= 0 "
            "AND cancellation_fee >= 0 AND retained_amount >= 0 "
            "AND refund_amount >= 0",
            name="nonnegative_cancellation_amounts",
        ),
        CheckConstraint(
            "refund_status IN ('NONE','PENDING','PAID','CANCELLED')",
            name="valid_cancellation_refund_status",
        ),
        CheckConstraint(
            "refund_method IS NULL OR refund_method IN ('CASH','BANK_TRANSFER')",
            name="valid_cancellation_refund_method",
        ),
    )

    enrollment_id: Mapped[UUID] = mapped_column(
        ForeignKey("student_enrollments.id", ondelete="CASCADE"), index=True
    )
    requested_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    course_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("school_courses.id", ondelete="RESTRICT"), nullable=True
    )
    service_type: Mapped[str] = mapped_column(String(20))
    service_key: Mapped[str] = mapped_column(String(80))
    service_name: Mapped[str] = mapped_column(String(200))
    original_price: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    total_sessions: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    attended_sessions: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    attendance_charge: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=0, server_default="0"
    )
    cancellation_fee: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, server_default="0")
    retained_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, server_default="0")
    old_total: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    new_total: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    reason: Mapped[str] = mapped_column(String(500))
    excess_handling: Mapped[str] = mapped_column(String(10))
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, server_default="0")
    refund_status: Mapped[str] = mapped_column(String(10), default="NONE", server_default="NONE")
    refund_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    refunded_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    refund_tracking_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    refunded_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    enrollment: Mapped[StudentEnrollment] = relationship(back_populates="service_cancellations")


class EnrollmentSupportChange(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable record of replacing a student's special-support plan."""

    __tablename__ = "enrollment_support_changes"
    __table_args__ = (
        CheckConstraint(
            "old_price >= 0 AND new_price >= 0", name="nonnegative_support_change_prices"
        ),
    )

    enrollment_id: Mapped[UUID] = mapped_column(
        ForeignKey("student_enrollments.id", ondelete="CASCADE"), index=True
    )
    changed_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    old_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    old_period: Mapped[str | None] = mapped_column(String(20), nullable=True)
    old_price: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    new_name: Mapped[str] = mapped_column(String(200))
    new_period: Mapped[str] = mapped_column(String(20))
    new_price: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    old_total: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    new_total: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    reason: Mapped[str] = mapped_column(String(500))
    enrollment: Mapped[StudentEnrollment] = relationship(back_populates="support_changes")


class SchoolCost(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "school_costs"
    __table_args__ = (
        UniqueConstraint(
            "workspace_owner_id",
            "school_institute_id",
            "factor_number",
            name="uq_school_cost_workspace_factor_number",
        ),
        CheckConstraint("amount > 0", name="positive_school_cost_amount"),
        CheckConstraint(
            "payment_method IN ('CASH','CHECK','BANK_TRANSFER')",
            name="valid_school_cost_payment_method",
        ),
    )

    workspace_owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    school_institute_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("school_institutes.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    factor_number: Mapped[str] = mapped_column(String(100))
    vendor_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reason: Mapped[str] = mapped_column(String(300))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    cost_date: Mapped[date] = mapped_column(Date, index=True)
    payment_method: Mapped[str] = mapped_column(String(20))
    check_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    tracking_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
