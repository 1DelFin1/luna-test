# Payment Service

FastAPI сервис для обработки платежей с гарантированной доставкой через RabbitMQ (Outbox pattern).

## Стек

- **FastAPI** + Pydantic v2
- **SQLAlchemy 2.0** (async) + **asyncpg**
- **PostgreSQL 17**
- **RabbitMQ 3.13** + **FastStream**
- **Alembic** (миграции)
- **httpx** (отправка webhook)
- **pytest** + **pytest-asyncio** (тесты)
- **Docker** + docker-compose

## Структура проекта

```
app/
├── api/
│   ├── deps.py              # зависимости: сессия БД, API-key аутентификация
│   └── routers/
│       └── payment.py       # эндпоинты
├── broker/
│   ├── consumer.py          # FastStream consumer: обработка, webhook, DLQ
│   └── setup.py             # exchanges и очереди RabbitMQ
├── core/
│   ├── config.py            # настройки через pydantic-settings
│   └── database.py          # async engine и session factory
├── models/
│   ├── payment.py           # модель Payment (enums Currency, PaymentStatus)
│   └── outbox.py            # модель OutboxEvent
├── services/
│   ├── payment.py           # бизнес-логика создания и получения платежа
│   └── outbox.py            # фоновый publisher: outbox → RabbitMQ
├── main.py                  # FastAPI app, lifespan (broker + outbox publisher)
└── worker.py                # FastStream точка входа для воркера
migrations/                  # Alembic миграции
tests/
├── conftest.py              # shared фикстуры (mock_session, client)
├── test_payment_service.py  # unit-тесты сервисного слоя
├── test_api_deps.py         # unit-тесты аутентификации
├── test_webhook.py          # unit-тесты отправки webhook
└── test_endpoints.py        # интеграционные тесты через ASGI
```

## Запуск

```bash
# Настроить переменные окружения
cp .env.example .env  # заполнить значения

# Собрать и запустить все сервисы
docker compose up --build
```

Порядок запуска через `depends_on`:
1. `db` + `rabbitmq` — ждут healthcheck
2. `migrate` — применяет `alembic upgrade head`
3. `server` + `worker` — стартуют после успешных миграций

## Переменные окружения

| Переменная | Описание | По умолчанию |
|---|---|---|
| `POSTGRES_DB__HOST` | Хост PostgreSQL | `db` |
| `POSTGRES_DB__PORT` | Порт | `5432` |
| `POSTGRES_DB__DATABASE` | Имя БД | — |
| `POSTGRES_DB__USERNAME` | Пользователь | — |
| `POSTGRES_DB__PASSWORD` | Пароль | — |
| `RABBITMQ__HOST` | Хост RabbitMQ | `rabbitmq` |
| `RABBITMQ__PORT` | Порт AMQP | `5672` |
| `RABBITMQ__USERNAME` | Пользователь | `guest` |
| `RABBITMQ__PASSWORD` | Пароль | `guest` |
| `API_KEY` | Статический ключ аутентификации | — |

## API

Все запросы требуют заголовок `X-API-Key`. Отсутствие ключа → `401`.

### POST /api/v1/payments — создать платёж

```http
POST /api/v1/payments
X-API-Key: secret
Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
Content-Type: application/json

{
  "total": "1500.00",
  "currency": "RUB",
  "description": "Оплата заказа #42",
  "meta": {"order_id": 42},
  "webhook_url": "https://example.com/webhook"
}
```

Ответ `202 Accepted`:
```json
{
  "payment_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "pending",
  "created_at": "2026-04-22T12:00:00Z"
}
```

Повторный запрос с тем же `Idempotency-Key` возвращает тот же ответ без создания дубля.

Допустимые валюты: `RUB`, `USD`, `EUR`. Неверная валюта → `422`.

### GET /api/v1/payments/{payment_id} — получить платёж

```http
GET /api/v1/payments/123e4567-e89b-12d3-a456-426614174000
X-API-Key: secret
```

Ответ `200 OK`:
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "total": "1500.00",
  "currency": "RUB",
  "description": "Оплата заказа #42",
  "meta": {"order_id": 42},
  "status": "succeeded",
  "idempotency_key": "550e8400-e29b-41d4-a716-446655440000",
  "webhook_url": "https://example.com/webhook",
  "created_at": "2026-04-22T12:00:00Z",
  "updated_at": "2026-04-22T12:00:05Z",
  "processed_at": "2026-04-22T12:00:04Z"
}
```

Неизвестный `payment_id` → `404`.

## Архитектура

### Outbox Pattern

Гарантирует, что событие в RabbitMQ будет опубликовано даже при сбое брокера:

1. `POST /payments` сохраняет `Payment` и `OutboxEvent` **в одной транзакции**.
2. Фоновый цикл в API-процессе каждую секунду читает необработанные события (`SELECT ... FOR UPDATE SKIP LOCKED`) и публикует в RabbitMQ.
3. После успешной публикации проставляет `processed_at` в `OutboxEvent`.

### Consumer (worker)

- Подписан на `payments.new` (exchange `payments`, type `direct`, durable).
- До **3 попыток** с экспоненциальной задержкой (1 с → 2 с).
- Симулирует обработку 2–5 сек: 90% успех, 10% ошибка.
- Проверяет идемпотентность: пропускает платёж, если статус уже не `pending`.
- После обработки обновляет статус в БД (`succeeded` / `failed`) и отправляет webhook.

### Webhook

- 3 попытки с экспоненциальной задержкой (1 с → 2 с).
- Сбой всех попыток логируется и не прерывает обработку платежа.

Payload:
```json
{
  "payment_id": "123e4567-...",
  "status": "succeeded",
  "processed_at": "2026-04-22T12:00:04Z"
}
```

### Dead Letter Queue

| Ресурс | Имя |
|---|---|
| Main exchange | `payments` |
| Main queue | `payments.new` |
| Dead letter exchange | `payments.dlx` |
| Dead letter queue | `payments.new.dlq` |

Если consumer бросает исключение после всех попыток → nack → RabbitMQ перекладывает сообщение в `payments.new.dlq` через `payments.dlx`. DLQ-consumer логирует сообщения для ручного разбора.

### RabbitMQ Management UI

`http://localhost:15672` — логин `guest` / `guest` (или значения из `.env`).

## Тесты

```bash
# Запустить все тесты
uv run pytest tests/ -v

# Только unit-тесты
uv run pytest tests/ -v -k "not test_endpoints"

# Только интеграционные
uv run pytest tests/test_endpoints.py -v
```

Тесты не требуют запущенных PostgreSQL или RabbitMQ — все внешние зависимости замокированы.
