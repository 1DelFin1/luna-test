from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.models.payment import Currency, PaymentStatus


class CreatePaymentRequest(BaseModel):
    total: Decimal
    currency: Currency
    description: str
    meta: dict
    webhook_url: str


class PaymentCreatedResponse(BaseModel):
    payment_id: UUID
    status: PaymentStatus
    created_at: datetime


class PaymentDetailResponse(BaseModel):
    id: UUID
    total: Decimal
    currency: Currency
    description: str
    meta: dict
    status: PaymentStatus
    idempotency_key: UUID
    webhook_url: str
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None

    model_config = {"from_attributes": True}


class PaymentEvent(BaseModel):
    payment_id: UUID
    webhook_url: str
