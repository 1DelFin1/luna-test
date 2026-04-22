from faststream import FastStream
from faststream.rabbit import RabbitBroker

from app.broker.consumer import router
from app.core.config import settings

broker = RabbitBroker(settings.rabbitmq.URL)
broker.include_router(router)

app = FastStream(broker)
