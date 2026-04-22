from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[UUID] = mapped_column(default=uuid4, primary_key=True)
    total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    meta: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String)
    idempotency_key: Mapped[UUID] = mapped_column(default=uuid4)
    webhook_url: Mapped[str] = mapped_column(String)
