from faststream.rabbit import RabbitExchange, RabbitQueue, ExchangeType
from faststream.rabbit.schemas.queue import ClassicQueueArgs

PAYMENTS_EXCHANGE = RabbitExchange("payments", type=ExchangeType.DIRECT, durable=True)
DLX = RabbitExchange("payments.dlx", type=ExchangeType.DIRECT, durable=True)

PAYMENTS_QUEUE = RabbitQueue(
    "payments.new",
    durable=True,
    routing_key="payments.new",
    arguments=ClassicQueueArgs(**{
        "x-dead-letter-exchange": "payments.dlx",
        "x-dead-letter-routing-key": "payments.new.dlq",
    }),
)
DLQ = RabbitQueue("payments.new.dlq", durable=True, routing_key="payments.new.dlq")
