# Story 3.2: `POST /v1/chat/completions` Transparent Proxy

Status: ready-for-dev

## Story

As a developer building OpenTalon,
I want the `POST /v1/chat/completions` endpoint implemented as a transparent proxy to OpenRouter,
So that the CLI can send LLM requests that are validated, key-swapped, forwarded, and returned unmodified.

## Acceptance Criteria

**AC1 — Valid key + body forwarded unmodified:**
Given a request with a valid `Authorization: Bearer ot_<key>` header
When `POST /v1/chat/completions` is called with any syntactically valid OpenRouter-compatible body
Then the request body is read as raw bytes and forwarded to OpenRouter unmodified — no JSON parsing, no field validation (satisfies FR12, FR13, FR14, NFR12)

**AC2 — Key swap: user key replaced with server's OpenRouter key:**
Given the proxy forwards the request
When the `Authorization` header is constructed for OpenRouter
Then it contains `Bearer <OPENROUTER_API_KEY>` (the server's env var) — the user's `ot_` key never reaches OpenRouter (satisfies NFR7)

**AC3 — Successful OpenRouter response returned unmodified:**
Given OpenRouter returns a 200 response
When the proxy handler returns
Then the OpenRouter response body, status code, and content-type are returned to the CLI unmodified (satisfies FR14)

**AC4 — OpenRouter error forwarded as uniform error shape:**
Given OpenRouter returns an error (e.g. 429, 502)
When the proxy receives it
Then the CLI receives HTTP 502 with body `{"detail": "Proxy error: <status>"}` (uniform error shape matching FastAPI convention)

**AC5 — Invalid key rejected 401:**
Given a request with an invalid or missing `Authorization` header
When `POST /v1/chat/completions` is called
Then the existing `verify_api_key` dependency rejects it with HTTP 401 before the body is read or forwarded

**AC6 — Tests pass:**
Given tests are run
When `uv run pytest` is executed from `api/`
Then tests pass for: valid key + body forwarded, invalid key rejected (401), raw bytes forwarded (no body parsing), OpenRouter error propagation — all using `httpx` mock

## Tasks / Subtasks

- [ ] Task 1: Add `httpx` to API dependencies
  - [ ] `uv add httpx` from `api/` directory
  - [ ] Verify `api/pyproject.toml` now lists `httpx`

- [ ] Task 2: Write tests FIRST in `tests/test_proxy.py` — confirm they fail (TDD)
  - [ ] Tests for AC1–AC5 all fail before `routers/proxy.py` exists
  - [ ] Mock `httpx.AsyncClient` as async context manager (same pattern as Story 2.6)
  - [ ] Override `verify_api_key` dependency to bypass bcrypt in tests

- [ ] Task 3: Create `api/src/opentaion_api/routers/proxy.py` (AC: 1–4)
  - [ ] `POST /v1/chat/completions` route with `Depends(verify_api_key)`
  - [ ] Read `body = await request.body()` — raw bytes only
  - [ ] Swap auth header using `os.environ["OPENROUTER_API_KEY"]`
  - [ ] Forward to `https://openrouter.ai/api/v1/chat/completions`
  - [ ] Return `Response(content=..., status_code=..., media_type=...)` on success
  - [ ] Raise `HTTPException(502, "Proxy error: <status>")` on OpenRouter error

- [ ] Task 4: Register proxy router in `main.py` (AC: 1)
  - [ ] `from opentaion_api.routers import proxy`
  - [ ] `app.include_router(proxy.router)` (no prefix — endpoint is `/v1/chat/completions`)

- [ ] Task 5: Run tests green (AC: 6)
  - [ ] `uv run pytest tests/test_proxy.py -v`
  - [ ] `uv run pytest` — full suite passes (test_auth.py + test_keys.py + test_cost.py + test_proxy.py)

## Dev Notes

### Prerequisite: Story 2.1 Must Be Complete

`api/src/opentaion_api/dependencies/auth.py` must exist with `verify_api_key` implemented.
`api/src/opentaion_api/dependencies/db.py` must exist with `get_db`.
Story 3.2 imports `verify_api_key` directly — the proxy authenticates via the existing dependency.

### New Dependency: `httpx`

The API uses `httpx.AsyncClient` to forward requests to OpenRouter. This is a **runtime** dependency, not just a test dependency.

```bash
cd api
uv add httpx
```

Note: `fastapi[standard]` does NOT include `httpx`. Without this step, importing from `httpx` in `routers/proxy.py` raises `ModuleNotFoundError` at startup.

### `routers/proxy.py` — Full Implementation

```python
# api/src/opentaion_api/routers/proxy.py
import os
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from opentaion_api.dependencies.auth import verify_api_key

router = APIRouter()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# httpx timeout: 5s connect (catches Railway cold start), 120s read (reasoning models)
PROXY_TIMEOUT = httpx.Timeout(connect=5.0, read=120.0)


@router.post("/v1/chat/completions")
async def proxy_chat_completions(
    request: Request,
    user_id: uuid.UUID = Depends(verify_api_key),
) -> Response:
    """Transparent proxy to OpenRouter.

    Reads raw request body (never parsed — NFR12) and forwards it to OpenRouter
    with the user's ot_ key swapped for the server's OPENROUTER_API_KEY (NFR7).
    Returns OpenRouter's response unmodified on success (FR14).
    Usage logging is added in Story 3.3 as a BackgroundTask.
    """
    openrouter_api_key = os.environ["OPENROUTER_API_KEY"]
    body = await request.body()  # raw bytes — never JSON-parsed (NFR12)

    async with httpx.AsyncClient() as client:
        openrouter_response = await client.post(
            OPENROUTER_URL,
            content=body,
            headers={
                "Authorization": f"Bearer {openrouter_api_key}",
                "Content-Type": request.headers.get("Content-Type", "application/json"),
            },
            timeout=PROXY_TIMEOUT,
        )

    if openrouter_response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Proxy error: {openrouter_response.status_code}",
        )

    return Response(
        content=openrouter_response.content,
        status_code=openrouter_response.status_code,
        media_type=openrouter_response.headers.get("content-type", "application/json"),
    )
```

**Why no `db` or `background_tasks` parameter yet?**
Story 3.3 adds usage logging. This story does only proxy mechanics. Story 3.3 will modify this function to add `background_tasks: BackgroundTasks` and `db: AsyncSession = Depends(get_db)` parameters. Keeping them separate makes each story's diff minimal and reviewable.

**Why `os.environ["OPENROUTER_API_KEY"]` (not `os.getenv()`)?**
`os.environ["OPENROUTER_API_KEY"]` raises `KeyError` at request time if the env var is missing. This is a loud, obvious failure that surfaces misconfiguration immediately. `os.getenv("OPENROUTER_API_KEY")` returns `None` silently — then the request goes to OpenRouter with `Authorization: Bearer None` and returns a confusing 401. Fail loudly on missing config.

**Why `Response(content=..., status_code=...)` instead of `JSONResponse`?**
`JSONResponse` would re-parse `openrouter_response.content` as JSON and re-serialize it, potentially altering the response. `Response` passes `content` (bytes) through directly with the original `content-type`. This is the only way to guarantee NFR12 compliance (pass-through without modification).

**Why `httpx.Timeout(connect=5.0, read=120.0)` not `timeout=5.0`?**
`timeout=5.0` applies 5 seconds to the entire request including the read. DeepSeek R1 (the `low` tier reasoning model) can take up to 60–90 seconds to respond. With `timeout=5.0`, every long reasoning task would time out. Splitting connect/read gives:
- `connect=5.0`: catches Railway cold start / unreachable proxy quickly
- `read=120.0`: gives reasoning models full time to respond

### Updated `main.py`

Add one import and one `include_router` call after the existing keys router:

```python
# api/src/opentaion_api/main.py
# ... existing imports ...
from opentaion_api.routers import keys, proxy

# ... existing app setup, CORS, health endpoint ...

app.include_router(keys.router, prefix="/api")
app.include_router(proxy.router)  # no prefix — endpoint is /v1/chat/completions
```

**Note on `/health` endpoint:** Story 1.2 placed `GET /health` directly in `main.py`. The architecture doc lists `/health` under `proxy.py`, but since it's already implemented and tested in `main.py`, do NOT move it. Moving it would break Story 1.2's implementation and change the route behavior with no benefit. Leave it in `main.py`.

### Tests — `tests/test_proxy.py`

Write BEFORE implementing `routers/proxy.py`. All tests fail initially (import error from missing module).

```python
# tests/test_proxy.py
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from opentaion_api.main import app
from opentaion_api.dependencies.auth import verify_api_key


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
    mock_response.content = b'{"choices": [{"message": {"content": "hello"}}]}'
    mock_response.headers = {"content-type": "application/json"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


@pytest.fixture
def mock_openrouter_error(status_code: int = 429):
    """Mock httpx.AsyncClient for an OpenRouter error response."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.content = b'{"error": "rate limit exceeded"}'
    mock_response.headers = {"content-type": "application/json"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


# ── Success path ───────────────────────────────────────────────────────────────

@pytest.mark.anyio
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


@pytest.mark.anyio
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


@pytest.mark.anyio
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

@pytest.mark.anyio
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


@pytest.mark.anyio
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


@pytest.mark.anyio
async def test_proxy_invalid_key_rejected_401():
    """Remove auth override to test real 401 rejection."""
    app.dependency_overrides.clear()  # use real verify_api_key
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            content=b'{"model": "deepseek/deepseek-r1:free", "messages": []}',
            headers={"Authorization": "Bearer not-an-ot-key"},
        )
    assert response.status_code == 401
    # Restore override for remaining tests in the session
    app.dependency_overrides[verify_api_key] = lambda: TEST_USER_ID
```

### `conftest.py` for Async Tests

If `api/tests/conftest.py` does not already have `anyio_backend` configured, add it:

```python
# api/tests/conftest.py (add if not already present)
import pytest

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
```

And ensure `anyio` is a dev dependency:
```bash
cd api
uv add --dev anyio pytest-anyio
# or verify fastapi[standard] already includes anyio
```

**Why `pytest-anyio` / `@pytest.mark.anyio` not `asyncio.run()`?**
`pytest-anyio` (from `anyio`) is the recommended way to run async tests with FastAPI's `ASGITransport`. `asyncio.run()` works but requires wrapping every test in a sync function. `@pytest.mark.anyio` is cleaner and consistent with FastAPI's own test documentation.

**Why `ASGITransport` not `TestClient`?**
`httpx.TestClient` (sync) can't test async routes properly in all cases. `ASGITransport` with `httpx.AsyncClient` is the FastAPI-recommended async testing approach and handles async dependencies correctly.

### Anti-Pattern: Do NOT Parse the Request Body

```python
# ❌ WRONG — parses body as JSON, rejects unknown OpenRouter fields (violates NFR12)
data = await request.json()
validated = SomeSchema(**data)
body = json.dumps(validated.dict()).encode()

# ✅ CORRECT — raw bytes, pass-through (satisfies NFR12)
body = await request.body()
```

NFR12 requires the proxy to accept "any syntactically valid OpenRouter-compatible request body without modification." OpenRouter frequently adds new parameters. Any JSON parsing on the proxy side would silently strip fields it doesn't know about.

### Anti-Pattern: Do NOT Use `JSONResponse` for the Proxy Return

```python
# ❌ WRONG — re-parses bytes as JSON, may alter whitespace/ordering
return JSONResponse(content=json.loads(openrouter_response.content))

# ✅ CORRECT — passes raw bytes through with original content-type
return Response(
    content=openrouter_response.content,
    status_code=openrouter_response.status_code,
    media_type=openrouter_response.headers.get("content-type", "application/json"),
)
```

### Architecture Cross-References

From `architecture.md`:
- `POST /v1/chat/completions` auth dependency: `verify_api_key` [Source: architecture.md#API Contract]
- Body forwarded as raw bytes — never parsed (NFR12) [Source: architecture.md#Implementation Patterns rule 7]
- `OPENROUTER_API_KEY` swap — user key never reaches OpenRouter (NFR7) [Source: architecture.md#API Contract]
- Usage logging via `BackgroundTasks` added in Story 3.3 [Source: architecture.md#Implementation Patterns rule 6]
- `httpx.Timeout(connect=5.0, read=120.0)` [Source: architecture.md#Gaps Resolved]
- `raise HTTPException` — never return error dicts [Source: architecture.md#Implementation Patterns rule 4]
- Proxy overhead < 200ms (NFR1) — architecture achieves this via async pattern [Source: architecture.md#NFR]

From `epics.md`:
- FR12: "The proxy validates the developer's OpenTalon API key on every incoming request" [Source: epics.md#FR12]
- FR13: "The proxy forwards LLM requests to OpenRouter using the server's master OpenRouter API key" [Source: epics.md#FR13]
- FR14: "The proxy returns the OpenRouter response to the CLI without modification" [Source: epics.md#FR14]
- NFR7: "The master OpenRouter API key must be stored exclusively as a server-side environment variable" [Source: epics.md#NFR7]
- NFR12: "The API must not reject requests based on unrecognized fields" [Source: epics.md#NFR12]

### What This Story Does NOT Include

- Usage logging (`BackgroundTasks` write to `usage_logs`) — that is Story 3.3
- `BackgroundTasks` or `db: AsyncSession` parameters on the route — Story 3.3 adds them
- `GET /health` — already in `main.py` from Story 1.2; do NOT move it
- `EFFORT_MODELS` routing — the proxy forwards any model ID in the request body; the CLI sends the model ID; the proxy doesn't filter or route by tier
- Streaming responses — V1 is non-streaming; no SSE or chunked transfer handling needed
- CLI retry logic — that is Story 3.5

### Railway Environment Variables Required

Before the proxy can forward requests in production, set in Railway:
```
OPENROUTER_API_KEY=sk-or-v1-...   # from openrouter.ai/keys
```

Without this env var, the proxy raises `KeyError: 'OPENROUTER_API_KEY'` on every request.

### Final Modified/Created Files

```
api/
├── pyproject.toml              ← MODIFIED — add httpx dependency
└── src/opentaion_api/
    ├── main.py                 ← MODIFIED — app.include_router(proxy.router)
    └── routers/
        └── proxy.py            ← NEW — POST /v1/chat/completions transparent proxy
tests/
└── test_proxy.py               ← NEW — proxy endpoint tests with httpx mock
```

## Dev Agent Record

### Agent Model Used

_to be filled by dev agent_

### Debug Log References

_none_

### Completion Notes List

_to be filled by dev agent_

### File List

_to be filled by dev agent_
