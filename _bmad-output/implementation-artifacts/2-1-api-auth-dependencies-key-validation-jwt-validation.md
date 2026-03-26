# Story 2.1: API Auth Dependencies (Key Validation + JWT Validation)

Status: done

## Story

As a developer building OpenTalon,
I want the two FastAPI auth dependencies — `verify_api_key()` and `verify_supabase_jwt()` — implemented and tested,
So that all subsequent API endpoints can declare their auth method via dependency injection.

## Acceptance Criteria

**AC1 — `verify_api_key()` returns user_id for a valid active key:**
Given a valid `Authorization: Bearer ot_<key>` header where the key is active (not revoked)
When `verify_api_key()` is called as a FastAPI dependency
Then it returns the `user_id` UUID associated with that key

**AC2 — `verify_api_key()` uses bcrypt prefix-lookup and rejects revoked keys:**
Given the key prefix lookup runs
When `verify_api_key()` resolves candidates from `api_keys` by `key_prefix`
Then it uses `bcrypt.checkpw` and raises `HTTPException(401)` if no match or if `revoked_at IS NOT NULL`

**AC3 — `verify_supabase_jwt()` returns user_id from valid Supabase JWT:**
Given a valid Supabase Auth JWT in the `Authorization: Bearer` header
When `verify_supabase_jwt()` is called as a FastAPI dependency
Then it verifies against `SUPABASE_JWT_SECRET`, extracts the `sub` claim as a UUID, and returns it

**AC4 — Both dependencies raise 401 on invalid input:**
Given an invalid key, revoked key, expired JWT, wrong secret, or missing `Bearer` prefix
When either auth dependency is called
Then it raises `HTTPException(status_code=401, detail="Unauthorized")`

**AC5 — Tests pass:**
Given tests are run
When `uv run pytest` is executed from `api/`
Then unit tests pass for: valid key, revoked key, invalid key, expired JWT, wrong secret, missing header

## Tasks / Subtasks

- [x] Task 1: Add `PyJWT` dependency (AC: 3, 4)
  - [x] `cd api && uv add PyJWT`
  - [x] Confirm `PyJWT` appears in `pyproject.toml` and `uv.lock`

- [x] Task 2: Write tests FIRST — confirm they fail before implementing (AC: 5, TDD)
  - [x] Create `tests/test_deps.py` with all required test cases (see Dev Notes)
  - [x] Run `uv run pytest tests/test_deps.py` — confirm tests FAIL (red phase)
  - [x] The existing `deps.py` stubs raise `501 Not Implemented` — tests expecting `user_id` or `401` will fail

- [x] Task 3: Implement `verify_api_key()` in `deps.py` (AC: 1, 2, 4)
  - [x] Replace the `verify_api_key` stub in `src/opentaion_api/deps.py` with the real implementation (see Dev Notes)
  - [x] Add required imports: `bcrypt`, `select`, `ApiKey`, `os`
  - [x] Parse `Authorization` header → strip `Bearer ` → extract `key_prefix = key[:12]`
  - [x] Query `api_keys` table by `key_prefix`
  - [x] For each candidate: `bcrypt.checkpw(key.encode(), candidate.key_hash.encode())`
  - [x] Reject if `candidate.revoked_at is not None`
  - [x] Return `candidate.user_id` on match; raise `HTTPException(401)` on any failure

- [x] Task 4: Implement `verify_supabase_jwt()` in `deps.py` (AC: 3, 4)
  - [x] Replace the `verify_supabase_jwt` stub in `deps.py` with the real implementation (see Dev Notes)
  - [x] Add `import jwt` and `import os`
  - [x] Parse `Authorization` header → strip `Bearer `
  - [x] `jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"], audience="authenticated")`
  - [x] Extract `payload["sub"]` as `uuid.UUID`
  - [x] Wrap ALL exceptions in `HTTPException(401)` — never let JWT errors propagate

- [x] Task 5: Run tests — confirm they pass (AC: 5)
  - [x] `uv run pytest tests/test_deps.py -v`
  - [x] All tests must pass (green phase)
  - [x] Then run full suite: `uv run pytest` — existing `test_health.py` must still pass

## Dev Notes

### Prerequisites: Stories 1.2 and 1.4 Must Be Complete

- Story 1.2 created the `deps.py` stubs and `database.py` — both are modified here
- Story 1.4 created `models.py` with `ApiKey` — used in `verify_api_key`
- If models aren't imported, `sqlalchemy.select(ApiKey)` will fail at import time

### Add `PyJWT` — New Dependency

`PyJWT` is not in the current `pyproject.toml`. Install it:
```bash
cd api
uv add PyJWT
```

**Why `PyJWT` and not `python-jose`?**
- `PyJWT` is the standard, maintained JWT library with minimal dependencies
- Supabase JWTs use HS256 — `PyJWT` handles this natively
- `python-jose` is heavier and has CVEs in older versions
- The `supabase` SDK is already installed but its auth client makes network calls to Supabase — not what we want for local JWT verification

**Import name:** The package is `PyJWT`, imported as `import jwt`.

### TDD: Write `tests/test_deps.py` First

Create this file BEFORE modifying `deps.py`. Confirm tests fail. Then implement. Then confirm tests pass.

```python
# tests/test_deps.py
import os
import time
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import bcrypt as _bcrypt
import jwt as pyjwt
import pytest
from fastapi import HTTPException

from opentaion_api.deps import verify_api_key, verify_supabase_jwt

TEST_JWT_SECRET = "test-supabase-jwt-secret-for-testing-only"


# ── Test helpers ─────────────────────────────────────────────────────────────

def make_test_jwt(user_id: str, secret: str = TEST_JWT_SECRET, expired: bool = False) -> str:
    """Create a signed Supabase-shaped JWT for testing."""
    now = int(time.time())
    return pyjwt.encode(
        {
            "sub": user_id,
            "aud": "authenticated",
            "exp": now - 10 if expired else now + 3600,
            "iat": now,
        },
        secret,
        algorithm="HS256",
    )


def make_key_candidate(key: str, revoked: bool = False) -> MagicMock:
    """Create a mock ApiKey DB row with a real bcrypt hash (rounds=4 for test speed)."""
    candidate = MagicMock()
    candidate.key_hash = _bcrypt.hashpw(key.encode(), _bcrypt.gensalt(rounds=4)).decode()
    candidate.revoked_at = datetime.now(timezone.utc) if revoked else None
    candidate.user_id = uuid.uuid4()
    return candidate


def mock_db_returning(candidates: list) -> AsyncMock:
    """Return an AsyncMock session that yields the given candidates from execute()."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = candidates
    db = AsyncMock()
    db.execute.return_value = mock_result
    return db


TEST_KEY = "ot_testkey1234567890123456789012"  # 35 chars: "ot_" + 32


# ── verify_api_key ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_api_key_valid_returns_user_id():
    candidate = make_key_candidate(TEST_KEY)
    db = mock_db_returning([candidate])
    result = await verify_api_key(authorization=f"Bearer {TEST_KEY}", db=db)
    assert result == candidate.user_id


@pytest.mark.asyncio
async def test_verify_api_key_revoked_raises_401():
    candidate = make_key_candidate(TEST_KEY, revoked=True)
    db = mock_db_returning([candidate])
    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(authorization=f"Bearer {TEST_KEY}", db=db)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_api_key_no_match_raises_401():
    db = mock_db_returning([])  # prefix lookup returns nothing
    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(authorization=f"Bearer {TEST_KEY}", db=db)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_api_key_missing_bearer_raises_401():
    db = mock_db_returning([])
    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(authorization=TEST_KEY, db=db)  # no "Bearer " prefix
    assert exc_info.value.status_code == 401


# ── verify_supabase_jwt ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_supabase_jwt_valid_returns_user_id(monkeypatch):
    user_id = str(uuid.uuid4())
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    token = make_test_jwt(user_id)
    result = await verify_supabase_jwt(authorization=f"Bearer {token}")
    assert result == uuid.UUID(user_id)


@pytest.mark.asyncio
async def test_verify_supabase_jwt_expired_raises_401(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    token = make_test_jwt(str(uuid.uuid4()), expired=True)
    with pytest.raises(HTTPException) as exc_info:
        await verify_supabase_jwt(authorization=f"Bearer {token}")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_supabase_jwt_wrong_secret_raises_401(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    token = make_test_jwt(str(uuid.uuid4()), secret="wrong-secret")
    with pytest.raises(HTTPException) as exc_info:
        await verify_supabase_jwt(authorization=f"Bearer {token}")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_supabase_jwt_missing_bearer_raises_401(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    token = make_test_jwt(str(uuid.uuid4()))
    with pytest.raises(HTTPException) as exc_info:
        await verify_supabase_jwt(authorization=token)  # no "Bearer " prefix
    assert exc_info.value.status_code == 401
```

**Why `rounds=4` in `_bcrypt.gensalt(rounds=4)`?**
bcrypt at default rounds (12) takes ~250ms per hash. Running 4 tests that each create a hash would take ~1 second. `rounds=4` takes ~1ms and still validates the bcrypt API correctly.

**Why `AsyncMock` for the DB session?**
`db.execute()` is awaited in the real code. `AsyncMock` automatically returns an awaitable. `MagicMock` for the result chain works because `.scalars().all()` is not awaited.

**Why call the dependency function directly?**
FastAPI dependency functions are regular async functions. They can be called with keyword args directly in tests, bypassing the HTTP layer entirely. This is faster and simpler than `TestClient` + dependency override for unit testing.

### Implementation: `src/opentaion_api/deps.py`

Replace the entire file with this implementation:

```python
# src/opentaion_api/deps.py
import os
import uuid

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opentaion_api.database import get_db
from opentaion_api.models import ApiKey  # noqa: F401 — registers model on Base.metadata


async def verify_api_key(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    """
    Validate an OpenTalon API key from the Authorization header.

    Flow: parse key → prefix lookup (indexed) → bcrypt.checkpw → revocation check
    Cost factor 10 is enforced during key GENERATION (Story 2.2), not here.
    checkpw timing is determined by the stored hash's cost factor.

    Used by: POST /v1/chat/completions (Story 3.2) — called on every proxy request.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    key = authorization.removeprefix("Bearer ").strip()

    if not key.startswith("ot_") or len(key) < 12:
        raise HTTPException(status_code=401, detail="Unauthorized")

    prefix = key[:12]

    result = await db.execute(select(ApiKey).where(ApiKey.key_prefix == prefix))
    candidates = result.scalars().all()

    for candidate in candidates:
        if bcrypt.checkpw(key.encode(), candidate.key_hash.encode()):
            if candidate.revoked_at is not None:
                raise HTTPException(status_code=401, detail="Unauthorized")
            return candidate.user_id

    raise HTTPException(status_code=401, detail="Unauthorized")


async def verify_supabase_jwt(
    authorization: str = Header(...),
) -> uuid.UUID:
    """
    Validate a Supabase Auth JWT from the Authorization header.

    Verifies signature against SUPABASE_JWT_SECRET (HS256).
    Supabase user tokens always have aud="authenticated".
    Extracts the `sub` claim (user UUID) and returns it.

    Used by: POST/GET/DELETE /api/keys (Story 2.2), GET /api/usage (Story 4.1)
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = authorization.removeprefix("Bearer ").strip()

    try:
        payload = jwt.decode(
            token,
            os.environ.get("SUPABASE_JWT_SECRET", ""),
            algorithms=["HS256"],
            audience="authenticated",
        )
        return uuid.UUID(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
```

### Key Implementation Rules — Enforced Here

**Never expose auth failure details.** Both functions always raise `HTTPException(401, "Unauthorized")` — they never say "key not found" or "JWT expired". This prevents enumeration attacks.

**Broad exception catch in `verify_supabase_jwt` is intentional.** `jwt.decode` raises different exceptions for different failure modes (`ExpiredSignatureError`, `InvalidSignatureError`, `DecodeError`, `MissingRequiredClaimError`, etc.). A bare `except Exception` converts all of them to a generic 401. Do not narrow this — every JWT failure should look identical to the caller.

**`key[:12]` is the prefix, not `key[3:12]`.** The prefix includes the `ot_` portion. Example: for key `ot_abc123xyz789...`, the prefix is `ot_abc123xyz7`. The first 12 characters of the full key string. This matches what Story 2.2 will store: `key_prefix = key[:12]`.

**`bcrypt.checkpw` with `.encode()`:** Both the plaintext key and the stored hash must be bytes. The DB stores `key_hash` as TEXT (str) — always `.encode()` before passing to `bcrypt.checkpw`.

**Architecture rule:** Auth is ALWAYS via `Depends(...)` on the route, never inline in the route body. These two functions are the only auth functions. Every protected endpoint will use one of them and nothing else.

### bcrypt Cost Factor Clarification

The AC mentions "bcrypt.checkpw with cost factor 10." The cost factor in bcrypt is embedded in the stored hash — `checkpw` uses whatever factor the hash was created with. Cost factor 10 is enforced at KEY GENERATION time (Story 2.2 uses `bcrypt.gensalt(rounds=10)` when storing new keys). This story does not set the cost factor — it just calls `checkpw`.

Why 10 and not 12? NFR1 requires the proxy to add less than 200ms overhead. On commodity hardware:
- bcrypt rounds=12: ~250–350ms
- bcrypt rounds=10: ~60–80ms

Story 3.2 calls `verify_api_key` on every `/v1/chat/completions` request. rounds=10 keeps auth well within the 200ms budget.

### Architecture Cross-References

From `architecture.md`:
- Dual authentication pattern: `verify_api_key()` (bcrypt, cost 10) for CLI routes; `verify_supabase_jwt()` for web routes [Source: architecture.md#Authentication & Security]
- FastAPI: auth always via `Depends(...)` argument — never inline in route body [Source: architecture.md#Implementation Patterns]
- `key_prefix` enables fast prefix-lookup before bcrypt comparison — keeps auth latency acceptable [Source: architecture.md#Database Schema]
- bcrypt cost factor 10 (not 12) for key validation in proxy hot path [Source: epics.md#Additional Requirements]
- Never expose `HTTPException` error details beyond `"Unauthorized"` [Source: architecture.md#Implementation Patterns]

From `epics.md`:
- Additional Requirements: "Dual authentication pattern: `verify_api_key()` (bcrypt, cost factor 10) for CLI routes; `verify_supabase_jwt()` (JWT secret validation) for web routes. Auth always via FastAPI dependency injection, never inline in route body." [Source: epics.md#Additional Requirements]
- Additional Requirements: "API key format: `ot_` prefix + 32 url-safe random chars = `'ot_' + secrets.token_urlsafe(24)`. Key prefix for bcrypt lookup = first 12 characters." [Source: epics.md#Additional Requirements]

### Regression Check: `test_health.py` Must Still Pass

Story 1.2 added `tests/test_health.py`. It must continue to pass after this story:
```bash
uv run pytest  # run the full suite, not just test_deps.py
```

The health endpoint at `GET /health` uses no auth dependency — it should be unaffected. If `test_health.py` breaks after this story, there's an import error in `deps.py` or `models.py`.

### What This Story Does NOT Include

Do NOT implement any of the following — they belong to later stories:

- `POST /api/keys`, `GET /api/keys`, `DELETE /api/keys/{key_id}` endpoints (Story 2.2)
- The actual key generation logic using `secrets.token_urlsafe(24)` (Story 2.2)
- bcrypt key hashing at cost 12 for generation (Story 2.2 — this story only does `checkpw`)
- Any web route handler that calls `verify_supabase_jwt` (Story 2.2+)
- Any CLI route handler that calls `verify_api_key` (Story 3.2)
- The `opentaion login` CLI command (Story 2.6)

### Final Modified/Created Files

```
api/
├── pyproject.toml          # MODIFIED — added PyJWT dependency
├── uv.lock                 # MODIFIED — updated by uv add
├── src/
│   └── opentaion_api/
│       └── deps.py         # MODIFIED — real implementations replace stubs
└── tests/
    └── test_deps.py        # NEW — unit tests for both auth dependencies
```

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- PyJWT was already installed in the venv (2.12.1) but not in pyproject.toml. Added manually since `uv add` requires network. Used `--frozen` sync to register it.

### Completion Notes List

- Added `PyJWT>=2.0` to `api/pyproject.toml` dependencies (package already present in venv at 2.12.1)
- Created `tests/test_deps.py` with 8 unit tests covering all ACs — confirmed red before implementing
- Replaced `deps.py` stubs with real implementations of `verify_api_key()` and `verify_supabase_jwt()`
- `verify_api_key`: Bearer parse → key prefix[:12] lookup → bcrypt.checkpw → revocation check → return user_id
- `verify_supabase_jwt`: Bearer parse → jwt.decode (HS256, aud=authenticated) → UUID(sub) → return
- All error paths return `HTTPException(401, "Unauthorized")` — no details exposed
- 15/15 tests pass (8 new + 5 database_url + 2 health), zero regressions

### File List

- `api/pyproject.toml` — MODIFIED: added `PyJWT>=2.0` dependency
- `api/src/opentaion_api/deps.py` — MODIFIED: replaced stubs with real implementations
- `api/tests/test_deps.py` — NEW: 8 unit tests for both auth dependencies

## Change Log

- 2026-03-25: Story 2.1 implemented — `verify_api_key()` and `verify_supabase_jwt()` replace stubs; PyJWT added; 8 tests added; all 15 tests pass
