from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.payment import Currency, Payment, PaymentStatus
from app.schemas import CreatePaymentRequest
from app.services.payment import PaymentService

FIXED_ID = uuid4()
FIXED_TIME = datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def session():
    s = AsyncMock()
    s.add = MagicMock()
    return s


@pytest.fixture
def create_request():
    return CreatePaymentRequest(
        total=Decimal("500.00"),
        currency=Currency.RUB,
        description="Test payment",
        meta={"order_id": 99},
        webhook_url="https://example.com/webhook",
    )


def _make_payment(**kwargs) -> Payment:
    defaults = dict(
        total=Decimal("500.00"),
        currency=Currency.RUB,
        description="Test payment",
        meta={"order_id": 99},
        webhook_url="https://example.com/webhook",
        idempotency_key=uuid4(),
        status=PaymentStatus.PENDING,
    )
    p = Payment(**{**defaults, **kwargs})
    p.id = FIXED_ID
    p.created_at = FIXED_TIME
    p.updated_at = FIXED_TIME
    p.processed_at = None
    return p


class TestCreatePayment:
    async def test_creates_payment_and_outbox_event(self, session, create_request):
        idempotency_key = uuid4()

        # первый execute — проверка дубля (не найден)
        no_result = MagicMock()
        no_result.scalar_one_or_none.return_value = None
        session.execute.return_value = no_result

        async def fake_refresh(obj):
            obj.id = FIXED_ID
            obj.status = PaymentStatus.PENDING
            obj.created_at = FIXED_TIME
            obj.updated_at = FIXED_TIME

        session.refresh.side_effect = fake_refresh

        result = await PaymentService.create_payment(session, create_request, idempotency_key)

        assert result.payment_id == FIXED_ID
        assert result.status == PaymentStatus.PENDING
        assert result.created_at == FIXED_TIME

        # payment + outbox_event
        assert session.add.call_count == 2
        session.commit.assert_called_once()

    async def test_returns_existing_on_duplicate_idempotency_key(self, session, create_request):
        idempotency_key = uuid4()
        existing = _make_payment(idempotency_key=idempotency_key)

        found = MagicMock()
        found.scalar_one_or_none.return_value = existing
        session.execute.return_value = found

        result = await PaymentService.create_payment(session, create_request, idempotency_key)

        assert result.payment_id == existing.id
        assert result.status == existing.status
        session.add.assert_not_called()
        session.commit.assert_not_called()


class TestGetPayment:
    async def test_returns_payment_detail(self, session):
        payment = _make_payment()

        found = MagicMock()
        found.scalar_one_or_none.return_value = payment
        session.execute.return_value = found

        result = await PaymentService.get_payment(session, payment.id)

        assert result.id == payment.id
        assert result.status == PaymentStatus.PENDING
        assert result.currency == Currency.RUB

    async def test_raises_404_when_not_found(self, session):
        not_found = MagicMock()
        not_found.scalar_one_or_none.return_value = None
        session.execute.return_value = not_found

        with pytest.raises(HTTPException) as exc_info:
            await PaymentService.get_payment(session, uuid4())

        assert exc_info.value.status_code == 404
