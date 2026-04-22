from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.api.deps import verify_api_key
from app.main import app
from app.models.payment import Currency, Payment, PaymentStatus

FIXED_ID = uuid4()
FIXED_TIME = datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc)

PAYMENT_BODY = {
    "total": "500.00",
    "currency": "RUB",
    "description": "Test payment",
    "meta": {"order_id": 1},
    "webhook_url": "https://example.com/webhook",
}


def make_payment(**kwargs) -> Payment:
    p = Payment(
        id=FIXED_ID,
        total=Decimal("500.00"),
        currency=Currency.RUB,
        description="Test payment",
        meta={"order_id": 1},
        webhook_url="https://example.com/webhook",
        idempotency_key=uuid4(),
        status=PaymentStatus.PENDING,
        **kwargs,
    )
    p.created_at = FIXED_TIME
    p.updated_at = FIXED_TIME
    p.processed_at = None
    return p


@pytest.fixture
def bypass_auth():
    app.dependency_overrides[verify_api_key] = lambda: None
    yield
    app.dependency_overrides.pop(verify_api_key, None)


class TestCreatePayment:
    async def test_returns_202_and_payment_id(self, client, mock_session, bypass_auth):
        no_result = MagicMock()
        no_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = no_result

        async def fake_refresh(obj):
            obj.status = PaymentStatus.PENDING
            obj.created_at = FIXED_TIME
            obj.updated_at = FIXED_TIME

        mock_session.refresh.side_effect = fake_refresh

        response = await client.post(
            "/api/v1/payments",
            json=PAYMENT_BODY,
            headers={"Idempotency-Key": str(uuid4())},
        )

        assert response.status_code == 202
        data = response.json()
        assert "payment_id" in data
        assert data["status"] == "pending"
        assert "created_at" in data

    async def test_idempotency_returns_same_payment(self, client, mock_session, bypass_auth):
        existing = make_payment()
        found = MagicMock()
        found.scalar_one_or_none.return_value = existing
        mock_session.execute.return_value = found

        idempotency_key = str(uuid4())
        headers = {"Idempotency-Key": idempotency_key}

        resp1 = await client.post("/api/v1/payments", json=PAYMENT_BODY, headers=headers)
        resp2 = await client.post("/api/v1/payments", json=PAYMENT_BODY, headers=headers)

        assert resp1.status_code == resp2.status_code == 202
        assert resp1.json()["payment_id"] == resp2.json()["payment_id"]
        mock_session.commit.assert_not_called()

    async def test_missing_api_key_returns_401(self, client):
        response = await client.post(
            "/api/v1/payments",
            json=PAYMENT_BODY,
            headers={"Idempotency-Key": str(uuid4())},
        )

        assert response.status_code == 401

    async def test_missing_idempotency_key_returns_422(self, client, bypass_auth):
        response = await client.post("/api/v1/payments", json=PAYMENT_BODY)

        assert response.status_code == 422

    async def test_invalid_currency_returns_422(self, client, bypass_auth):
        response = await client.post(
            "/api/v1/payments",
            json={**PAYMENT_BODY, "currency": "GBP"},
            headers={"Idempotency-Key": str(uuid4())},
        )

        assert response.status_code == 422


class TestGetPayment:
    async def test_returns_200_with_full_details(self, client, mock_session, bypass_auth):
        payment = make_payment()
        found = MagicMock()
        found.scalar_one_or_none.return_value = payment
        mock_session.execute.return_value = found

        response = await client.get(f"/api/v1/payments/{payment.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(FIXED_ID)
        assert data["status"] == "pending"
        assert data["currency"] == "RUB"
        assert data["total"] == "500.00"

    async def test_returns_404_for_unknown_id(self, client, mock_session, bypass_auth):
        not_found = MagicMock()
        not_found.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = not_found

        response = await client.get(f"/api/v1/payments/{uuid4()}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Payment not found"

    async def test_missing_api_key_returns_401(self, client):
        response = await client.get(f"/api/v1/payments/{uuid4()}")

        assert response.status_code == 401
