# Story 1.2: Initialize API FastAPI Service with Health Check

Status: done

## Story

As a developer building OpenTalon,
I want the API project scaffolded with FastAPI, Alembic, async SQLAlchemy, and a working `/health` endpoint,
So that Railway can monitor service health and the API is deployable from day one.

## Acceptance Criteria

**AC1 — Directory structure is correct:**
Given the API project is initialized
When `api/` is examined
Then it contains ALL of the following:
- `src/opentaion_api/main.py` — FastAPI app instance with `/health` route mounted
- `src/opentaion_api/routers/` — directory (empty `__init__.py` is sufficient for now)
- `src/opentaion_api/deps.py` — placeholder stubs for `verify_api_key` and `verify_supabase_jwt`
- `src/opentaion_api/database.py` — async engine + `AsyncSession` + `get_db` async generator
- `alembic/` — directory with `env.py` configured for async SQLAlchemy (using `asyncio.run`)
- `uv.lock` — present and committed
- `pyproject.toml` — with all required dependencies (see Dev Notes)

**AC2 — Health endpoint returns correct response:**
Given the API server is running locally via `fastapi dev`
When `GET /health` is called
Then the response is `{"status": "ok"}` with HTTP 200

**AC3 — Test suite passes:**
Given a test is run
When `uv run pytest` is executed from `api/`
Then the test for `GET /health` passes using FastAPI's `TestClient`

## Tasks / Subtasks

- [x] Task 1: Scaffold API package with uv (AC: 1)
  - [x] From `api/`, run `uv init .` (or adjust if `api/` already partially exists — check first with `ls api/`)
  - [x] Add runtime dependencies: `uv add "fastapi[standard]>=0.110" "sqlalchemy[asyncio]>=2.0" alembic asyncpg bcrypt python-dotenv httpx supabase`
  - [x] Add dev dependencies: `uv add --dev pytest pytest-asyncio httpx`
  - [x] Verify `uv.lock` is generated

- [x] Task 2: Create src layout with correct package structure (AC: 1)
  - [x] Create `src/opentaion_api/__init__.py`
  - [x] Create `src/opentaion_api/main.py` with FastAPI app + `/health` route
  - [x] Create `src/opentaion_api/routers/__init__.py`
  - [x] Create `src/opentaion_api/deps.py` with placeholder auth stubs
  - [x] Create `src/opentaion_api/database.py` with async engine + `get_db`
  - [x] Update `pyproject.toml` to use `src` layout

- [x] Task 3: Initialize and configure Alembic for async SQLAlchemy (AC: 1)
  - [x] Run `alembic init alembic` from `api/`
  - [x] Update `alembic/env.py` to use `asyncio.run()` + async engine (see Dev Notes — critical)
  - [x] Update `alembic.ini` to set `sqlalchemy.url` to a placeholder (real URL comes from env in Story 1.4)
  - [x] Verify `alembic/versions/` directory exists (empty is fine)

- [x] Task 4: Write TDD tests first, then verify AC (AC: 3)
  - [x] Create `tests/__init__.py`
  - [x] Create `tests/test_health.py` with `GET /health` test using `TestClient`
  - [x] Confirm test fails before implementation (red)
  - [x] Verify test passes after implementation (green)
  - [x] Run `uv run pytest` — must exit 0

## Dev Notes

### Package Manager — uv (MANDATORY)
- **Never use `pip` or `poetry`** — this project uses `uv` exclusively
- Initialize from inside `api/`: `uv init .` (note the `.` — not `uv init api`)
- All installs: `uv add <package>` and `uv add --dev <package>`
- Run: `uv run pytest`, `fastapi dev src/opentaion_api/main.py`

### Pre-existing `api/` directory
`api/` appears as untracked in git. **Check its current state before initializing:**
```bash
ls api/
```
If `pyproject.toml` already exists there, read it and adjust rather than overwrite. Goal state is the structure described in AC1.

### Required pyproject.toml Shape

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "opentaion-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi[standard]>=0.110",
    "sqlalchemy[asyncio]>=2.0",
    "alembic",
    "asyncpg",
    "bcrypt",
    "python-dotenv",
    "httpx",
    "supabase",
]

[tool.hatch.build.targets.wheel]
packages = ["src/opentaion_api"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[dependency-groups]
dev = [
    "pytest",
    "pytest-asyncio",
    "httpx",
]
```

Note: `httpx` appears in both runtime and dev deps — runtime because the proxy forwards requests via `httpx.AsyncClient`; dev because FastAPI's `TestClient` is based on httpx. Both entries are intentional.

### Required File Contents

**`src/opentaion_api/main.py`** — FastAPI app, `/health` route only. Do NOT add any other routes in this story:

```python
# src/opentaion_api/main.py
from fastapi import FastAPI

app = FastAPI(title="opentaion-api", version="0.1.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
```

**`src/opentaion_api/database.py`** — Async SQLAlchemy engine and session factory. `DATABASE_URL` comes from environment (set in Railway, not `.env` in this story — just scaffold the loading):

```python
# src/opentaion_api/database.py
import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.environ.get("DATABASE_URL", "")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

> **Important:** `DATABASE_URL` for asyncpg must use the `postgresql+asyncpg://` scheme, NOT `postgresql://`. Railway provides `postgresql://` — the caller (Alembic env.py) must replace the scheme. See Alembic section below.

**`src/opentaion_api/deps.py`** — Placeholder stubs. These will be fully implemented in Story 2.1. Do NOT implement any real auth logic here:

```python
# src/opentaion_api/deps.py
"""
Authentication dependency placeholders.
Implemented fully in Story 2.1.
"""
import uuid
from fastapi import HTTPException, Header


async def verify_api_key(
    authorization: str = Header(...),
) -> uuid.UUID:
    """Validates OpenTalon API key (bcrypt). Implemented in Story 2.1."""
    raise HTTPException(status_code=501, detail="Not implemented")


async def verify_supabase_jwt(
    authorization: str = Header(...),
) -> uuid.UUID:
    """Validates Supabase JWT for web routes. Implemented in Story 2.1."""
    raise HTTPException(status_code=501, detail="Not implemented")
```

**`src/opentaion_api/routers/__init__.py`** — Empty:
```python
# src/opentaion_api/routers/__init__.py
```

**`src/opentaion_api/__init__.py`** — Empty:
```python
# src/opentaion_api/__init__.py
```

### CRITICAL: Alembic Async Configuration

`alembic init alembic` generates a **synchronous** `env.py`. The entire `run_migrations_online()` function must be replaced with an **async version**. Failing to do this is the single most common mistake when setting up FastAPI + async SQLAlchemy + Alembic.

After running `alembic init alembic`, replace the `run_migrations_online` function in `alembic/env.py` with this async version:

```python
# alembic/env.py
# ... (keep the file header and imports as generated) ...
import asyncio
import os
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import your models' Base so Alembic can autogenerate migrations later
# (No models yet in this story, but the import path is set up now)
# from opentaion_api.database import Base
# target_metadata = Base.metadata
target_metadata = None


def get_url() -> str:
    url = os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url", ""))
    # Railway provides postgresql:// but asyncpg requires postgresql+asyncpg://
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(get_url())
    async with connectable.connect() as connection:
        await connection.run_sync(
            lambda conn: context.configure(conn=conn, target_metadata=target_metadata)
        )
        async with connection.begin():
            await connection.run_sync(lambda conn: context.run_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

Also update `alembic.ini` — set `sqlalchemy.url` to a placeholder so offline mode has something:
```ini
sqlalchemy.url = postgresql+asyncpg://placeholder/placeholder
```

The real `DATABASE_URL` is always read from the environment (Railway env var) — the placeholder is only used for `alembic revision --autogenerate` in local development where the env var is set in `.env`.

### Test Requirements

**Write the test FIRST (TDD), confirm it fails, then implement:**

```python
# tests/test_health.py
from fastapi.testclient import TestClient
from opentaion_api.main import app

client = TestClient(app)


def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_correct_body():
    response = client.get("/health")
    assert response.json() == {"status": "ok"}
```

- `TestClient` is synchronous — no `async def` needed in these tests
- `TestClient` comes from `fastapi` (re-exported from `httpx`) — no extra import needed beyond `fastapi.testclient`

### Final Directory Structure

After this story is complete, `api/` must look exactly like this:

```
api/
├── pyproject.toml
├── uv.lock
├── alembic.ini
├── alembic/
│   ├── env.py              # async-configured (see above)
│   ├── script.py.mako
│   └── versions/           # empty — migrations come in Story 1.4
├── src/
│   └── opentaion_api/
│       ├── __init__.py
│       ├── main.py         # FastAPI app + /health
│       ├── database.py     # async engine + get_db
│       ├── deps.py         # auth placeholder stubs
│       └── routers/
│           └── __init__.py
└── tests/
    ├── __init__.py
    └── test_health.py      # GET /health tests
```

### Architecture Cross-References

From `architecture.md`:
- No official FastAPI scaffold — structure is manual [Source: architecture.md#API FastAPI]
- Async SQLAlchemy: `create_async_engine`, `AsyncSession` throughout [Source: architecture.md#API FastAPI]
- Two auth dependencies: `verify_api_key()` (bcrypt) for CLI routes; `verify_supabase_jwt()` for web routes [Source: architecture.md#Authentication & Security]
- Railway health check: `GET /health` returns `{"status": "ok"}` [Source: architecture.md#API Contract]
- `SUPABASE_SERVICE_ROLE_KEY` as Railway env var only — never in code [Source: architecture.md#Authentication & Security]

From `epics.md`:
- Additional Requirements: "FastAPI uses `SUPABASE_SERVICE_ROLE_KEY` for all DB operations (Railway env var only)" [Source: epics.md#Additional Requirements]
- Additional Requirements: "Starter templates: API via manual FastAPI structure + `uv add "fastapi[standard]>=0.110" ...`" [Source: epics.md#Additional Requirements]
- NFR11: "The API must expose a /health endpoint that Railway can poll; the service must restart automatically on unhealthy status" [Source: epics.md#NFR11]

### What This Story Does NOT Include

Do NOT implement any of the following — they belong to later stories:
- Any database migration or schema creation (Story 1.4)
- Real `verify_api_key()` or `verify_supabase_jwt()` implementations (Story 2.1)
- Any `/v1/chat/completions`, `/api/keys`, or `/api/usage` routes (Stories 2.x, 3.x, 4.x)
- Loading any `.env` file — `database.py` reads from `os.environ` but no `load_dotenv()` call is needed in this story since we're not connecting to a real DB
- A `Dockerfile` or Railway-specific config — those come in Story 1.5

### Dependency Note: `supabase` Package

The `supabase` Python SDK is added here (even though it's not used until Story 2.x) because it is a dependency of the auth layer and adding it now avoids a `uv.lock` churn in the middle of Story 2.1. It does not need to be imported in this story.

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

_none_

### Completion Notes List

- `api/` contained only `CLAUDE.md` and `.env` — scaffolded from scratch with `uv init .`
- `pyproject.toml` generated by uv then updated to hatchling/src layout with correct project name `opentaion-api`
- `uv sync` re-ran after pyproject.toml update to register the src package
- `alembic init alembic` generated synchronous `env.py` — fully replaced with async version using `asyncio.run(run_migrations_online())`
- `alembic.ini` `sqlalchemy.url` updated from placeholder `driver://user:pass@localhost/dbname` to `postgresql+asyncpg://placeholder/placeholder`
- `database.py` reads `DATABASE_URL` from env — no `load_dotenv()` call since no real DB needed in this story
- TDD: `test_health.py` written first (confirmed ImportError on red), then `main.py` implemented (green)
- Full suite: 2 tests, 2 passed

### File List

- `api/pyproject.toml` — NEW (via uv init, then rewritten to hatchling shape)
- `api/uv.lock` — NEW
- `api/alembic.ini` — NEW (sqlalchemy.url set to placeholder)
- `api/alembic/env.py` — NEW (async-configured)
- `api/alembic/script.py.mako` — NEW (generated by alembic init)
- `api/alembic/README` — NEW (generated by alembic init)
- `api/alembic/versions/` — NEW (empty directory)
- `api/src/opentaion_api/__init__.py` — NEW
- `api/src/opentaion_api/main.py` — NEW
- `api/src/opentaion_api/database.py` — NEW
- `api/src/opentaion_api/deps.py` — NEW
- `api/src/opentaion_api/routers/__init__.py` — NEW
- `api/tests/__init__.py` — NEW
- `api/tests/test_health.py` — NEW
