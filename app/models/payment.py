import enum
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import String, JSON, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class Currency(str, enum.Enum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[UUID] = mapped_column(default=uuid4, primary_key=True)
    total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    currency: Mapped[Currency] = mapped_column(Enum(Currency))
    description: Mapped[str] = mapped_column(String)
    meta: Mapped[dict] = mapped_column(JSON)
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    idempotency_key: Mapped[UUID] = mapped_column(default=uuid4, unique=True)
    webhook_url: Mapped[str] = mapped_column(String)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
