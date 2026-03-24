# Story 1.4: Supabase Schema Migrations (Database Foundation)

Status: review

## Story

As a developer building OpenTalon,
I want the `api_keys` and `usage_logs` tables created in Supabase via Alembic migrations with all required indexes and RLS policies,
So that all subsequent API endpoints have a correct, secured data layer to work against.

## Acceptance Criteria

**AC1 — Migration applies without error:**
Given a Supabase project is configured and `DATABASE_URL` is set in `api/.env`
When `alembic upgrade head` is run from `api/`
Then the migration applies without error

**AC2 — Tables exist with correct schema:**
Given the migrations have run
When `public.api_keys` is inspected in Supabase Table Editor
Then it has exactly: `id` (UUID PK DEFAULT gen_random_uuid()), `user_id` (UUID NOT NULL FK → `auth.users(id)` ON DELETE CASCADE), `key_hash` (TEXT NOT NULL), `key_prefix` (TEXT NOT NULL), `created_at` (TIMESTAMPTZ NOT NULL DEFAULT NOW()), `revoked_at` (TIMESTAMPTZ NULL)

When `public.usage_logs` is inspected
Then it has exactly: `id` (UUID PK DEFAULT gen_random_uuid()), `user_id` (UUID NOT NULL FK → `auth.users(id)` ON DELETE CASCADE), `model` (TEXT NOT NULL), `prompt_tokens` (INTEGER NOT NULL), `completion_tokens` (INTEGER NOT NULL), `cost_usd` (NUMERIC(10,8) NOT NULL), `created_at` (TIMESTAMPTZ NOT NULL DEFAULT NOW())

**AC3 — Indexes exist:**
Given the migrations have run
When `public.api_keys` indexes are inspected
Then `idx_api_keys_prefix` on `(key_prefix)` exists AND `idx_api_keys_user` on `(user_id)` exists

When `public.usage_logs` indexes are inspected
Then `idx_usage_logs_user_date` on `(user_id, created_at DESC)` exists

**AC4 — RLS is enabled with correct policies:**
Given the migrations have run
When RLS policy status is checked (via Supabase Dashboard → Authentication → Policies)
Then:
- RLS is ENABLED on `public.api_keys`
- RLS is ENABLED on `public.usage_logs`
- `api_keys` has SELECT policy: `USING (auth.uid() = user_id)`
- `api_keys` has INSERT policy: `WITH CHECK (auth.uid() = user_id)`
- `api_keys` has UPDATE policy: `USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id)`
- `usage_logs` has SELECT policy: `USING (auth.uid() = user_id)`
- `usage_logs` has NO INSERT policy (service role only — zero INSERT policy = no direct access)

## Tasks / Subtasks

- [ ] Task 1: Create Supabase project (prerequisite — skip if already exists)
  - [ ] Create a new project at supabase.com (free tier is sufficient)
  - [ ] Note the project ref (appears in project URL: `https://supabase.com/dashboard/project/<ref>`)
  - [ ] Go to Project Settings → Database → Copy the "Connection string" (URI format, port 5432, NOT the pooler at 6543)
  - [ ] Note: the URI format is `postgresql://postgres:[YOUR-PASSWORD]@db.[ref].supabase.co:5432/postgres`

- [ ] Task 2: Configure local environment (prerequisite)
  - [ ] Create `api/.env` (already gitignored) with:
    ```
    DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[ref].supabase.co:5432/postgres
    ```
  - [ ] Create `api/.env.example` listing required vars without values (see Dev Notes)
  - [ ] Add `load_dotenv()` call to `src/opentaion_api/database.py` (see Dev Notes)

- [ ] Task 3: Create SQLAlchemy ORM models (AC: 1, 2)
  - [ ] Create `src/opentaion_api/models.py` with `ApiKey` and `UsageLog` classes (see Dev Notes)
  - [ ] Both models must extend `Base` from `database.py`

- [ ] Task 4: Update `alembic/env.py` to reference model metadata (AC: 1)
  - [ ] Add `load_dotenv()` call at top of env.py (before DATABASE_URL is read)
  - [ ] Uncomment the `from opentaion_api.database import Base` import
  - [ ] Set `target_metadata = Base.metadata`
  - [ ] Ensure the models are imported so Base.metadata is populated (see Dev Notes)

- [ ] Task 5: Write the Alembic migration manually (AC: 1, 2, 3, 4)
  - [ ] Run `alembic revision -m "create api keys and usage logs"` from `api/` to generate the file
  - [ ] Fill in the `upgrade()` and `downgrade()` functions (see Dev Notes for exact content)
  - [ ] Do NOT use `--autogenerate` — the cross-schema FK to `auth.users` requires manual migration

- [ ] Task 6: Apply migration and verify (AC: 1, 2, 3, 4)
  - [ ] Run `alembic upgrade head` from `api/`
  - [ ] Open Supabase Dashboard → Table Editor → verify `api_keys` and `usage_logs` exist
  - [ ] Open Supabase Dashboard → Authentication → Policies → verify RLS is enabled and policies exist
  - [ ] Run `alembic current` — should show the migration as the current head

## Dev Notes

### Prerequisite: Story 1.2 Must Be Complete

This story modifies files created in Story 1.2:
- `api/alembic/env.py` (update async env.py to reference models)
- `api/src/opentaion_api/database.py` (add `load_dotenv()`)

If Story 1.2 is not done, do Story 1.2 first.

### DATABASE_URL: Direct Connection (Port 5432), NOT Pooler (Port 6543)

Supabase provides two connection strings. **Use the direct connection for Alembic migrations:**

| Connection type | Port | Use for |
|---|---|---|
| Direct connection | 5432 | Alembic migrations ← use this |
| Connection pooler (Supavisor) | 6543 | Application runtime (Stories 1.5+) |

Alembic creates transactions that can hold connections open during long migrations. The pooler is for short-lived request-response cycles. Wrong connection string = migration hangs or fails with "prepared transactions not supported."

**Where to find it:** Supabase Dashboard → Project Settings → Database → "Connection string" → URI → make sure you select port 5432.

### Create `api/.env.example`

Commit this file (it shows required vars without real values):

```bash
# api/.env.example
# Copy to .env and fill in real values for local development
# Production values are set as Railway environment variables
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[ref].supabase.co:5432/postgres
SUPABASE_URL=https://[ref].supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here
SUPABASE_JWT_SECRET=your-jwt-secret-here
OPENROUTER_API_KEY=your-openrouter-key-here
```

### Update `src/opentaion_api/database.py`

Add `load_dotenv()` so local development picks up `api/.env`. The file as written in Story 1.2 reads `DATABASE_URL` from `os.environ` — without `load_dotenv()`, Alembic and the dev server won't find it locally:

```python
# src/opentaion_api/database.py
import os
from collections.abc import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()  # ← ADD THIS LINE (reads api/.env for local dev; no-op in Railway where env vars are set directly)

DATABASE_URL = os.environ.get("DATABASE_URL", "")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

Note: `load_dotenv()` is a no-op when the env var is already set (e.g., in Railway). Safe to call unconditionally.

### Create `src/opentaion_api/models.py`

Define both ORM models. These will be used by auth dependencies (Story 2.1), CRUD endpoints (Story 2.2), proxy (Story 3.2), and usage (Story 4.1):

```python
# src/opentaion_api/models.py
import uuid
from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from opentaion_api.database import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    key_hash: Mapped[str] = mapped_column(Text, nullable=False)
    key_prefix: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
    )


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )
```

**Why both `server_default` and `default` on `id`?**
- `server_default=sa.text("gen_random_uuid()")` — database-side UUID generation on INSERT (production path)
- `default=uuid.uuid4` — Python-side UUID generation when creating objects without a DB (test path)

**Why no `total_tokens` column?**
From architecture.md: "Don't store derived data twice." `total_tokens = prompt_tokens + completion_tokens` — computed in query when needed, not stored.

**Why `Decimal` for `cost_usd`?**
Float arithmetic is imprecise for monetary values. `decimal.Decimal` is exact. SQLAlchemy maps `Numeric(10,8)` to Python `Decimal` automatically. Serialize as string in JSON responses (Stories 4.x) — never as float.

### Update `alembic/env.py`

Story 1.2 left `target_metadata = None` (commented out import). Update to reference models:

```python
# alembic/env.py
# Add these lines after the existing imports:
from dotenv import load_dotenv

load_dotenv()  # Load api/.env before DATABASE_URL is read by get_url()

# Replace the commented-out lines with:
from opentaion_api.database import Base
import opentaion_api.models  # noqa: F401 — imports register models on Base.metadata

target_metadata = Base.metadata
```

**Why the `import opentaion_api.models` line?**
SQLAlchemy models register themselves on `Base.metadata` only when their module is imported. Without this import, `Base.metadata` is empty and autogenerate produces nothing. The `# noqa: F401` suppresses the "unused import" linter warning — the import is intentional.

### Write the Migration File Manually

**Do NOT use `--autogenerate` for this migration.** Reasons:
1. Alembic autogenerate doesn't know about the `auth` schema in Supabase — it will fail or generate incomplete FK constraints
2. RLS policies (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY` and `CREATE POLICY`) are pure SQL — Alembic's autogenerate never generates these
3. The DESC index (`created_at DESC`) requires raw SQL

**Step 1:** Generate the empty revision file:
```bash
cd api
alembic revision -m "create api keys and usage logs"
```

**Step 2:** Open the generated file in `alembic/versions/` and replace its `upgrade()` and `downgrade()` with:

```python
# alembic/versions/xxxx_create_api_keys_and_usage_logs.py
"""create api keys and usage logs

Revision ID: (auto-generated)
Revises:
Create Date: (auto-generated)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "(auto-generated by Alembic)"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── api_keys ───────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE public.api_keys (
            id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            key_hash    TEXT        NOT NULL,
            key_prefix  TEXT        NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            revoked_at  TIMESTAMPTZ NULL
        )
    """)
    op.execute("CREATE INDEX idx_api_keys_prefix ON public.api_keys (key_prefix)")
    op.execute("CREATE INDEX idx_api_keys_user   ON public.api_keys (user_id)")

    # ── usage_logs ─────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE public.usage_logs (
            id                UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id           UUID          NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            model             TEXT          NOT NULL,
            prompt_tokens     INTEGER       NOT NULL,
            completion_tokens INTEGER       NOT NULL,
            cost_usd          NUMERIC(10,8) NOT NULL,
            created_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_usage_logs_user_date ON public.usage_logs (user_id, created_at DESC)")

    # ── RLS ───────────────────────────────────────────────────────────────────
    op.execute("ALTER TABLE public.api_keys   ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.usage_logs ENABLE ROW LEVEL SECURITY")

    # api_keys policies — authenticated web users manage their own keys
    op.execute("""
        CREATE POLICY "Users can view own keys"
        ON public.api_keys FOR SELECT
        USING (auth.uid() = user_id)
    """)
    op.execute("""
        CREATE POLICY "Users can create own keys"
        ON public.api_keys FOR INSERT
        WITH CHECK (auth.uid() = user_id)
    """)
    op.execute("""
        CREATE POLICY "Users can revoke own keys"
        ON public.api_keys FOR UPDATE
        USING (auth.uid() = user_id)
        WITH CHECK (auth.uid() = user_id)
    """)

    # usage_logs policies — web users can read; INSERT is service-role-only (no INSERT policy)
    op.execute("""
        CREATE POLICY "Users can view own usage"
        ON public.usage_logs FOR SELECT
        USING (auth.uid() = user_id)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.usage_logs")
    op.execute("DROP TABLE IF EXISTS public.api_keys")
```

**Why raw SQL (`op.execute`) instead of `op.create_table`?**
- `REFERENCES auth.users(id)` is a cross-schema FK — `op.create_table` with `sa.ForeignKey("auth.users.id")` can produce incorrect DDL on some Alembic/SQLAlchemy versions
- RLS statements have no `op.*` equivalent — must use `op.execute` anyway
- Raw SQL is explicit, readable, and matches the architecture document exactly

**Keep the revision/down_revision values auto-generated by Alembic** — do not change them manually.

### Run `alembic upgrade head`

```bash
cd api
alembic upgrade head
```

Expected output:
```
INFO  [alembic.runtime.migration] Context impl PostgreSQLImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> <revision>, create api keys and usage logs
```

If you see errors:
- `connection refused` → wrong DATABASE_URL or Supabase project not running
- `SSL connection has been closed unexpectedly` → use the direct connection (port 5432), not pooler
- `function gen_random_uuid() does not exist` → Supabase PostgreSQL is older than 13 (very unlikely — Supabase uses PG 15+)
- `column "id" is of type uuid but expression is of type text` → PostgreSQL extension issue (unlikely on Supabase)

### Verify in Supabase Dashboard

After `alembic upgrade head` succeeds, verify in the Supabase dashboard:

1. **Table Editor** → should show `api_keys` and `usage_logs` in the `public` schema
2. **Authentication → Policies** → should show policies on both tables
3. **Database → Indexes** → should show the three indexes

You can also verify via SQL in Supabase's SQL Editor:
```sql
-- Check tables exist
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' AND table_name IN ('api_keys', 'usage_logs');

-- Check RLS is enabled
SELECT tablename, rowsecurity FROM pg_tables
WHERE schemaname = 'public' AND tablename IN ('api_keys', 'usage_logs');

-- Check policies
SELECT tablename, policyname, cmd FROM pg_policies
WHERE schemaname = 'public';

-- Check indexes
SELECT indexname, tablename FROM pg_indexes
WHERE schemaname = 'public' AND tablename IN ('api_keys', 'usage_logs');
```

### Alembic Version Tracking

Alembic tracks applied migrations in a `alembic_version` table it creates automatically. After running the migration, `alembic current` should show your revision hash:
```bash
alembic current
# INFO  [alembic.runtime.migration] Context impl PostgreSQLImpl.
# <revision_hash> (head)
```

If you need to roll back: `alembic downgrade base` (drops both tables — use with caution).

### No Pytest Tests for This Story

Unlike Stories 1.1 and 1.2, there are no automated tests for this story. The acceptance criteria requires a live Supabase database, which is impractical for a pytest suite at this stage. Verification is manual via Supabase Dashboard and `alembic current`.

Story 2.1 (auth dependencies) will introduce test fixtures for database access. Story 1.4's schema is the foundation those tests sit on.

### Architecture Cross-References

From `architecture.md`:
- Database schema design: `api_keys` + `usage_logs` tables, FK to `auth.users(id)`, `revoked_at` timestamp pattern, `cost_usd` stored at write time [Source: architecture.md#Database Schema]
- `SUPABASE_SERVICE_ROLE_KEY` for all DB operations via FastAPI — service role bypasses RLS [Source: architecture.md#Authentication & Security]
- Index on `(user_id, created_at DESC)` covers the 30-day dashboard query exactly [Source: architecture.md#Database Schema]
- No `total_tokens` computed column — sum in query when needed [Source: architecture.md#Database Schema]
- Naming: tables plural snake_case, indexes `idx_{table}_{column}` [Source: architecture.md#Implementation Patterns]

From `epics.md` Additional Requirements:
- "Database schema (blocks everything): Two tables required before any endpoint can be implemented" [Source: epics.md#Additional Requirements]
- "No `public.users` mirror table: All FK references point to `auth.users(id)` directly" [Source: epics.md#Additional Requirements]
- "Supabase RLS policies: Row-level security on both tables" [Source: epics.md#Additional Requirements]
- "FastAPI uses `SUPABASE_SERVICE_ROLE_KEY` for all DB operations (Railway env var only)" [Source: epics.md#Additional Requirements]
- "cost_usd stored at write time: Computed from `model_pricing` dict at moment of usage log write. Not recomputed on query." [Source: epics.md#Additional Requirements]
- "revoked_at timestamp pattern: API key revocation sets `revoked_at = NOW()`, not a boolean." [Source: epics.md#Additional Requirements]

### What This Story Does NOT Include

Do NOT implement any of the following — they belong to later stories:

- Real `verify_api_key()` / `verify_supabase_jwt()` implementations (Story 2.1 — `deps.py` stubs remain)
- Any API endpoint using these tables (Stories 2.x, 3.x, 4.x)
- The `model_pricing` dict or `compute_cost()` function (Story 3.1)
- The Supabase Auth magic link setup (Story 2.3 handles web auth; just creating a project here)
- Deploying the API to Railway (Story 1.5)
- Seeding the database with test data
- A `schemas/` Pydantic module (Story 2.2 introduces Pydantic schemas alongside CRUD endpoints)

### Final Modified/Created Files

After this story completes, the following files will have changed from Story 1.2:

```
api/
├── .env                              # NEW — real DATABASE_URL (gitignored)
├── .env.example                      # NEW — template (committed)
├── alembic/
│   ├── env.py                        # MODIFIED — load_dotenv + Base.metadata import
│   └── versions/
│       └── xxxx_create_api_keys_and_usage_logs.py  # NEW — manual migration
└── src/
    └── opentaion_api/
        ├── database.py               # MODIFIED — added load_dotenv() call
        └── models.py                 # NEW — ApiKey + UsageLog ORM models
```

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Fixed `alembic/env.py`: `context.configure(conn=conn)` → `context.configure(connection=connection)` and restructured two-lambda pattern into single `do_run_migrations(connection)` function
- Fixed `database.py`: added `postgresql://` → `postgresql+asyncpg://` scheme replacement so asyncpg driver is used (not psycopg2)
- `alembic upgrade head` succeeded on first run after both fixes

### Completion Notes List

- All 6 tasks complete
- Migration `88a7cdb79508` applied at head
- `alembic current` confirms `88a7cdb79508 (head)`
- No pytest tests per story spec (live DB required; Story 2.1 introduces fixtures)

### File List

- `api/.env` — NEW (gitignored, real DATABASE_URL)
- `api/.env.example` — NEW (committed template)
- `api/alembic/env.py` — MODIFIED (load_dotenv, Base.metadata, fixed async pattern)
- `api/alembic/versions/88a7cdb79508_create_api_keys_and_usage_logs.py` — NEW
- `api/src/opentaion_api/database.py` — MODIFIED (load_dotenv, asyncpg scheme replacement)
- `api/src/opentaion_api/models.py` — NEW (ApiKey, UsageLog ORM models)
