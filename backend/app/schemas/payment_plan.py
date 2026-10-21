from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PaymentPart(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    method: Literal["CASH", "BANK_TRANSFER", "CHECK", "INSTALLMENT"]
    due_date: date | None = None
    tracking_code: str | None = Field(default=None, max_length=100)
    sayad_id: str | None = Field(default=None, max_length=32)


class ScheduledCheckDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    due_date: date | None = None
    tracking_code: str | None = Field(default=None, max_length=100)
    sayad_id: str | None = Field(default=None, max_length=32)


class PaymentPlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[PaymentPart] = Field(default_factory=list, max_length=60)
    installment_count: int = Field(default=0, ge=0, le=60)
    installment_method: Literal["INSTALLMENT", "CHECK"] = "INSTALLMENT"
    check_details: list[ScheduledCheckDetails] = Field(default_factory=list, max_length=60)


class PaymentPlanReplace(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan: PaymentPlanCreate
    expected_balance: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    expected_pending_ids: list[UUID] = Field(default_factory=list, max_length=120)


class PaymentPlanPreview(BaseModel):
    anchor_date: date | None = None
    model_config = ConfigDict(extra="forbid")
    total: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    plan: PaymentPlanCreate


class PaymentPlanRead(BaseModel):
    total: Decimal
    immediate: Decimal
    scheduled: Decimal
    items: list[PaymentPart]
