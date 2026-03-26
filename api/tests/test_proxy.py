# tests/test_proxy.py
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from opentaion_api.main import app
from opentaion_api.deps import verify_api_key


# ── Test fixtures ──────────────────────────────────────────────────────────────

TEST_USER_ID = uuid.uuid4()


@pytest.fixture(autouse=True)
def override_auth():
    """Bypass bcrypt key validation — return a fixed user_id for all proxy tests."""
    app.dependency_overrides[verify_api_key] = lambda: TEST_USER_ID
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_openrouter_success():
    """Mock httpx.AsyncClient for a successful OpenRouter response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b'{"model": "deepseek/deepseek-r1:free", "choices": [{"message": {"content": "hello"}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}'
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json = MagicMock(return_value={
        "model": "deepseek/deepseek-r1:free",
        "choices": [{"message": {"content": "hello"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    })

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


# ── Success path ───────────────────────────────────────────────────────────────

async def test_proxy_returns_openrouter_response(mock_openrouter_success, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    with patch("opentaion_api.routers.proxy.httpx.AsyncClient", return_value=mock_openrouter_success):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                content=b'{"model": "deepseek/deepseek-r1:free", "messages": []}',
                headers={"Authorization": "Bearer ot_testkey", "Content-Type": "application/json"},
            )
    assert response.status_code == 200
    assert b"choices" in response.content


async def test_proxy_forwards_raw_bytes_unmodified(mock_openrouter_success, monkeypatch):
    """Verify body forwarded as raw bytes — AsyncClient.post called with content= not json=."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    raw_body = b'{"model": "deepseek/deepseek-r1:free", "messages": [], "unknown_field": true}'

    with patch("opentaion_api.routers.proxy.httpx.AsyncClient", return_value=mock_openrouter_success):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                "/v1/chat/completions",
                content=raw_body,
                headers={"Authorization": "Bearer ot_testkey", "Content-Type": "application/json"},
            )

    # Verify OpenRouter was called with raw bytes via content= kwarg
    call_kwargs = mock_openrouter_success.post.call_args
    assert call_kwargs.kwargs.get("content") == raw_body


async def test_proxy_swaps_auth_header(mock_openrouter_success, monkeypatch):
    """Verify the user's ot_ key is replaced with OPENROUTER_API_KEY."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-secretmasterkey")
    with patch("opentaion_api.routers.proxy.httpx.AsyncClient", return_value=mock_openrouter_success):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                "/v1/chat/completions",
                content=b'{"model": "deepseek/deepseek-r1:free", "messages": []}',
                headers={"Authorization": "Bearer ot_userapikey", "Content-Type": "application/json"},
            )

    call_headers = mock_openrouter_success.post.call_args.kwargs.get("headers", {})
    assert call_headers["Authorization"] == "Bearer sk-or-v1-secretmasterkey"
    assert "ot_userapikey" not in str(call_headers)


# ── Error paths ────────────────────────────────────────────────────────────────

async def test_proxy_openrouter_429_returns_502(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.content = b'{"error": "rate limit"}'
    mock_response.headers = {"content-type": "application/json"}
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("opentaion_api.routers.proxy.httpx.AsyncClient", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                content=b'{"model": "deepseek/deepseek-r1:free", "messages": []}',
                headers={"Authorization": "Bearer ot_testkey"},
            )
    assert response.status_code == 502
    assert "Proxy error: 429" in response.json()["detail"]


async def test_proxy_openrouter_502_returns_502(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 502
    mock_response.content = b'{"error": "bad gateway"}'
    mock_response.headers = {"content-type": "application/json"}
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("opentaion_api.routers.proxy.httpx.AsyncClient", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                content=b'{"model": "deepseek/deepseek-r1:free", "messages": []}',
                headers={"Authorization": "Bearer ot_testkey"},
            )
    assert response.status_code == 502


async def test_proxy_invalid_key_rejected_401():
    """Remove auth override to test real 401 rejection."""
    app.dependency_overrides.clear()  # use real verify_api_key
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                content=b'{"model": "deepseek/deepseek-r1:free", "messages": []}',
                headers={"Authorization": "Bearer not-an-ot-key"},
            )
        assert response.status_code == 401
    finally:
        app.dependency_overrides[verify_api_key] = lambda: TEST_USER_ID


# ── Background task integration ────────────────────────────────────────────────

async def test_proxy_success_enqueues_usage_log(mock_openrouter_success, monkeypatch):
    """Verify write_usage_log is called as background task with correct args."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    with patch("opentaion_api.routers.proxy.httpx.AsyncClient", return_value=mock_openrouter_success):
        with patch("opentaion_api.routers.proxy.write_usage_log") as mock_write:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/v1/chat/completions",
                    content=b'{"model": "deepseek/deepseek-r1:free", "messages": []}',
                    headers={"Authorization": "Bearer ot_testkey"},
                )
    assert response.status_code == 200
    mock_write.assert_called_once()
    call_args = mock_write.call_args
    assert call_args[0][0] == TEST_USER_ID  # user_id
    assert call_args[0][1] == "deepseek/deepseek-r1:free"  # model
    assert call_args[0][2] == 10  # prompt_tokens
    assert call_args[0][3] == 5  # completion_tokens


async def test_proxy_error_does_not_enqueue_usage_log(monkeypatch):
    """On OpenRouter error, background task must NOT be enqueued."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.content = b'{"error": "rate limit"}'
    mock_response.headers = {"content-type": "application/json"}
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("opentaion_api.routers.proxy.httpx.AsyncClient", return_value=mock_client):
        with patch("opentaion_api.routers.proxy.write_usage_log") as mock_write:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/v1/chat/completions",
                    content=b'{"model": "deepseek/deepseek-r1:free", "messages": []}',
                    headers={"Authorization": "Bearer ot_testkey"},
                )
    assert response.status_code == 502
    mock_write.assert_not_called()
