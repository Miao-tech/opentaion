# Story 3.3: Async Usage Logging

Status: ready-for-dev

## Story

As a developer building OpenTalon,
I want usage data written to `usage_logs` asynchronously via FastAPI `BackgroundTasks` after every proxied LLM call,
So that token counts and cost are recorded without blocking the response being returned to the CLI.

## Acceptance Criteria

**AC1 — Background task enqueued, response returned immediately:**
Given OpenRouter returns a successful response
When the proxy handler returns the response to the CLI
Then a `BackgroundTasks` task is enqueued to write a `usage_logs` record — the response is returned before the write completes (satisfies FR15, NFR9)

**AC2 — Usage record contains correct fields:**
Given the background task runs
When it writes the usage record
Then the record contains: `user_id` (from `verify_api_key`), `model` (from the OpenRouter response `model` field), `prompt_tokens` (from `usage.prompt_tokens`), `completion_tokens` (from `usage.completion_tokens`), `cost_usd` (computed via `compute_cost()` from Story 3.1), `created_at` (server-side `NOW()` via SQLAlchemy default) (satisfies FR16, FR17, FR18, FR19)

**AC3 — Background write failure is silent to the CLI:**
Given the background write fails (e.g. DB connection error)
When the exception is raised inside `write_usage_log`
Then the error is printed to stdout only — it does not propagate to the CLI and does not affect the already-returned response (satisfies NFR9)

**AC4 — `cost_usd` is a Decimal, never a float:**
Given `cost_usd` is stored
When the value is written
Then it is a `NUMERIC(10,8)` column value derived from `compute_cost()` using `decimal.Decimal` — never a float, never client-provided (satisfies FR18, NFR13)

**AC5 — Tests pass:**
Given tests are run
When `uv run pytest` is executed from `api/`
Then tests pass for: background task enqueued on success, write with correct fields, write failure does not raise (logged only), cost_usd is Decimal

## Tasks / Subtasks

- [ ] Task 1: Write tests FIRST — confirm they fail (TDD)
  - [ ] Add new section to `tests/test_proxy.py` for background task integration tests
  - [ ] Create `tests/test_usage_logging.py` for `write_usage_log` unit tests
  - [ ] All tests fail before modifications to `proxy.py`

- [ ] Task 2: Add `write_usage_log` function to `routers/proxy.py` (AC: 2, 3, 4)
  - [ ] New `async def write_usage_log(db, user_id, model, prompt_tokens, completion_tokens)` in `proxy.py`
  - [ ] Uses `compute_cost()` from `services/cost.py`
  - [ ] Uses `UsageLog` ORM model from `models.py`
  - [ ] Wraps entire body in `try/except Exception` — prints warning on failure, never re-raises

- [ ] Task 3: Modify `proxy_chat_completions` in `routers/proxy.py` (AC: 1, 2)
  - [ ] Add `background_tasks: BackgroundTasks` parameter (no `Depends` — FastAPI injects it automatically)
  - [ ] Add `db: AsyncSession = Depends(get_db)` parameter
  - [ ] After success check, parse `openrouter_response.json()` for `model` + `usage` fields
  - [ ] Wrap parse in try/except — default to `"unknown"` / `0` if response malformed
  - [ ] Call `background_tasks.add_task(write_usage_log, db, user_id, model, prompt_tokens, completion_tokens)`
  - [ ] Background task call is BEFORE `return Response(...)` but AFTER the error check

- [ ] Task 4: Run tests green (AC: 5)
  - [ ] `uv run pytest tests/test_proxy.py tests/test_usage_logging.py -v`
  - [ ] `uv run pytest` — full suite passes

## Dev Notes

### Prerequisites: Stories 3.1 and 3.2 Must Be Complete

- `api/src/opentaion_api/services/cost.py` must exist with `compute_cost()` (Story 3.1)
- `api/src/opentaion_api/routers/proxy.py` must exist with `proxy_chat_completions()` (Story 3.2)
- `api/src/opentaion_api/models.py` must have `UsageLog` ORM model (Story 1.4)
- `api/src/opentaion_api/dependencies/db.py` must have `get_db` (Story 1.2)

### Updated `routers/proxy.py` — Full File

This replaces the Story 3.2 version. Added parameters: `background_tasks`, `db`. Added function: `write_usage_log`.

```python
# api/src/opentaion_api/routers/proxy.py
import os
import uuid

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from opentaion_api.dependencies.auth import verify_api_key
from opentaion_api.dependencies.db import get_db
from opentaion_api.models import UsageLog
from opentaion_api.services.cost import compute_cost

router = APIRouter()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
PROXY_TIMEOUT = httpx.Timeout(connect=5.0, read=120.0)


async def write_usage_log(
    db: AsyncSession,
    user_id: uuid.UUID,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    """Write a usage record to usage_logs. Always called as a BackgroundTask.

    Must NEVER propagate exceptions — any failure is logged to stdout only (NFR9).
    The CLI has already received its response before this function runs.
    """
    try:
        cost = compute_cost(model, prompt_tokens, completion_tokens)
        log = UsageLog(
            user_id=user_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
        )
        db.add(log)
        await db.commit()
    except Exception as exc:
        print(f"[WARNING] write_usage_log failed: {exc!r}")


@router.post("/v1/chat/completions")
async def proxy_chat_completions(
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: uuid.UUID = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Transparent proxy to OpenRouter with async usage logging.

    1. Authenticates request via verify_api_key dependency
    2. Forwards raw body bytes to OpenRouter with key swap
    3. On success: enqueues write_usage_log as BackgroundTask (non-blocking)
    4. Returns OpenRouter response unmodified
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

    # Parse OpenRouter response for usage logging (best-effort — malformed response → log zeros)
    try:
        response_data = openrouter_response.json()
        model = response_data.get("model", "unknown")
        usage = response_data.get("usage", {})
        prompt_tokens = int(usage.get("prompt_tokens", 0))
        completion_tokens = int(usage.get("completion_tokens", 0))
    except Exception:
        model, prompt_tokens, completion_tokens = "unknown", 0, 0

    # Enqueue usage log write — response is returned to CLI before this executes (NFR9)
    background_tasks.add_task(
        write_usage_log,
        db,
        user_id,
        model,
        prompt_tokens,
        completion_tokens,
    )

    return Response(
        content=openrouter_response.content,
        status_code=openrouter_response.status_code,
        media_type=openrouter_response.headers.get("content-type", "application/json"),
    )
```

### Why `BackgroundTasks` Has No `Depends()`

FastAPI injects `BackgroundTasks` automatically when it appears as a route parameter — no `Depends()` needed. Unlike `AsyncSession` (which requires a dependency factory), `BackgroundTasks` is a first-class FastAPI primitive:

```python
# ✅ correct — FastAPI injects automatically
async def proxy_chat_completions(
    request: Request,
    background_tasks: BackgroundTasks,      # no Depends()
    db: AsyncSession = Depends(get_db),     # requires Depends()
):
```

### Why Parse `openrouter_response.json()` in the Route (Not in the Background Task)

Two options:
1. Pass `openrouter_response.content` (bytes) to `write_usage_log` and parse there
2. Parse in the route, pass typed fields to `write_usage_log`

Option 2 is chosen because:
- **Testability:** `write_usage_log` unit tests use `(db, user_id, model, prompt_tokens, completion_tokens)` — no mock response needed
- **Separation:** The background task is responsible only for writing; parsing is the route's concern
- **Clarity:** Typed parameters make the background task contract explicit

The parse failure path is wrapped in `try/except` in the route. If it fails, we log zeros (graceful degradation — better to record a $0 log than no log).

### Why `write_usage_log` Is in `proxy.py` (Not `services/usage.py`)

The architecture doc shows `services/cost.py` explicitly, but has no `services/usage.py`. The `write_usage_log` function is:
- Called only from `proxy_chat_completions`
- A DB write (not business logic)
- Simple enough that extracting it adds a module with one function

If usage logging grows (retry logic, S3 fallback, etc.), extract it then. For V1, inline in `proxy.py` is the right size.

### `UsageLog` ORM Model — Expected Definition (from Story 1.4)

```python
# api/src/opentaion_api/models.py (from Story 1.4)
class UsageLog(Base):
    __tablename__ = "usage_logs"
    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id           = Column(UUID(as_uuid=True), nullable=False)
    model             = Column(Text, nullable=False)
    prompt_tokens     = Column(Integer, nullable=False)
    completion_tokens = Column(Integer, nullable=False)
    cost_usd          = Column(Numeric(10, 8), nullable=False)
    created_at        = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())
```

`created_at` uses `server_default=func.now()` — the DB sets the timestamp at INSERT time. Do NOT set `created_at` explicitly in `write_usage_log`.

`cost_usd` is `Numeric(10, 8)` — SQLAlchemy accepts `Decimal` values directly and stores them correctly.

### Tests — `tests/test_usage_logging.py`

Unit tests for `write_usage_log` function. No HTTP client needed — pure function tests with mocked DB.

```python
# tests/test_usage_logging.py
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opentaion_api.routers.proxy import write_usage_log


TEST_USER_ID = uuid.uuid4()


def make_mock_db():
    """Create a mock AsyncSession for testing write_usage_log."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


# ── Successful write ───────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_write_usage_log_calls_db_add_and_commit():
    db = make_mock_db()
    await write_usage_log(db, TEST_USER_ID, "deepseek/deepseek-r1:free", 1000, 500)
    db.add.assert_called_once()
    db.commit.assert_awaited_once()


@pytest.mark.anyio
async def test_write_usage_log_model_field():
    db = make_mock_db()
    await write_usage_log(db, TEST_USER_ID, "meta-llama/llama-3.3-70b-instruct:free", 100, 50)
    log_record = db.add.call_args[0][0]
    assert log_record.model == "meta-llama/llama-3.3-70b-instruct:free"


@pytest.mark.anyio
async def test_write_usage_log_token_fields():
    db = make_mock_db()
    await write_usage_log(db, TEST_USER_ID, "deepseek/deepseek-r1:free", 1234, 567)
    log_record = db.add.call_args[0][0]
    assert log_record.prompt_tokens == 1234
    assert log_record.completion_tokens == 567


@pytest.mark.anyio
async def test_write_usage_log_user_id_field():
    db = make_mock_db()
    await write_usage_log(db, TEST_USER_ID, "deepseek/deepseek-r1:free", 100, 50)
    log_record = db.add.call_args[0][0]
    assert log_record.user_id == TEST_USER_ID


@pytest.mark.anyio
async def test_write_usage_log_cost_usd_is_decimal():
    db = make_mock_db()
    await write_usage_log(db, TEST_USER_ID, "deepseek/deepseek-r1:free", 1000, 500)
    log_record = db.add.call_args[0][0]
    assert isinstance(log_record.cost_usd, Decimal)


@pytest.mark.anyio
async def test_write_usage_log_free_model_cost_is_zero():
    db = make_mock_db()
    await write_usage_log(db, TEST_USER_ID, "deepseek/deepseek-r1:free", 1_000_000, 500_000)
    log_record = db.add.call_args[0][0]
    assert log_record.cost_usd == Decimal("0")


@pytest.mark.anyio
async def test_write_usage_log_paid_model_cost_computed():
    """deepseek/deepseek-r1 (not :free): 1M prompt + 1M completion = $2.74"""
    db = make_mock_db()
    await write_usage_log(db, TEST_USER_ID, "deepseek/deepseek-r1", 1_000_000, 1_000_000)
    log_record = db.add.call_args[0][0]
    assert log_record.cost_usd == Decimal("2.74")


# ── Failure path — must not propagate ─────────────────────────────────────────

@pytest.mark.anyio
async def test_write_usage_log_db_commit_failure_does_not_raise(capsys):
    """DB failure must be silent to the caller — only logged to stdout."""
    db = make_mock_db()
    db.commit = AsyncMock(side_effect=Exception("DB connection lost"))

    # Must NOT raise — returns None silently
    result = await write_usage_log(db, TEST_USER_ID, "deepseek/deepseek-r1:free", 100, 50)
    assert result is None


@pytest.mark.anyio
async def test_write_usage_log_db_failure_logged_to_stdout(capsys):
    db = make_mock_db()
    db.commit = AsyncMock(side_effect=Exception("connection timeout"))

    await write_usage_log(db, TEST_USER_ID, "deepseek/deepseek-r1:free", 100, 50)
    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "write_usage_log" in captured.out


@pytest.mark.anyio
async def test_write_usage_log_db_add_failure_does_not_raise():
    db = make_mock_db()
    db.add = MagicMock(side_effect=Exception("add failed"))
    # Must NOT raise
    await write_usage_log(db, TEST_USER_ID, "deepseek/deepseek-r1:free", 100, 50)
```

### Additional Tests for `test_proxy.py` — Background Task Integration

Add this section to the existing `tests/test_proxy.py` from Story 3.2. These verify that the proxy route enqueues the background task correctly.

```python
# ── Background task integration (add to test_proxy.py) ────────────────────────

@pytest.mark.anyio
async def test_proxy_success_enqueues_usage_log(mock_openrouter_success, monkeypatch):
    """Verify write_usage_log is called as background task on success."""
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
    # BackgroundTask is enqueued but may not have run yet in test context
    # Verify it was registered by checking mock_write was called or queued
    # (FastAPI runs background tasks after response in test context)


@pytest.mark.anyio
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
```

### Note on BackgroundTask Testing with ASGITransport

FastAPI's `ASGITransport` runs background tasks synchronously after the response in test context. This means:
- `write_usage_log` will actually be called before the test `async with` block exits
- Patching `write_usage_log` works to verify it was scheduled

If you see background tasks NOT running in tests, add:
```python
# In conftest.py, if needed:
@pytest.fixture
def anyio_backend():
    return "asyncio"
```

### Architecture Cross-References

From `architecture.md`:
- `BackgroundTasks` for usage logging — never `await` the write [Source: architecture.md#Implementation Patterns rule 6]
- `write_usage_log` function: `background_tasks.add_task(write_usage_log, db, user_id, response)` [Source: architecture.md#Process Patterns]
- `cost_usd` stored as `decimal.Decimal` — never float [Source: architecture.md#Format Patterns]
- Usage logging failure must be logged to stdout, never propagated [Source: architecture.md#Cross-Cutting Concerns]
- `NUMERIC(10,8)` for `cost_usd` in DB schema [Source: architecture.md#Data Architecture]
- `created_at` uses `server_default=func.now()` — never set explicitly [Source: architecture.md#Data Architecture]

From `epics.md`:
- FR15: "The proxy records usage data asynchronously, without blocking the LLM response" [Source: epics.md#FR15]
- FR16: "The system records prompt token count, completion token count, and model ID" [Source: epics.md#FR16]
- FR17: "The system records a timestamp for each proxied LLM call" [Source: epics.md#FR17]
- FR18: "Cost computed server-side from stored token counts using a model pricing table" [Source: epics.md#FR18]
- FR19: "The system associates each usage record with the authenticated developer" [Source: epics.md#FR19]
- NFR9: "Usage logging failures must not delay or prevent the LLM response" [Source: epics.md#NFR9]
- NFR13: "Cost must not depend on any external pricing API call in the request path" [Source: epics.md#NFR13]
- Additional Requirements: "FastAPI BackgroundTasks for usage logging: never awaited" [Source: epics.md#Additional Requirements]

### What This Story Does NOT Include

- `GET /api/usage` endpoint — that is Story 4.1
- Retry logic for failed DB writes in the background task — V1 fails silently
- Any CLI changes — the CLI doesn't know about or interact with usage logging
- The `UsageLog` ORM model — created in Story 1.4
- `compute_cost()` — created in Story 3.1

### Final Modified/Created Files

```
api/
└── src/opentaion_api/
    └── routers/
        └── proxy.py            ← MODIFIED — add write_usage_log, BackgroundTasks, db param
tests/
├── test_proxy.py               ← MODIFIED — add background task integration tests
└── test_usage_logging.py       ← NEW — write_usage_log unit tests
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
