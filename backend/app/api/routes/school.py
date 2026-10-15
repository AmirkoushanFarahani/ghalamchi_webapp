from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_permission
from backend.app.api.routes.auth import enforce_auth_rate_limit
from backend.app.core.config import Settings, get_settings
from backend.app.db.database import get_db
from backend.app.db.models import (
    DiscountCode,
    EnrollmentPayment,
    SchoolCost,
    SchoolCourse,
    SchoolInstitute,
    SchoolSpecialSupport,
    Student,
    User,
)
from backend.app.ml.registry import (
    ModelNotFoundError,
    NoActiveModelError,
    PredictionExecutionError,
    PredictionInputError,
)
from backend.app.schemas.school import (
    AttendanceCreate,
    AttendanceRead,
    ClassChangeCreate,
    ClassChangeRead,
    CourseCreate,
    CourseRead,
    CourseUpdate,
    DiscountCodeCreate,
    DiscountCodeRead,
    EnrollmentCourseRead,
    EnrollmentPaymentCreate,
    EnrollmentPaymentRead,
    EnrollmentRead,
    ExamPlanRead,
    ExamPlanUpdate,
    ExamPricingPeriodCreate,
    ExamPricingPeriodRead,
    PaymentStatusUpdate,
    RefundAction,
    RegistrationFeesRead,
    RegistrationFeesUpdate,
    SchoolComparisonRead,
    SchoolCostCreate,
    SchoolCostList,
    SchoolCostRead,
    SchoolGrade,
    SchoolInstituteCreate,
    SchoolInstituteRead,
    SchoolInstituteSelect,
    SchoolSecretaryAssign,
    SchoolSecretaryCreate,
    SchoolSecretaryPasswordReset,
    SchoolSecretaryRead,
    SchoolSecretaryStatusUpdate,
    SchoolSecretaryUpdate,
    ServiceCancellationCreate,
    ServiceCancellationRead,
    SpecialSupportCreate,
    SpecialSupportRead,
    SpecialSupportUpdate,
    StudentEnrollmentCreate,
    StudentRead,
    StudentSegmentationRead,
    SupportChangeCreate,
    SupportChangeRead,
)
from backend.app.services.ml import MLService
from backend.app.services.school import SchoolConflictError, SchoolError, SchoolService

router = APIRouter(prefix="/school")
SessionDep = Annotated[Session, Depends(get_db)]


def service(session: Session, actor: User) -> SchoolService:
    return SchoolService(session, actor)


def student_read(student: Student) -> StudentRead:
    return StudentRead(
        id=student.id,
        full_name=student.full_name,
        national_id=student.national_id,
        student_phone=student.student_phone,
        birth_date=student.birth_date,
        registration_date=student.registration_date,
        first_exam_date=student.first_exam_date,
        grade=cast(SchoolGrade, student.grade),
        academic_track=student.academic_track,
        book_voucher_eligible=student.book_voucher_eligible,
        exam_registered=student.exam_registered,
        guardian_full_name=student.guardian_full_name,
        guardian_phone=student.guardian_phone,
        address=student.address,
        previous_school=student.previous_school,
        emergency_contact=student.emergency_contact,
        notes=student.notes,
        created_by_id=student.created_by_id,
        enrollments=[
            EnrollmentRead(
                id=enrollment.id,
                subtotal=enrollment.subtotal,
                discount_amount=enrollment.discount_amount,
                book_price=enrollment.book_price,
                exam_price=enrollment.exam_price,
                exam_session_count=enrollment.exam_session_count,
                special_support_name=enrollment.special_support_name,
                special_support_period=cast(
                    Literal["MONTHLY", "SEASONAL"] | None,
                    enrollment.special_support_period,
                ),
                special_support_price=enrollment.special_support_price,
                total_amount=enrollment.total_amount,
                amount_paid=enrollment.amount_paid,
                balance_due=enrollment.balance_due,
                credit_balance=enrollment.credit_balance,
                class_changes=[
                    ClassChangeRead.model_validate(row) for row in enrollment.class_changes
                ],
                attendance_records=[
                    AttendanceRead.model_validate(row) for row in enrollment.attendance_records
                ],
                service_cancellations=[
                    ServiceCancellationRead.model_validate(row)
                    for row in enrollment.service_cancellations
                ],
                support_changes=[
                    SupportChangeRead.model_validate(row) for row in enrollment.support_changes
                ],
                status=cast(
                    Literal["UNPAID", "PARTIALLY_PAID", "PAID", "OVERDUE"],
                    enrollment.status,
                ),
                courses=[EnrollmentCourseRead.model_validate(row) for row in enrollment.courses],
                payments=[EnrollmentPaymentRead.model_validate(row) for row in enrollment.payments],
            )
            for enrollment in student.enrollments
        ],
    )


def institute_read(session: Session, institute: SchoolInstitute) -> SchoolInstituteRead:
    secretary = session.scalar(
        select(User).where(User.school_institute_id == institute.id).order_by(User.created_at)
    )
    return SchoolInstituteRead(
        id=institute.id,
        name=institute.name,
        is_active=institute.is_active,
        secretary_id=secretary.id if secretary else None,
        secretary_name=(f"{secretary.first_name} {secretary.last_name}" if secretary else None),
    )


@router.get("/institutes", response_model=list[SchoolInstituteRead])
def list_institutes(
    session: SessionDep, actor: Annotated[User, Depends(require_permission("school:read"))]
) -> list[SchoolInstituteRead]:
    return [institute_read(session, row) for row in service(session, actor).list_institutes()]


@router.post("/institutes", response_model=SchoolInstituteRead, status_code=status.HTTP_201_CREATED)
def create_institute(
    data: SchoolInstituteCreate,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> SchoolInstituteRead:
    try:
        return institute_read(session, service(session, actor).create_institute(data))
    except SchoolConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except SchoolError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.patch("/institutes/active", response_model=SchoolInstituteRead)
def select_institute(
    data: SchoolInstituteSelect,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> SchoolInstituteRead:
    try:
        return institute_read(
            session, service(session, actor).select_institute(data.school_institute_id)
        )
    except SchoolError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.patch("/institutes/{school_id}", response_model=SchoolInstituteRead)
def rename_institute(
    school_id: UUID,
    data: SchoolInstituteCreate,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> SchoolInstituteRead:
    try:
        return institute_read(session, service(session, actor).rename_institute(school_id, data))
    except SchoolConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except SchoolError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.patch("/institutes/{school_id}/secretary", response_model=SchoolInstituteRead)
def assign_secretary(
    school_id: UUID,
    data: SchoolSecretaryAssign,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> SchoolInstituteRead:
    try:
        return institute_read(session, service(session, actor).assign_secretary(school_id, data))
    except SchoolError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post(
    "/institutes/{school_id}/secretaries",
    response_model=SchoolInstituteRead,
    status_code=status.HTTP_201_CREATED,
)
def create_secretary(
    school_id: UUID,
    data: SchoolSecretaryCreate,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> SchoolInstituteRead:
    try:
        service(session, actor).create_secretary(school_id, data)
        school = session.get(SchoolInstitute, school_id)
        if school is None:
            raise SchoolError("School or institute was not found")
        return institute_read(session, school)
    except SchoolConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except SchoolError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/institutes/{school_id}/secretaries", response_model=list[SchoolSecretaryRead])
def list_secretaries(
    school_id: UUID,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> list[User]:
    try:
        return service(session, actor).list_secretaries(school_id)
    except SchoolError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.patch(
    "/institutes/{school_id}/secretaries/{secretary_id}", response_model=SchoolSecretaryRead
)
def update_secretary(
    school_id: UUID,
    secretary_id: UUID,
    data: SchoolSecretaryUpdate,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> User:
    try:
        return service(session, actor).update_secretary(school_id, secretary_id, data)
    except SchoolConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except SchoolError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.patch(
    "/institutes/{school_id}/secretaries/{secretary_id}/status", response_model=SchoolSecretaryRead
)
def set_secretary_status(
    school_id: UUID,
    secretary_id: UUID,
    data: SchoolSecretaryStatusUpdate,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> User:
    try:
        return service(session, actor).set_secretary_status(school_id, secretary_id, data.is_active)
    except SchoolError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.patch("/institutes/{school_id}/secretaries/{secretary_id}/password", status_code=204)
def reset_secretary_password(
    school_id: UUID,
    secretary_id: UUID,
    data: SchoolSecretaryPasswordReset,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
    request: Request,
) -> Response:
    enforce_auth_rate_limit(request, "secretary-password-reset", session, str(actor.id))
    try:
        service(session, actor).reset_secretary_password(school_id, secretary_id, data)
    except SchoolError as exc:
        raise HTTPException(404, str(exc)) from exc
    return Response(status_code=204)


@router.get("/institutes/comparison", response_model=list[SchoolComparisonRead])
def compare_institutes(
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> list[SchoolComparisonRead]:
    try:
        return [
            SchoolComparisonRead.model_validate(row) for row in service(session, actor).comparison()
        ]
    except SchoolError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.get("/courses", response_model=list[CourseRead])
def list_courses(
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:read"))],
    grade: str | None = None,
    include_deleted: bool = False,
) -> list[SchoolCourse]:
    if include_deleted and "school:manage" not in actor.permission_names:
        raise HTTPException(403, "Insufficient permission")
    return service(session, actor).list_courses(grade, include_deleted)


@router.post("/courses", response_model=CourseRead, status_code=status.HTTP_201_CREATED)
def create_course(
    data: CourseCreate,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> SchoolCourse:
    try:
        return service(session, actor).create_course(data)
    except SchoolConflictError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.patch("/courses/{course_id}", response_model=CourseRead)
def update_course(
    course_id: UUID,
    data: CourseUpdate,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> SchoolCourse:
    try:
        return service(session, actor).update_course(course_id, data)
    except SchoolConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except SchoolError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/special-supports", response_model=list[SpecialSupportRead])
def list_special_supports(
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:read"))],
    include_deleted: bool = False,
) -> list[SchoolSpecialSupport]:
    if include_deleted and "school:manage" not in actor.permission_names:
        raise HTTPException(403, "Insufficient permission")
    return service(session, actor).list_special_supports(include_deleted)


@router.post(
    "/special-supports", response_model=SpecialSupportRead, status_code=status.HTTP_201_CREATED
)
def create_special_support(
    data: SpecialSupportCreate,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> SchoolSpecialSupport:
    try:
        return service(session, actor).create_special_support(
            data.name, data.monthly_price, data.seasonal_price
        )
    except SchoolConflictError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.patch("/special-supports/{support_id}", response_model=SpecialSupportRead)
def update_special_support(
    support_id: UUID,
    data: SpecialSupportUpdate,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> SpecialSupportRead:
    try:
        return SpecialSupportRead.model_validate(
            service(session, actor).update_special_support(support_id, data)
        )
    except SchoolConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except SchoolError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/discounts", response_model=list[DiscountCodeRead])
def list_discounts(
    session: SessionDep, actor: Annotated[User, Depends(require_permission("school:manage"))]
) -> list[DiscountCode]:
    return service(session, actor).list_discounts()


@router.post("/discounts", response_model=DiscountCodeRead, status_code=status.HTTP_201_CREATED)
def create_discount(
    data: DiscountCodeCreate,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> DiscountCode:
    try:
        return service(session, actor).create_discount(data)
    except SchoolConflictError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/exam-pricing-periods", response_model=list[ExamPricingPeriodRead])
def list_exam_pricing_periods(
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:read"))],
) -> list[ExamPricingPeriodRead]:
    return [
        ExamPricingPeriodRead.model_validate(period)
        for period in service(session, actor).list_exam_pricing_periods()
    ]


@router.post("/exam-pricing-periods", response_model=ExamPricingPeriodRead, status_code=201)
def create_exam_pricing_period(
    data: ExamPricingPeriodCreate,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> ExamPricingPeriodRead:
    try:
        return ExamPricingPeriodRead.model_validate(
            service(session, actor).create_exam_pricing_period(data)
        )
    except SchoolConflictError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/exam-plans/{plan_id}/restore", response_model=ExamPlanRead)
def restore_exam_plan(
    plan_id: UUID,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> ExamPlanRead:
    try:
        return ExamPlanRead.model_validate(service(session, actor).restore_exam_plan(plan_id))
    except SchoolConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except SchoolError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/exam-plans", response_model=list[ExamPlanRead])
def list_exam_plans(
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:read"))],
    grade: str | None = None,
    include_deleted: bool = False,
) -> list[ExamPlanRead]:
    if include_deleted and "school:manage" not in actor.permission_names:
        raise HTTPException(403, "Insufficient permission")
    return [
        ExamPlanRead.model_validate(plan)
        for plan in service(session, actor).list_exam_plans(grade, include_deleted)
    ]


@router.delete("/catalog/{kind}/{item_id}", status_code=204)
def delete_catalog_item(
    kind: Literal["courses", "special-supports", "exam-plans"],
    item_id: UUID,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> Response:
    try:
        service(session, actor).set_catalog_deleted(kind, item_id, True)
    except SchoolError as exc:
        raise HTTPException(404, str(exc)) from exc
    return Response(status_code=204)


@router.post("/catalog/{kind}/{item_id}/restore", status_code=204)
def restore_catalog_item(
    kind: Literal["courses", "special-supports", "exam-plans"],
    item_id: UUID,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> Response:
    try:
        service(session, actor).set_catalog_deleted(kind, item_id, False)
    except SchoolError as exc:
        raise HTTPException(404, str(exc)) from exc
    return Response(status_code=204)


@router.post("/exam-plans", response_model=ExamPlanRead, status_code=status.HTTP_201_CREATED)
def create_exam_plan(
    data: ExamPlanUpdate,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> ExamPlanRead:
    try:
        return ExamPlanRead.model_validate(service(session, actor).create_exam_plan(data))
    except SchoolConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except SchoolError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.patch("/exam-plans/{plan_id}", response_model=ExamPlanRead)
def update_exam_plan(
    plan_id: UUID,
    data: ExamPlanUpdate,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> ExamPlanRead:
    try:
        return ExamPlanRead.model_validate(service(session, actor).update_exam_plan(plan_id, data))
    except SchoolConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except SchoolError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/registration-fees", response_model=RegistrationFeesRead)
def get_registration_fees(
    session: SessionDep, actor: Annotated[User, Depends(require_permission("school:read"))]
) -> RegistrationFeesRead:
    book_price, exam_price = service(session, actor).registration_fees()
    return RegistrationFeesRead(book_price=book_price, exam_price=exam_price)


@router.put("/registration-fees", response_model=RegistrationFeesRead)
def update_registration_fees(
    data: RegistrationFeesUpdate,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> RegistrationFeesRead:
    fees = service(session, actor).update_registration_fees(data)
    return RegistrationFeesRead(book_price=fees.book_price, exam_price=fees.exam_price)


@router.get("/students", response_model=list[StudentRead])
def list_students(
    session: SessionDep, actor: Annotated[User, Depends(require_permission("school:read"))]
) -> list[StudentRead]:
    return [student_read(student) for student in service(session, actor).list_students()]


@router.get("/students/{student_id}", response_model=StudentRead)
def get_student(
    student_id: UUID,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:read"))],
) -> StudentRead:
    try:
        return student_read(service(session, actor).get_student(student_id))
    except SchoolError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/costs", response_model=SchoolCostList)
def list_school_costs(
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
    start_date: date | None = None,
    end_date: date | None = None,
) -> SchoolCostList:
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(422, "Start date must not be after end date")
    rows = service(session, actor).list_costs(start_date, end_date)
    return SchoolCostList(
        items=[SchoolCostRead.model_validate(row) for row in rows],
        total=sum((row.amount for row in rows), Decimal("0")),
    )


@router.post("/costs", response_model=SchoolCostRead, status_code=status.HTTP_201_CREATED)
def create_school_cost(
    data: SchoolCostCreate,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> SchoolCost:
    try:
        return service(session, actor).create_cost(data)
    except SchoolConflictError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/students/enroll", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
def enroll_student(
    data: StudentEnrollmentCreate,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:enroll"))],
) -> StudentRead:
    try:
        return student_read(service(session, actor).create_enrollment(data))
    except SchoolConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except SchoolError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.patch("/payments/{payment_id}", response_model=EnrollmentPaymentRead)
def update_payment(
    payment_id: UUID,
    data: PaymentStatusUpdate,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:payments"))],
) -> EnrollmentPayment:
    try:
        return service(session, actor).update_payment_status(payment_id, data)
    except SchoolConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except SchoolError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.patch(
    "/students/{student_id}/enrollments/{enrollment_id}/classes/{course_id}",
    response_model=StudentRead,
)
def change_enrolled_class(
    student_id: UUID,
    enrollment_id: UUID,
    course_id: UUID,
    data: ClassChangeCreate,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:enroll"))],
) -> StudentRead:
    try:
        return student_read(
            service(session, actor).change_class(student_id, enrollment_id, course_id, data)
        )
    except SchoolConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except SchoolError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post(
    "/students/{student_id}/enrollments/{enrollment_id}/payments",
    response_model=StudentRead,
    status_code=201,
)
def add_student_payment(
    student_id: UUID,
    enrollment_id: UUID,
    data: EnrollmentPaymentCreate,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:payments"))],
) -> StudentRead:
    try:
        return student_read(service(session, actor).add_payment(student_id, enrollment_id, data))
    except SchoolConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except SchoolError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.patch(
    "/students/{student_id}/enrollments/{enrollment_id}/special-support",
    response_model=StudentRead,
)
def change_student_special_support(
    student_id: UUID,
    enrollment_id: UUID,
    data: SupportChangeCreate,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:enroll"))],
) -> StudentRead:
    try:
        return student_read(
            service(session, actor).change_special_support(student_id, enrollment_id, data)
        )
    except SchoolConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except SchoolError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post(
    "/students/{student_id}/enrollments/{enrollment_id}/attendance",
    response_model=StudentRead,
    status_code=201,
)
def record_student_attendance(
    student_id: UUID,
    enrollment_id: UUID,
    data: AttendanceCreate,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:enroll"))],
) -> StudentRead:
    try:
        return student_read(
            service(session, actor).record_attendance(student_id, enrollment_id, data)
        )
    except SchoolConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except SchoolError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post(
    "/students/{student_id}/enrollments/{enrollment_id}/cancellations",
    response_model=StudentRead,
    status_code=201,
)
def cancel_student_service(
    student_id: UUID,
    enrollment_id: UUID,
    data: ServiceCancellationCreate,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:enroll"))],
) -> StudentRead:
    try:
        return student_read(service(session, actor).cancel_service(student_id, enrollment_id, data))
    except SchoolConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except SchoolError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.patch(
    "/students/{student_id}/enrollments/{enrollment_id}/refunds/{change_id}",
    response_model=StudentRead,
)
def confirm_student_refund(
    student_id: UUID,
    enrollment_id: UUID,
    change_id: UUID,
    data: RefundAction,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> StudentRead:
    try:
        return student_read(
            service(session, actor).process_refund(student_id, enrollment_id, change_id, data)
        )
    except SchoolConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except SchoolError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.patch(
    "/students/{student_id}/enrollments/{enrollment_id}/cancellations/{cancellation_id}/refund",
    response_model=StudentRead,
)
def confirm_service_cancellation_refund(
    student_id: UUID,
    enrollment_id: UUID,
    cancellation_id: UUID,
    data: RefundAction,
    session: SessionDep,
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> StudentRead:
    try:
        return student_read(
            service(session, actor).process_service_cancellation_refund(
                student_id, enrollment_id, cancellation_id, data
            )
        )
    except SchoolConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except SchoolError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/accounting/students/{student_id}/segment", response_model=StudentSegmentationRead)
def segment_student_for_school_accounting(
    student_id: UUID,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    actor: Annotated[User, Depends(require_permission("school:manage"))],
) -> StudentSegmentationRead:
    # Verify the student belongs to the manager's shared school workspace before ML inference.
    try:
        service(session, actor).get_student(student_id)
        prediction, value = MLService(session, settings).segment_student(
            student_id, date.today(), actor
        )
    except ModelNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (NoActiveModelError, PredictionExecutionError, PredictionInputError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return StudentSegmentationRead(
        student_id=student_id,
        segment=int(value["segment"]),
        behavioral_description=str(value["behavioral_description"]),
        model_version=str(value["model_version"]),
        prediction_timestamp=prediction.predicted_at,
        as_of=date.today(),
    )
