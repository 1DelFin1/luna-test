from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox import OutboxEvent
from app.models.payment import Payment
from app.schemas import CreatePaymentRequest, PaymentCreatedResponse, PaymentDetailResponse


class PaymentService:
    @classmethod
    async def create_payment(
        cls,
        session: AsyncSession,
        body: CreatePaymentRequest,
        idempotency_key: UUID,
    ) -> PaymentCreatedResponse:
        result = await session.execute(
            select(Payment).where(Payment.idempotency_key == idempotency_key)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return PaymentCreatedResponse(
                payment_id=existing.id,
                status=existing.status,
                created_at=existing.created_at,
            )

        payment = Payment(
            total=body.total,
            currency=body.currency,
            description=body.description,
            meta=body.meta,
            webhook_url=body.webhook_url,
            idempotency_key=idempotency_key,
        )
        session.add(payment)

        outbox_event = OutboxEvent(
            event_type="payment.created",
            payload={
                "payment_id": str(payment.id),
                "webhook_url": body.webhook_url,
            },
        )
        session.add(outbox_event)

        await session.commit()
        await session.refresh(payment)

        return PaymentCreatedResponse(
            payment_id=payment.id,
            status=payment.status,
            created_at=payment.created_at,
        )

    @classmethod
    async def get_payment(cls, session: AsyncSession, payment_id: UUID) -> PaymentDetailResponse:
        result = await session.execute(select(Payment).where(Payment.id == payment_id))
        payment = result.scalar_one_or_none()
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        return PaymentDetailResponse.model_validate(payment)
