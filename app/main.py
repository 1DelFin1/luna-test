import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from faststream.rabbit import RabbitBroker

from app.api.routers.payment import payment_router
from app.core.config import settings
from app.services.outbox import run_outbox_publisher


@asynccontextmanager
async def lifespan(app: FastAPI):
    broker = RabbitBroker(settings.rabbitmq.URL)
    await broker.connect()

    task = asyncio.create_task(run_outbox_publisher(broker))
    yield
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await broker.close()


app = FastAPI(lifespan=lifespan)
app.include_router(payment_router, prefix="/api/v1")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
