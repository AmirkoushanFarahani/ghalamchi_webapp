from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

SchoolGrade = Literal[
    "GRADE_1",
    "GRADE_2",
    "GRADE_3",
    "GRADE_4",
    "GRADE_5",
    "GRADE_6",
    "GRADE_7",
    "GRADE_8",
    "GRADE_9",
    "GRADE_10",
    "GRADE_11",
    "GRADE_12",
]
PaymentMethod = Literal["CASH", "BANK_TRANSFER", "CHECK", "INSTALLMENT"]
SchoolCostPaymentMethod = Literal["CASH", "BANK_TRANSFER", "CHECK"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CourseCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    instructor_name: str | None = Field(default=None, max_length=200)
    grade: SchoolGrade
    price: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    session_count: int = Field(default=0, ge=0, le=500)


class CourseUpdate(CourseCreate):
    """Manager-controlled replacement of editable course information."""

    is_active: bool = True


class CourseRead(ORMModel):
    id: UUID
    name: str
    instructor_name: str | None
    grade: SchoolGrade
    price: Decimal
    session_count: int = 0
    is_active: bool
    is_deleted: bool = False


class DiscountCodeCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    code: str = Field(min_length=2, max_length=50)
    percentage: Decimal = Field(gt=0, le=100, max_digits=5, decimal_places=2)
    expires_on: date | None = None
    max_uses: int | None = Field(default=None, gt=0)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.upper()


class DiscountCodeRead(ORMModel):
    id: UUID
    code: str
    percentage: Decimal
    expires_on: date | None
    max_uses: int | None
    uses_count: int
    is_active: bool


class RegistrationFeesRead(BaseModel):
    book_price: Decimal
    exam_price: Decimal


class RegistrationFeesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    book_price: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    exam_price: Decimal = Field(ge=0, max_digits=18, decimal_places=2)


class SpecialSupportCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    monthly_price: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    seasonal_price: Decimal = Field(ge=0, max_digits=18, decimal_places=2)


class SpecialSupportUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    monthly_price: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    seasonal_price: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    is_active: bool = True


class SpecialSupportRead(ORMModel):
    id: UUID
    name: str
    monthly_price: Decimal
    seasonal_price: Decimal
    is_active: bool
    is_deleted: bool = False


class SpecialSupportSelection(BaseModel):
    """An optional special-support add-on chosen during student registration."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    support_id: UUID
    period: Literal["MONTHLY", "SEASONAL"]


class ExamPricingPeriodCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    starts_on: date | None = None
    ends_on: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "ExamPricingPeriodCreate":
        if self.starts_on is None and self.ends_on is None:
            raise ValueError("حداقل تاریخ شروع یا پایان بازه را انتخاب کنید.")
        if self.starts_on and self.ends_on and self.starts_on > self.ends_on:
            raise ValueError("تاریخ پایان نباید قبل از تاریخ شروع باشد.")
        return self


class ExamCatalogImportRead(BaseModel):
    added_prices: int
    periods_count: int


class ExamPricingPeriodRead(ORMModel):
    id: UUID
    name: str
    starts_on: date | None
    ends_on: date | None


class ExamPlanRead(ORMModel):
    id: UUID
    grade: SchoolGrade
    academic_track: str | None
    plan_code: str
    exam_count: int
    exam_unit_price: Decimal
    exam_total: Decimal
    book_voucher_amount: Decimal
    book_voucher_discount: Decimal
    is_active: bool
    pricing_period_id: UUID | None = None
    revision: int = 1
    is_current: bool = True
    is_deleted: bool = False


class ExamPlanUpdate(BaseModel):
    """Manager-controlled replacement of an exam and book-voucher plan."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    grade: SchoolGrade
    academic_track: str | None = Field(default=None, max_length=100)
    plan_code: str = Field(min_length=1, max_length=30)
    exam_count: int = Field(gt=0)
    exam_unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    exam_total: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    book_voucher_amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    book_voucher_discount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    is_active: bool = True
    pricing_period_id: UUID | None = None
    expected_revision: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def voucher_discount_must_not_exceed_amount(self) -> "ExamPlanUpdate":
        if self.book_voucher_discount > self.book_voucher_amount:
            raise ValueError("Book-voucher discount cannot exceed its amount")
        return self


class EnrollmentPaymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    method: PaymentMethod
    due_date: date | None = None
    tracking_code: str | None = Field(default=None, max_length=100)
    sayad_id: str | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def scheduled_payments_require_due_date(self) -> "EnrollmentPaymentCreate":
        if self.method in {"CHECK", "INSTALLMENT"} and self.due_date is None:
            raise ValueError("A check or installment payment requires a due date")
        return self


class StudentEnrollmentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    full_name: str = Field(min_length=3, max_length=200)
    national_id: str = Field(min_length=5, max_length=20)
    student_phone: str | None = Field(default=None, max_length=32)
    birth_date: date
    registration_date: date | None = None
    first_exam_date: date | None = None
    grade: SchoolGrade
    academic_track: str | None = Field(default=None, max_length=100)
    book_voucher_eligible: bool = False
    exam_registered: bool = False
    exam_plan_id: UUID | None = None
    guardian_full_name: str = Field(min_length=3, max_length=200)
    guardian_phone: str = Field(min_length=7, max_length=32)
    address: str | None = Field(default=None, max_length=500)
    previous_school: str | None = Field(default=None, max_length=200)
    emergency_contact: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=1000)
    course_ids: list[UUID] = Field(default_factory=list, max_length=200)
    discount_code: str | None = Field(default=None, max_length=50)
    special_support: SpecialSupportSelection | None = None
    payments: list[EnrollmentPaymentCreate] = Field(default_factory=list, max_length=120)


class EnrollmentCourseRead(ORMModel):
    course_id: UUID
    course_name: str
    instructor_name: str | None = None
    price: Decimal
    session_count: int = 0
    status: Literal["ACTIVE", "CANCELLED"] = "ACTIVE"


class AttendanceCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    service_type: Literal["COURSE", "EXAM"]
    course_id: UUID | None = None
    session_number: int = Field(gt=0, le=500)
    attended_on: date
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def course_attendance_requires_course(self) -> "AttendanceCreate":
        if (self.service_type == "COURSE") != (self.course_id is not None):
            raise ValueError(
                "Course attendance requires a course; exam attendance must not include one"
            )
        return self


class AttendanceRead(ORMModel):
    id: UUID
    service_type: Literal["COURSE", "EXAM"]
    course_id: UUID | None
    session_number: int
    attended_on: date
    notes: str | None
    created_at: datetime


class ServiceCancellationCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    service_type: Literal["COURSE", "EXAM", "BOOK", "SUPPORT"]
    course_id: UUID | None = None
    attended_sessions: int = Field(default=0, ge=0, le=500)
    expected_original_price: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    expected_total: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    reason: str = Field(min_length=1, max_length=500)
    excess_handling: Literal["CREDIT", "REFUND"] = "CREDIT"

    @model_validator(mode="after")
    def course_cancellation_requires_course(self) -> "ServiceCancellationCreate":
        if (self.service_type == "COURSE") != (self.course_id is not None):
            raise ValueError(
                "Course cancellation requires a course; other services must not include one"
            )
        return self


class ServiceCancellationRead(ORMModel):
    id: UUID
    service_type: Literal["COURSE", "EXAM", "BOOK", "SUPPORT"]
    service_name: str
    original_price: Decimal
    total_sessions: int
    attended_sessions: int
    attendance_charge: Decimal
    cancellation_fee: Decimal
    retained_amount: Decimal
    old_total: Decimal
    new_total: Decimal
    reason: str
    excess_handling: Literal["CREDIT", "REFUND"]
    refund_amount: Decimal
    refund_status: Literal["NONE", "PENDING", "PAID", "CANCELLED"]
    refund_method: Literal["CASH", "BANK_TRANSFER"] | None
    refunded_on: date | None
    refund_tracking_code: str | None
    created_at: datetime


class SupportChangeCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    support_id: UUID
    period: Literal["MONTHLY", "SEASONAL"]
    expected_old_price: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    expected_total: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    reason: str = Field(min_length=1, max_length=500)


class SupportChangeRead(ORMModel):
    id: UUID
    old_name: str | None
    old_period: Literal["MONTHLY", "SEASONAL"] | None
    old_price: Decimal
    new_name: str
    new_period: Literal["MONTHLY", "SEASONAL"]
    new_price: Decimal
    old_total: Decimal
    new_total: Decimal
    reason: str
    created_at: datetime


class EnrollmentPaymentRead(ORMModel):
    id: UUID
    amount: Decimal
    method: PaymentMethod
    due_date: date | None
    tracking_code: str | None
    sayad_id: str | None
    status: Literal["PENDING", "PAID", "BOUNCED", "CANCELLED"]
    created_at: datetime
    updated_at: datetime


class EnrollmentRead(ORMModel):
    id: UUID
    subtotal: Decimal
    discount_amount: Decimal
    book_price: Decimal
    exam_price: Decimal
    exam_session_count: int = 0
    special_support_name: str | None
    special_support_period: Literal["MONTHLY", "SEASONAL"] | None
    special_support_price: Decimal
    total_amount: Decimal
    amount_paid: Decimal
    balance_due: Decimal
    credit_balance: Decimal = Decimal("0")
    status: Literal["UNPAID", "PARTIALLY_PAID", "PAID", "OVERDUE"]
    courses: list[EnrollmentCourseRead]
    payments: list[EnrollmentPaymentRead]
    class_changes: list["ClassChangeRead"] = Field(default_factory=list)
    attendance_records: list[AttendanceRead] = Field(default_factory=list)
    service_cancellations: list[ServiceCancellationRead] = Field(default_factory=list)
    support_changes: list[SupportChangeRead] = Field(default_factory=list)


class StudentRead(ORMModel):
    id: UUID
    full_name: str
    national_id: str
    student_phone: str | None
    birth_date: date
    registration_date: date
    first_exam_date: date | None
    grade: SchoolGrade
    academic_track: str | None
    book_voucher_eligible: bool
    exam_registered: bool
    guardian_full_name: str
    guardian_phone: str
    address: str | None
    previous_school: str | None
    emergency_contact: str | None
    notes: str | None
    created_by_id: UUID
    enrollments: list[EnrollmentRead]


class PaymentStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["PAID", "BOUNCED", "CANCELLED"]


class ClassChangeCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    new_course_id: UUID
    expected_old_price: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    expected_new_price: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    expected_total: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    reason: str = Field(min_length=1, max_length=500)
    excess_handling: Literal["CREDIT", "REFUND"] = "CREDIT"
    payment: EnrollmentPaymentCreate | None = None


class RefundAction(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    action: Literal["PAY", "KEEP_CREDIT"]
    method: Literal["CASH", "BANK_TRANSFER"] | None = None
    paid_on: date | None = None
    tracking_code: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def paid_refund_requires_details(self) -> "RefundAction":
        if self.action == "PAY" and (self.method is None or self.paid_on is None):
            raise ValueError("A paid refund requires a method and payment date")
        return self


class ClassChangeRead(ORMModel):
    id: UUID
    old_course_name: str
    new_course_name: str
    old_instructor_name: str | None
    new_instructor_name: str | None
    old_price: Decimal
    new_price: Decimal
    old_total: Decimal
    new_total: Decimal
    reason: str
    changed_by_id: UUID
    created_at: datetime
    excess_handling: Literal["CREDIT", "REFUND"]
    refund_amount: Decimal
    refund_status: Literal["NONE", "PENDING", "PAID", "CANCELLED"]
    refund_method: Literal["CASH", "BANK_TRANSFER"] | None
    refunded_on: date | None
    refund_tracking_code: str | None


EnrollmentRead.model_rebuild()
StudentRead.model_rebuild()


class StudentSegmentationRead(BaseModel):
    student_id: UUID
    segment: int
    behavioral_description: str
    model_version: str
    prediction_timestamp: datetime
    as_of: date


class SchoolCostCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    factor_number: str | None = Field(default=None, max_length=100)
    vendor_name: str | None = Field(default=None, max_length=200)
    reason: str = Field(min_length=1, max_length=300)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    cost_date: date
    payment_method: SchoolCostPaymentMethod
    check_due_date: date | None = None
    tracking_code: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def check_requires_due_date(self) -> "SchoolCostCreate":
        if self.payment_method == "CHECK" and self.check_due_date is None:
            raise ValueError("A check cost requires a due date")
        return self


class SchoolCostRead(ORMModel):
    id: UUID
    factor_number: str
    vendor_name: str | None
    reason: str
    amount: Decimal
    cost_date: date
    payment_method: SchoolCostPaymentMethod
    check_due_date: date | None
    tracking_code: str | None
    notes: str | None


class SchoolCostList(BaseModel):
    items: list[SchoolCostRead]
    total: Decimal


class SchoolInstituteCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=2, max_length=200)


class SchoolInstituteRead(ORMModel):
    id: UUID
    name: str
    is_active: bool
    secretary_name: str | None = None
    secretary_id: UUID | None = None


class SchoolInstituteSelect(BaseModel):
    model_config = ConfigDict(extra="forbid")
    school_institute_id: UUID


class SchoolSecretaryAssign(BaseModel):
    model_config = ConfigDict(extra="forbid")
    secretary_id: UUID


class SchoolSecretaryCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class SchoolSecretaryPasswordReset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=12, max_length=128)


class SchoolSecretaryRead(ORMModel):
    id: UUID
    first_name: str
    last_name: str
    email: EmailStr | None
    is_active: bool
    last_login_at: datetime | None


class SchoolSecretaryUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr


class SchoolSecretaryStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: bool


class SchoolComparisonRead(BaseModel):
    school_institute_id: UUID
    school_name: str
    student_count: int
    registered_tuition: Decimal
    received_tuition: Decimal
    outstanding_tuition: Decimal
    due_payments: Decimal
    costs: Decimal
    net_cash: Decimal
