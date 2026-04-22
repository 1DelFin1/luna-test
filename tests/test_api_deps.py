from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.api.deps import verify_api_key


class TestVerifyApiKey:
    async def test_valid_key_passes(self):
        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.api_key = "correct-key"
            await verify_api_key("correct-key")  # не должно бросить исключение

    async def test_invalid_key_raises_403(self):
        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.api_key = "correct-key"

            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key("wrong-key")

            assert exc_info.value.status_code == 403

    async def test_empty_key_raises_403(self):
        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.api_key = "correct-key"

            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key("")

            assert exc_info.value.status_code == 403
