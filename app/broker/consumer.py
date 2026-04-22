import asyncio
import logging
import random
from datetime import datetime, timezone

import httpx
from faststream.rabbit import RabbitRouter
from sqlalchemy import select

from app.broker.setup import PAYMENTS_EXCHANGE, PAYMENTS_QUEUE, DLX, DLQ
from app.core.database import async_session_factory
from app.models.payment import Payment, PaymentStatus
from app.schemas import PaymentEvent

logger = logging.getLogger(__name__)

router = RabbitRouter()


async def _send_webhook(url: str, payload: dict) -> None:
    async with httpx.AsyncClient() as client:
        for attempt in range(3):
            try:
                resp = await client.post(url, json=payload, timeout=10.0)
                resp.raise_for_status()
                return
            except Exception as exc:
                if attempt < 2:
                    await asyncio.sleep(2**attempt)
                else:
                    logger.warning("Webhook delivery failed after 3 attempts: %s — %s", url, exc)


async def _update_payment_status(
    payment_id, new_status: PaymentStatus, processed_at: datetime
) -> None:
    async with async_session_factory() as session:
        result = await session.execute(select(Payment).where(Payment.id == payment_id))
        payment = result.scalar_one_or_none()
        if payment:
            payment.status = new_status
            payment.processed_at = processed_at
            await session.commit()


@router.subscriber(PAYMENTS_QUEUE, PAYMENTS_EXCHANGE)
@router.subscriber(DLQ, DLX)
async def handle_payment(event: PaymentEvent) -> None:
    async with async_session_factory() as session:
        result = await session.execute(select(Payment).where(Payment.id == event.payment_id))
        payment = result.scalar_one_or_none()

    if payment is None:
        logger.error("Payment %s not found", event.payment_id)
        return

    if payment.status != PaymentStatus.PENDING:
        logger.info("Payment %s already processed, skipping", event.payment_id)
        return

    last_exc = None
    succeeded = False

    for attempt in range(3):
        try:
            await asyncio.sleep(random.uniform(2, 5))
            if random.random() < 0.1:
                raise RuntimeError("Simulated processing failure")
            succeeded = True
            break
        except Exception as exc:
            last_exc = exc
            logger.warning("Attempt %d failed for payment %s: %s", attempt + 1, event.payment_id, exc)
            if attempt < 2:
                await asyncio.sleep(2**attempt)

    processed_at = datetime.now(timezone.utc)

    if succeeded:
        await _update_payment_status(event.payment_id, PaymentStatus.SUCCEEDED, processed_at)
        await _send_webhook(event.webhook_url, {
            "payment_id": str(event.payment_id),
            "status": "succeeded",
            "processed_at": processed_at.isoformat(),
        })
    else:
        await _update_payment_status(event.payment_id, PaymentStatus.FAILED, processed_at)
        await _send_webhook(event.webhook_url, {
            "payment_id": str(event.payment_id),
            "status": "failed",
            "processed_at": processed_at.isoformat(),
        })
        raise last_exc
