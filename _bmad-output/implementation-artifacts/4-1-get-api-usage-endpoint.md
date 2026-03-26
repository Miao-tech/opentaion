# Story 4.1: `GET /api/usage` Endpoint

Status: done

## Story

As a developer building OpenTalon,
I want the `GET /api/usage` endpoint implemented,
So that the web dashboard can fetch 30 days of my usage records aggregated by model and day in a single request.

## Acceptance Criteria

**AC1 — Authenticated request returns 30-day records:**
Given an authenticated web user (valid Supabase JWT)
When `GET /api/usage` is called
Then the response has shape:
```json
{
  "records": [
    {
      "date": "2026-03-24",
      "model": "meta-llama/llama-3.3-70b-instruct:free",
      "prompt_tokens": 1200,
      "completion_tokens": 800,
      "cost_usd": "0.00000000"
    }
  ],
  "total_cost_usd": "0.00120000",
  "period_days": 30
}
```
(satisfies FR20, FR21)

**AC2 — Index is used and response is fast:**
Given the query runs
When the database is queried
Then it filters using `WHERE user_id = $1 AND created_at >= $2` — this matches the `idx_usage_logs_user_date` index on `(user_id, created_at DESC)` (satisfies NFR2)

**AC3 — Empty result returns valid shape:**
Given the user has no usage records
When `GET /api/usage` is called
Then the response is `{"records": [], "total_cost_usd": "0.00000000", "period_days": 30}` — no error

**AC4 — Monetary values serialized as decimal strings:**
Given all monetary values in the response
When serialized to JSON
Then `cost_usd` (per-record) and `total_cost_usd` are strings with exactly 8 decimal places (e.g. `"0.00120000"`) — never JSON numbers (satisfies architecture rule 2)

**AC5 — Unauthenticated request returns 401:**
Given no `Authorization` header or an invalid JWT
When `GET /api/usage` is called
Then the `verify_supabase_jwt` dependency rejects it with HTTP 401

**AC6 — Tests pass:**
Given tests are run
When `uv run pytest` is executed from `api/`
Then tests pass for: populated 30-day window, empty result, JWT auth required (401 without token), decimal string serialization

## Tasks / Subtasks

- [x] Task 1: Write tests FIRST in `tests/test_usage.py` — confirm they fail (TDD)
  - [x] Tests for AC1–AC5 all fail before implementation

- [x] Task 2: Add `UsageRecord` and `UsageResponse` Pydantic schemas to `schemas.py` (AC: 1, 3, 4)
  - [x] `UsageRecord` with `date: str`, `model: str`, `prompt_tokens: int`, `completion_tokens: int`, `cost_usd: str`
  - [x] `UsageResponse` with `records: list[UsageRecord]`, `total_cost_usd: str`, `period_days: int = 30`
  - [x] `UsageRecord.from_log(log: UsageLog) -> UsageRecord` classmethod for clean conversion

- [x] Task 3: Create `api/src/opentaion_api/routers/usage.py` (AC: 1–5)
  - [x] `GET /usage` route with `Depends(verify_supabase_jwt)` and `Depends(get_db)`
  - [x] Query `usage_logs` for last 30 days filtered by `user_id`
  - [x] Build and return `UsageResponse`

- [x] Task 4: Register usage router in `main.py` (AC: 1)
  - [x] `from opentaion_api.routers import usage`
  - [x] `app.include_router(usage.router, prefix="/api")`

- [x] Task 5: Run tests green (AC: 6)
  - [x] `uv run pytest tests/test_usage.py -v`
  - [x] `uv run pytest` — full suite passes

## Dev Notes

### Prerequisites: Stories 1.4, 2.1 Must Be Complete

- `api/src/opentaion_api/models.py` must have `UsageLog` (Story 1.4)
- `api/src/opentaion_api/dependencies/auth.py` must have `verify_supabase_jwt` (Story 2.1)
- `api/src/opentaion_api/dependencies/db.py` must have `get_db` (Story 1.2)
- `api/src/opentaion_api/schemas.py` must exist (Story 2.2) — add new schemas here

### New Pydantic Schemas in `schemas.py`

Add to the existing `schemas.py` file alongside `ApiKeyCreateResponse` and `ApiKeyListItem`:

```python
# api/src/opentaion_api/schemas.py (additions)
from decimal import Decimal
from datetime import datetime

class UsageRecord(BaseModel):
    """One usage_logs row, date-truncated and cost serialized as string."""
    date: str              # "YYYY-MM-DD" extracted from created_at
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: str          # Decimal serialized as 8-dp string — never float

    @classmethod
    def from_log(cls, log: "UsageLog") -> "UsageRecord":
        return cls(
            date=log.created_at.strftime("%Y-%m-%d"),
            model=log.model,
            prompt_tokens=log.prompt_tokens,
            completion_tokens=log.completion_tokens,
            cost_usd=f"{log.cost_usd:.8f}",
        )


class UsageResponse(BaseModel):
    """Response shape for GET /api/usage."""
    records: list[UsageRecord]
    total_cost_usd: str    # sum of all cost_usd, 8 decimal places
    period_days: int = 30
```

**Why `cost_usd: str` not `cost_usd: Decimal`?**
Pydantic v2 serializes `Decimal` as a JSON number by default (e.g., `0.0012`), which loses trailing zeros and makes the format inconsistent. The architecture spec requires exactly `"0.00120000"` (8 decimal places as a string). Using `str` with `f"{value:.8f}"` formatting is the simplest way to guarantee this. The frontend parses it with `parseFloat(record.cost_usd).toFixed(4)` for display.

**Why `from_log` classmethod instead of `model_validate` / `from_orm`?**
`from_orm` requires `model_config = ConfigDict(from_attributes=True)`, which works for direct ORM column mapping. Here `date` (a string) is derived from `created_at` (a datetime) — this transformation can't be expressed via `from_attributes`. A classmethod with explicit mapping is cleaner and unambiguous.

### `routers/usage.py` — Full Implementation

```python
# api/src/opentaion_api/routers/usage.py
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opentaion_api.dependencies.auth import verify_supabase_jwt
from opentaion_api.dependencies.db import get_db
from opentaion_api.models import UsageLog
from opentaion_api.schemas import UsageRecord, UsageResponse

router = APIRouter()


@router.get("/usage")
async def get_usage(
    user_id: uuid.UUID = Depends(verify_supabase_jwt),
    db: AsyncSession = Depends(get_db),
) -> UsageResponse:
    """Return all usage_logs records for the authenticated user from the last 30 days.

    Ordered by created_at DESC — most recent first.
    Uses idx_usage_logs_user_date index on (user_id, created_at DESC).
    """
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    result = await db.execute(
        select(UsageLog)
        .where(UsageLog.user_id == user_id)
        .where(UsageLog.created_at >= thirty_days_ago)
        .order_by(UsageLog.created_at.desc())
    )
    logs = result.scalars().all()

    records = [UsageRecord.from_log(log) for log in logs]

    # Sum cost_usd (Decimal) across all records
    total_cost: Decimal = sum(
        (log.cost_usd for log in logs), Decimal("0")
    )

    return UsageResponse(
        records=records,
        total_cost_usd=f"{total_cost:.8f}",
        period_days=30,
    )
```

**Why `sum(..., Decimal("0"))` not `sum(...)`?**
Python's `sum()` starts from integer `0` by default. `Decimal("0") + Decimal("0.00120000")` works fine, but `int(0) + Decimal("0.00120000")` also works. The explicit `Decimal("0")` start value is a safety net — if `logs` is empty, `sum([], Decimal("0"))` returns `Decimal("0")` rather than `int(0)`. This prevents type confusion when calling `f"{total:.8f}"` on an int.

**Why `order_by(UsageLog.created_at.desc())`?**
The `idx_usage_logs_user_date` index is defined as `(user_id, created_at DESC)`. Ordering DESC in the query matches the index's sort order and enables an index-only scan. A forward-scan on a DESC index for a DESC query requires no additional sort step.

### Updated `main.py`

```python
# api/src/opentaion_api/main.py (addition)
from opentaion_api.routers import keys, proxy, usage

# ... existing router registration ...
app.include_router(usage.router, prefix="/api")  # → GET /api/usage
```

**Route math:** prefix `/api` + route `/usage` = `GET /api/usage`. The `verify_supabase_jwt` dependency applies to the route, not the router — no `dependencies` kwarg needed on `include_router`.

### Tests — `tests/test_usage.py`

```python
# tests/test_usage.py
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from opentaion_api.main import app
from opentaion_api.dependencies.auth import verify_supabase_jwt
from opentaion_api.dependencies.db import get_db
from opentaion_api.models import UsageLog


TEST_USER_ID = uuid.uuid4()


@pytest.fixture(autouse=True)
def override_auth():
    """Use JWT auth override for all tests in this file."""
    app.dependency_overrides[verify_supabase_jwt] = lambda: TEST_USER_ID
    yield
    app.dependency_overrides.clear()


def make_log(
    model: str = "deepseek/deepseek-r1:free",
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    cost_usd: Decimal = Decimal("0.00000000"),
    days_ago: int = 1,
) -> MagicMock:
    """Build a mock UsageLog ORM object."""
    log = MagicMock()
    log.user_id = TEST_USER_ID
    log.model = model
    log.prompt_tokens = prompt_tokens
    log.completion_tokens = completion_tokens
    log.cost_usd = cost_usd
    log.created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return log


def make_db_with_logs(logs: list) -> AsyncMock:
    """Create a mock AsyncSession that returns logs on execute()."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = logs

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_db


# ── Populated result ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_usage_returns_200():
    logs = [make_log(prompt_tokens=100, completion_tokens=50)]
    app.dependency_overrides[get_db] = lambda: make_db_with_logs(logs)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/usage",
            headers={"Authorization": "Bearer fake-jwt"},
        )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_get_usage_response_shape():
    logs = [make_log(model="deepseek/deepseek-r1:free", prompt_tokens=1200, completion_tokens=800)]
    app.dependency_overrides[get_db] = lambda: make_db_with_logs(logs)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/usage", headers={"Authorization": "Bearer fake-jwt"})

    data = response.json()
    assert "records" in data
    assert "total_cost_usd" in data
    assert "period_days" in data
    assert data["period_days"] == 30


@pytest.mark.anyio
async def test_get_usage_record_fields():
    logs = [make_log(
        model="deepseek/deepseek-r1:free",
        prompt_tokens=1200,
        completion_tokens=800,
        days_ago=2,
    )]
    app.dependency_overrides[get_db] = lambda: make_db_with_logs(logs)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/usage", headers={"Authorization": "Bearer fake-jwt"})

    record = response.json()["records"][0]
    assert "date" in record
    assert "model" in record
    assert "prompt_tokens" in record
    assert "completion_tokens" in record
    assert "cost_usd" in record
    assert record["model"] == "deepseek/deepseek-r1:free"
    assert record["prompt_tokens"] == 1200
    assert record["completion_tokens"] == 800


@pytest.mark.anyio
async def test_get_usage_date_field_format():
    """date must be 'YYYY-MM-DD' string, not a datetime."""
    logs = [make_log(days_ago=5)]
    app.dependency_overrides[get_db] = lambda: make_db_with_logs(logs)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/usage", headers={"Authorization": "Bearer fake-jwt"})

    date_str = response.json()["records"][0]["date"]
    # Must be YYYY-MM-DD format (10 chars, no time component)
    assert len(date_str) == 10
    assert date_str[4] == "-" and date_str[7] == "-"


# ── Decimal string serialization ──────────────────────────────────────────────

@pytest.mark.anyio
async def test_cost_usd_is_string_not_number():
    logs = [make_log(cost_usd=Decimal("0.00120000"))]
    app.dependency_overrides[get_db] = lambda: make_db_with_logs(logs)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/usage", headers={"Authorization": "Bearer fake-jwt"})

    record = response.json()["records"][0]
    # cost_usd must be a JSON string, not a JSON number
    assert isinstance(record["cost_usd"], str)


@pytest.mark.anyio
async def test_cost_usd_has_eight_decimal_places():
    logs = [make_log(cost_usd=Decimal("0.00120000"))]
    app.dependency_overrides[get_db] = lambda: make_db_with_logs(logs)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/usage", headers={"Authorization": "Bearer fake-jwt"})

    cost_str = response.json()["records"][0]["cost_usd"]
    # Must have exactly 8 decimal places
    decimal_part = cost_str.split(".")[1]
    assert len(decimal_part) == 8


@pytest.mark.anyio
async def test_total_cost_usd_is_string_not_number():
    logs = [make_log(cost_usd=Decimal("0.00050000")), make_log(cost_usd=Decimal("0.00070000"))]
    app.dependency_overrides[get_db] = lambda: make_db_with_logs(logs)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/usage", headers={"Authorization": "Bearer fake-jwt"})

    assert isinstance(response.json()["total_cost_usd"], str)


@pytest.mark.anyio
async def test_total_cost_usd_sums_correctly():
    logs = [
        make_log(cost_usd=Decimal("0.00050000")),
        make_log(cost_usd=Decimal("0.00070000")),
    ]
    app.dependency_overrides[get_db] = lambda: make_db_with_logs(logs)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/usage", headers={"Authorization": "Bearer fake-jwt"})

    assert response.json()["total_cost_usd"] == "0.00120000"


# ── Empty result ───────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_usage_empty_result():
    app.dependency_overrides[get_db] = lambda: make_db_with_logs([])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/usage", headers={"Authorization": "Bearer fake-jwt"})

    assert response.status_code == 200
    data = response.json()
    assert data["records"] == []
    assert data["total_cost_usd"] == "0.00000000"
    assert data["period_days"] == 30


# ── Auth required ─────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_usage_requires_auth():
    """Without auth override, real verify_supabase_jwt should reject."""
    app.dependency_overrides.clear()  # remove auth override for this test

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/usage")  # no Authorization header

    assert response.status_code == 401
    # Restore override for other tests
    app.dependency_overrides[verify_supabase_jwt] = lambda: TEST_USER_ID
```

### `conftest.py` — Ensure `get_db` Override Cleanup

After each test that sets `app.dependency_overrides[get_db]`, the override must be cleared. The `autouse=True` `override_auth` fixture clears ALL overrides in teardown. However, if a test sets `get_db` override after `override_auth` runs setup, the `get_db` override won't be cleaned up unless `override_auth` runs teardown last.

The safe approach: set `get_db` override inline in each test (not in a fixture) and rely on `override_auth` autouse teardown to clear everything. This is the pattern shown above.

**Do not add `get_db` to a shared fixture** — different tests need different return values (different log sets), so inline setup is cleaner.

### Why Return Individual Records (Not DB-Aggregated by Day+Model)

The AC says "all `usage_logs` records for that user from the last 30 days." Story 4.2 needs to:
1. Group records by day for the bar chart (total tokens per day)
2. Group records by model for the model table (tokens + cost per model)

The API returns individual records; the frontend does the grouping. This approach:
- Keeps the query simple (no `GROUP BY` + `SUM` complexity in the API)
- Gives the frontend all the data it needs for both aggregations in one response
- Allows future flexibility (e.g., per-call drill-down)

**When would you pre-aggregate at the DB level?** If the user had millions of records (V1 won't), a DB-level GROUP BY would be critical for performance. For V1 solo-developer scale, returning individual records is fine.

### Architecture Cross-References

From `architecture.md`:
- `GET /api/usage` auth: `verify_supabase_jwt` [Source: architecture.md#API Contract]
- Response shape (JSON, with decimal string cost) [Source: architecture.md#API Contract]
- `idx_usage_logs_user_date` on `(user_id, created_at DESC)` [Source: architecture.md#Data Architecture]
- `cost_usd` serialized as string in JSON — never float [Source: architecture.md#Format Patterns, rule 2]
- Pydantic schemas never mixed with ORM models [Source: architecture.md#Structure Patterns]
- `GET /api/usage` must return within 2 seconds for 30-day dataset (NFR2) [Source: architecture.md#NFR]

From `epics.md`:
- FR20: "Developer can view a bar chart of their token usage for the last 30 days, grouped by day and broken down by model" [Source: epics.md#FR20]
- FR21: "Developer can view a per-model cost summary table for their last 30 days of usage" [Source: epics.md#FR21]
- NFR2: "GET /api/usage must return a response within 2 seconds for a standard 30-day dataset" [Source: epics.md#NFR2]

### What This Story Does NOT Include

- `<UsageChart>` and `<ModelTable>` React components — those are Story 4.2
- Aggregation or grouping at the SQL level — the frontend groups for the chart and table
- Pagination — 30 days of calls for a solo dev is a small dataset, no pagination needed
- Filtering by model or date range beyond 30 days — out of V1 scope

### Final Modified/Created Files

```
api/
└── src/opentaion_api/
    ├── main.py         ← MODIFIED — app.include_router(usage.router, prefix="/api")
    ├── schemas.py      ← MODIFIED — add UsageRecord, UsageResponse
    └── routers/
        └── usage.py    ← NEW — GET /usage endpoint
tests/
└── test_usage.py       ← NEW — usage endpoint tests
```

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Story spec imports from `opentaion_api.dependencies.auth` and `opentaion_api.dependencies.db` — actual modules are `opentaion_api.deps` and `opentaion_api.database`; adapted accordingly
- Story spec uses `@pytest.mark.anyio` — project uses `asyncio_mode = "auto"`; used plain `async def` tests

### Completion Notes List

- TDD red: all 10 tests failed (404 from missing route)
- Added `UsageRecord` and `UsageResponse` schemas to `schemas.py`; `TYPE_CHECKING` guard avoids circular import
- `routers/usage.py` created with 30-day query + Decimal sum
- `main.py` updated to register usage router with `/api` prefix
- 10/10 usage tests pass; 67/67 full suite passes

### File List

- `api/src/opentaion_api/schemas.py` — MODIFIED: added UsageRecord, UsageResponse schemas
- `api/src/opentaion_api/routers/usage.py` — NEW: GET /api/usage endpoint
- `api/src/opentaion_api/main.py` — MODIFIED: registered usage router
- `api/tests/test_usage.py` — NEW: 10 tests for usage endpoint
