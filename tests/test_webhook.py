from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.broker.consumer import _send_webhook

PAYLOAD = {"payment_id": "abc", "status": "succeeded"}
URL = "https://example.com/webhook"


def _mock_client(responses):
    """Возвращает контекстный менеджер httpx.AsyncClient с заданными ответами на post()."""
    mock_client = AsyncMock()
    mock_client.post.side_effect = responses

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, mock_client


class TestSendWebhook:
    async def test_success_on_first_attempt(self):
        response = AsyncMock()
        response.raise_for_status = MagicMock()
        ctx, mock_client = _mock_client([response])

        with patch("app.broker.consumer.httpx.AsyncClient", return_value=ctx):
            await _send_webhook(URL, PAYLOAD)

        mock_client.post.assert_called_once_with(URL, json=PAYLOAD, timeout=10.0)

    async def test_retries_on_failure_and_succeeds(self):
        success = AsyncMock()
        success.raise_for_status = MagicMock()
        ctx, mock_client = _mock_client([
            httpx.ConnectError("timeout"),
            success,
        ])

        with patch("app.broker.consumer.httpx.AsyncClient", return_value=ctx):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await _send_webhook(URL, PAYLOAD)

        assert mock_client.post.call_count == 2

    async def test_logs_warning_after_all_attempts_fail(self):
        ctx, mock_client = _mock_client([
            httpx.ConnectError("err"),
            httpx.ConnectError("err"),
            httpx.ConnectError("err"),
        ])

        with patch("app.broker.consumer.httpx.AsyncClient", return_value=ctx):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch("app.broker.consumer.logger") as mock_logger:
                    await _send_webhook(URL, PAYLOAD)

        assert mock_client.post.call_count == 3
        mock_logger.warning.assert_called_once()
