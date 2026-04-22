from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.api.deps import get_session
from app.main import app


@pytest.fixture
def mock_session():
    s = AsyncMock()
    s.add = MagicMock()
    return s


@pytest.fixture(autouse=True)
def override_session(mock_session):
    async def fake_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = fake_get_session
    yield
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
async def client():
    with (
        patch("app.main.RabbitBroker") as mock_broker_cls,
        patch("app.main.run_outbox_publisher", new_callable=AsyncMock),
    ):
        mock_broker_cls.return_value = AsyncMock()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            yield c
