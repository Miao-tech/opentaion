# cli/tests/test_llm.py
import pytest
from unittest.mock import AsyncMock, patch
from opentaion.llm import OpenRouterClient

@pytest.mark.asyncio
async def test_openrouter_client_retries_on_429():
    """Client retries up to 3 times when receiving 429 responses."""
    client = OpenRouterClient(api_key="sk-test-key")

    call_count = 0
    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            # Return 429 for first two calls
            mock_response = AsyncMock()
            mock_response.status_code = 429
            mock_response.headers = {"Retry-After": "1"}
            return mock_response
        # Return success on third call
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "response"}}]
        })
        return mock_response

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        response = await client.complete("test prompt")

    assert call_count == 3
    assert response.content == "response"

@pytest.mark.asyncio
async def test_openrouter_client_raises_after_max_retries():
    """Client raises after 3 failed attempts."""
    client = OpenRouterClient(api_key="sk-test-key")

    async def always_429(*args, **kwargs):
        mock_response = AsyncMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "1"}
        return mock_response

    with patch("httpx.AsyncClient.post", side_effect=always_429):
        with pytest.raises(RuntimeError, match="Rate limit exceeded after"):
            await client.complete("test prompt")
