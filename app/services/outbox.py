import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.broker.setup import PAYMENTS_EXCHANGE
from app.models.outbox import OutboxEvent

logger = logging.getLogger(__name__)

POLL_INTERVAL = 1  # seconds


async def _publish_pending(session: AsyncSession, broker) -> None:
    result = await session.execute(
        select(OutboxEvent)
        .where(OutboxEvent.processed_at.is_(None))
        .with_for_update(skip_locked=True)
        .limit(10)
    )
    events = result.scalars().all()

    for event in events:
        try:
            await broker.publish(
                event.payload,
                exchange=PAYMENTS_EXCHANGE,
                routing_key="payments.new",
            )
            event.processed_at = datetime.now(timezone.utc)
        except Exception as exc:
            logger.error("Failed to publish outbox event %s: %s", event.id, exc)

    if events:
        await session.commit()


async def run_outbox_publisher(broker) -> None:
    from app.core.database import async_session_factory

    logger.info("Outbox publisher started")
    while True:
        try:
            async with async_session_factory() as session:
                await _publish_pending(session, broker)
        except Exception as exc:
            logger.error("Outbox publisher error: %s", exc)
        await asyncio.sleep(POLL_INTERVAL)
