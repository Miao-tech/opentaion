# Story 2.2: API Key CRUD Endpoints

Status: done

## Story

As a developer building OpenTalon,
I want `POST /api/keys`, `GET /api/keys`, and `DELETE /api/keys/{key_id}` endpoints implemented,
So that the web dashboard can generate, list, and revoke API keys for the authenticated user.

## Acceptance Criteria

**AC1 — POST /api/keys generates and returns a key once:**
Given an authenticated web user (valid Supabase JWT)
When `POST /api/keys` is called
Then a new API key is generated in the format `ot_` + `secrets.token_urlsafe(24)`, the full plaintext key is returned exactly once in the response (`{"id": "...", "key": "ot_...", "key_prefix": "...", "created_at": "..."}`), the `key_hash` (bcrypt cost 12) and `key_prefix` (first 12 chars) are stored in `api_keys`, and the plaintext key is never persisted

**AC2 — GET /api/keys returns active keys without exposing hashes:**
Given an authenticated web user
When `GET /api/keys` is called
Then all active keys (`revoked_at IS NULL`) for the user are returned as a list with fields `id`, `key_prefix`, `created_at` — no `key_hash` in the response

**AC3 — DELETE /api/keys/{key_id} revokes a key:**
Given an authenticated web user with an existing active key
When `DELETE /api/keys/{key_id}` is called with a valid key ID belonging to the user
Then `revoked_at` is set to `NOW()` for that key and HTTP 204 is returned

**AC4 — DELETE /api/keys/{key_id} returns 404 for wrong owner:**
Given a key ID belonging to a different user
When `DELETE /api/keys/{key_id}` is called
Then HTTP 404 is returned (no cross-user key access, no information leakage)

**AC5 — Tests pass:**
Given tests are run
When `uv run pytest` is executed from `api/`
Then tests pass for all three endpoints: happy path, unauthorized, not found

## Tasks / Subtasks

- [x] Task 1: Create Pydantic schemas for request/response (AC: 1, 2)
  - [x] Create `src/opentaion_api/schemas.py` with `ApiKeyCreateResponse` and `ApiKeyListItem` (see Dev Notes)
  - [x] Use `datetime` + ISO 8601 serialization via Pydantic's `model_config`

- [x] Task 2: Write tests FIRST in `tests/test_keys.py` — confirm they fail (AC: 5, TDD)
  - [x] Create test file with `TestClient`, dependency overrides for `verify_supabase_jwt` and `get_db`
  - [x] Run `uv run pytest tests/test_keys.py` — all tests must FAIL (router doesn't exist yet)

- [x] Task 3: Create `src/opentaion_api/routers/keys.py` with all three endpoints (AC: 1, 2, 3, 4)
  - [x] `POST /api/keys` — generate key, hash at cost 12, store, return plaintext once
  - [x] `GET /api/keys` — query active keys for user, return list (no key_hash)
  - [x] `DELETE /api/keys/{key_id}` — set `revoked_at`, return 204; 404 if not found or wrong owner

- [x] Task 4: Register the router in `src/opentaion_api/main.py` (AC: 1, 2, 3)
  - [x] `app.include_router(keys_router, prefix="/api")` in `main.py`

- [x] Task 5: Run tests green (AC: 5)
  - [x] `uv run pytest tests/test_keys.py -v` — all tests pass
  - [x] `uv run pytest` — full suite (health + deps + keys) all pass

## Dev Notes

### Prerequisite: Story 2.1 Must Be Complete

`verify_supabase_jwt` must be the real implementation (not the 501 stub). All three endpoints use it as their auth dependency. If Story 2.1 is not done, the tests will error with `501 Not Implemented`.

### Pydantic Schemas — Create `src/opentaion_api/schemas.py`

Create a new file for Pydantic response models. Do NOT define them inside the router file — schemas will be reused by multiple routers in later stories:

```python
# src/opentaion_api/schemas.py
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ApiKeyCreateResponse(BaseModel):
    """Response for POST /api/keys — contains the plaintext key (shown ONCE only)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str           # full plaintext key — only returned at creation, never again
    key_prefix: str
    created_at: datetime


class ApiKeyListItem(BaseModel):
    """One entry in GET /api/keys — NO key_hash, NO full key."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key_prefix: str
    created_at: datetime
```

**Why `from_attributes=True`?**
Allows Pydantic to build these models directly from SQLAlchemy ORM objects with `ApiKeyListItem.model_validate(orm_obj)`. Avoids manually mapping fields.

**Why no `ApiKeyCreateRequest`?**
`POST /api/keys` takes no request body — the key is generated server-side. The route handler signature has no `Body` parameter.

**`datetime` serialization:** Pydantic v2 serializes `datetime` as ISO 8601 strings by default. No extra config needed.

### Router Implementation — `src/opentaion_api/routers/keys.py`

```python
# src/opentaion_api/routers/keys.py
import secrets
import uuid
from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opentaion_api.database import get_db
from opentaion_api.deps import verify_supabase_jwt
from opentaion_api.models import ApiKey
from opentaion_api.schemas import ApiKeyCreateResponse, ApiKeyListItem

router = APIRouter(tags=["keys"])


@router.post("/keys", response_model=ApiKeyCreateResponse, status_code=201)
async def create_api_key(
    user_id: uuid.UUID = Depends(verify_supabase_jwt),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyCreateResponse:
    """
    Generate a new API key for the authenticated user.
    The plaintext key is returned ONCE here and never stored — only its bcrypt hash.
    """
    key = "ot_" + secrets.token_urlsafe(24)
    key_prefix = key[:12]
    key_hash = bcrypt.hashpw(key.encode(), bcrypt.gensalt(rounds=12)).decode()

    new_key = ApiKey(
        user_id=user_id,
        key_hash=key_hash,
        key_prefix=key_prefix,
    )
    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)

    return ApiKeyCreateResponse(
        id=new_key.id,
        key=key,           # plaintext key — included here and NEVER again
        key_prefix=key_prefix,
        created_at=new_key.created_at,
    )


@router.get("/keys", response_model=list[ApiKeyListItem])
async def list_api_keys(
    user_id: uuid.UUID = Depends(verify_supabase_jwt),
    db: AsyncSession = Depends(get_db),
) -> list[ApiKeyListItem]:
    """
    Return all active (non-revoked) API keys for the authenticated user.
    Never returns key_hash or the full plaintext key.
    """
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user_id)
        .where(ApiKey.revoked_at.is_(None))
        .order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [ApiKeyListItem.model_validate(k) for k in keys]


@router.delete("/keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: uuid.UUID,
    user_id: uuid.UUID = Depends(verify_supabase_jwt),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Revoke an API key by setting revoked_at = NOW().
    Returns 404 if the key doesn't exist OR belongs to a different user.
    This prevents leaking the existence of other users' keys.
    """
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.id == key_id)
        .where(ApiKey.user_id == user_id)
    )
    key = result.scalar_one_or_none()

    if key is None:
        raise HTTPException(status_code=404, detail="Not found")

    key.revoked_at = datetime.now(timezone.utc)
    await db.commit()
```

**Why `secrets.token_urlsafe(24)` and not `secrets.token_urlsafe(32)`?**
`token_urlsafe(n)` generates `n` random bytes, then base64url-encodes them producing `ceil(n * 4/3)` characters. 24 bytes → 32 characters. So the full key is `"ot_"` (3) + 32 chars = 35 characters total. This matches the format spec exactly.

**Why bcrypt cost 12 for generation?**
Key generation is infrequent (a user creates at most a handful of keys). Cost 12 (~250-350ms) is acceptable for this path. The proxy validation path (`verify_api_key` in Story 2.1 + 3.2) calls `checkpw` against whatever cost is embedded in the stored hash. Keep in mind this means proxy auth will also run at cost 12 (~250-350ms), which approaches the 200ms NFR1. This is documented as a trade-off in the architecture ("NFR1: Hard requirement — not a target" combined with bcrypt overhead being a known constraint).

**Why `revoked_at.is_(None)` not `== None`?**
SQLAlchemy ORM uses `.is_(None)` to generate `IS NULL` SQL. The Python `== None` comparison generates `= NULL` which is always false in SQL. This is a very common ORM mistake.

**Why 404 (not 403) for cross-user key?**
Returning 403 confirms the key exists but the user doesn't own it — information leakage. 404 is indistinguishable from "key doesn't exist", preventing enumeration of other users' key IDs.

### Register in `main.py`

Update `src/opentaion_api/main.py`:

```python
# src/opentaion_api/main.py
from fastapi import FastAPI

from opentaion_api.routers import keys

app = FastAPI(title="opentaion-api", version="0.1.0")

app.include_router(keys.router, prefix="/api")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
```

The prefix `/api` + router path `/keys` = final path `/api/keys`. The delete route becomes `/api/keys/{key_id}`.

### Tests — `tests/test_keys.py`

Write these BEFORE implementing the router. The tests use `TestClient` with dependency overrides — no real database or JWT required:

```python
# tests/test_keys.py
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from opentaion_api.main import app
from opentaion_api.database import get_db
from opentaion_api.deps import verify_supabase_jwt

TEST_USER_ID = uuid.uuid4()
TEST_KEY_ID = uuid.uuid4()


# ── Dependency overrides ──────────────────────────────────────────────────────

def override_auth():
    """Always authenticates as TEST_USER_ID — no real JWT needed."""
    return TEST_USER_ID


def make_mock_key(user_id: uuid.UUID = TEST_USER_ID, revoked: bool = False) -> MagicMock:
    key = MagicMock()
    key.id = TEST_KEY_ID
    key.user_id = user_id
    key.key_hash = "hashed"
    key.key_prefix = "ot_testkey12"
    key.created_at = datetime.now(timezone.utc)
    key.revoked_at = datetime.now(timezone.utc) if revoked else None
    return key


# ── POST /api/keys ────────────────────────────────────────────────────────────

def test_create_key_returns_201_with_plaintext_key():
    mock_key = make_mock_key()

    async def override_db():
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "created_at", mock_key.created_at) or setattr(obj, "id", TEST_KEY_ID))
        yield db

    app.dependency_overrides[verify_supabase_jwt] = override_auth
    app.dependency_overrides[get_db] = override_db

    client = TestClient(app)
    response = client.post("/api/keys")

    app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["key"].startswith("ot_")
    assert len(data["key"]) == 35  # "ot_" + 32 chars
    assert data["key_prefix"] == data["key"][:12]
    assert "id" in data
    assert "created_at" in data
    assert "key_hash" not in data  # never exposed


def test_create_key_requires_auth():
    client = TestClient(app)
    response = client.post("/api/keys")  # no override → real verify_supabase_jwt → 401
    assert response.status_code == 401


# ── GET /api/keys ─────────────────────────────────────────────────────────────

def test_list_keys_returns_active_keys():
    mock_key = make_mock_key()

    async def override_db():
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_key]
        db = AsyncMock()
        db.execute.return_value = mock_result
        yield db

    app.dependency_overrides[verify_supabase_jwt] = override_auth
    app.dependency_overrides[get_db] = override_db

    client = TestClient(app)
    response = client.get("/api/keys")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["key_prefix"] == "ot_testkey12"
    assert "key_hash" not in data[0]
    assert "key" not in data[0]  # full key never in list response


def test_list_keys_returns_empty_list():
    async def override_db():
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db = AsyncMock()
        db.execute.return_value = mock_result
        yield db

    app.dependency_overrides[verify_supabase_jwt] = override_auth
    app.dependency_overrides[get_db] = override_db

    client = TestClient(app)
    response = client.get("/api/keys")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == []


def test_list_keys_requires_auth():
    client = TestClient(app)
    response = client.get("/api/keys")
    assert response.status_code == 401


# ── DELETE /api/keys/{key_id} ─────────────────────────────────────────────────

def test_revoke_key_returns_204():
    mock_key = make_mock_key()

    async def override_db():
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_key
        db = AsyncMock()
        db.execute.return_value = mock_result
        db.commit = AsyncMock()
        yield db

    app.dependency_overrides[verify_supabase_jwt] = override_auth
    app.dependency_overrides[get_db] = override_db

    client = TestClient(app)
    response = client.delete(f"/api/keys/{TEST_KEY_ID}")

    app.dependency_overrides.clear()

    assert response.status_code == 204
    assert mock_key.revoked_at is not None  # verify revoked_at was set


def test_revoke_key_not_found_returns_404():
    async def override_db():
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # key not found
        db = AsyncMock()
        db.execute.return_value = mock_result
        yield db

    app.dependency_overrides[verify_supabase_jwt] = override_auth
    app.dependency_overrides[get_db] = override_db

    client = TestClient(app)
    response = client.delete(f"/api/keys/{uuid.uuid4()}")

    app.dependency_overrides.clear()

    assert response.status_code == 404


def test_revoke_key_requires_auth():
    client = TestClient(app)
    response = client.delete(f"/api/keys/{TEST_KEY_ID}")
    assert response.status_code == 401
```

**Key testing pattern — dependency override vs `monkeypatch`:**
`app.dependency_overrides` is FastAPI's built-in mechanism for replacing dependencies in tests. It works for any `Depends(...)` in route signatures. Always call `app.dependency_overrides.clear()` after each test — shared state between tests causes hard-to-debug failures.

**The `override_db` generator pattern:**
FastAPI's `get_db` is an `async def` generator (`yield` dependency). The override must also be an `async def` generator that yields the mock. A plain `AsyncMock` return won't work.

### JSON Response Format

All API responses use snake_case (never camelCase). `datetime` fields serialize as ISO 8601 UTC strings — Pydantic v2 does this automatically. `uuid.UUID` fields serialize as lowercase hyphenated strings — also automatic.

Example `POST /api/keys` response:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "key": "ot_abc123xyz789def456uvw012rst3456",
  "key_prefix": "ot_abc123xyz789",
  "created_at": "2026-03-24T10:30:00.000000Z"
}
```

No `key_hash`. Never. The hash must not appear in any response, log, or error message.

### Architecture Cross-References

From `architecture.md`:
- API key format: `"ot_" + secrets.token_urlsafe(24)` — never `random` [Source: architecture.md#Implementation Patterns]
- `revoked_at` timestamp pattern: set to `NOW()` on revoke, not a boolean flag [Source: architecture.md#Database Schema]
- `cost_usd` as `Decimal` (not relevant here), snake_case JSON throughout [Source: architecture.md#Implementation Patterns]
- Pydantic schemas vs SQLAlchemy models: never mix — routes receive Pydantic → ORM → Pydantic response [Source: architecture.md#Project Structure]
- `raise HTTPException` for all API errors — never `return {"error": ...}` [Source: architecture.md#Implementation Patterns]

From `epics.md`:
- FR2: "Developer can generate a new OpenTalon API key from the web dashboard (displayed once at creation)" [Source: epics.md#FR2]
- FR3: "Developer can view a list of their active API keys with a truncated preview of each key" [Source: epics.md#FR3]
- FR4: "Developer can revoke an API key by ID from the web dashboard" [Source: epics.md#FR4]
- NFR4: "OpenTalon API keys must be stored bcrypt-hashed in the database; plaintext keys must never be persisted" [Source: epics.md#NFR4]
- NFR5: "A generated API key must be displayed exactly once at creation; it must not be retrievable after the creation response" [Source: epics.md#NFR5]
- Additional Requirements: "bcrypt cost factor 12 (infrequent) for key generation" [Source: epics.md#Additional Requirements]

### What This Story Does NOT Include

Do NOT implement any of the following:

- The web UI for key management (Stories 2.4, 2.5)
- `opentaion login` CLI command that uses the API key (Story 2.6)
- `POST /v1/chat/completions` proxy endpoint that validates keys (Story 3.2)
- Any rate limiting on key generation
- Key expiration — keys are active until explicitly revoked

### Final Modified/Created Files

```
api/
└── src/
    └── opentaion_api/
        ├── main.py           # MODIFIED — added router include
        ├── schemas.py        # NEW — ApiKeyCreateResponse, ApiKeyListItem
        └── routers/
            ├── __init__.py   # unchanged
            └── keys.py       # NEW — POST/GET/DELETE /api/keys
    tests/
    └── test_keys.py          # NEW — CRUD endpoint tests
```

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- `Header(...)` (required) causes FastAPI to return 422 before calling the dependency when the header is absent. Tests expect 401. Fixed by making authorization `str | None = Header(default=None)` and checking for None in the function body. This also fixed the same issue retroactively in `verify_api_key`. All existing test_deps.py tests unaffected (they always supply the header explicitly).

### Completion Notes List

- Created `schemas.py` with `ApiKeyCreateResponse` (includes plaintext key) and `ApiKeyListItem` (no key/hash)
- Created `routers/keys.py` with POST/GET/DELETE endpoints — bcrypt cost 12 for generation, `revoked_at` pattern for revocation, 404 for cross-user key access
- Updated `main.py` to include keys router under `/api` prefix
- Updated `deps.py` to use optional Authorization header (`str | None`) in both auth functions — returns 401 for absent header instead of FastAPI's 422
- 8 new tests in `test_keys.py` — all pass; full suite 23/23

### File List

- `api/src/opentaion_api/schemas.py` — NEW: ApiKeyCreateResponse, ApiKeyListItem
- `api/src/opentaion_api/routers/keys.py` — NEW: POST/GET/DELETE /api/keys
- `api/src/opentaion_api/main.py` — MODIFIED: added keys router include
- `api/src/opentaion_api/deps.py` — MODIFIED: optional Authorization header in both deps
- `api/tests/test_keys.py` — NEW: 8 endpoint tests

## Change Log

- 2026-03-25: Story 2.2 implemented — API key CRUD endpoints; schemas added; deps.py updated to return 401 (not 422) for missing Authorization header; 8 tests added; all 23 tests pass
