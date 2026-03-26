# Story 1.5: Deploy API to Railway with Auto-Restart

Status: done

## Story

As a developer building OpenTalon,
I want the API deployed to Railway with environment variables configured, health check monitoring active, and HTTPS enforced,
So that the proxy is reachable from the CLI and Railway automatically restarts the service on failure.

## Acceptance Criteria

**AC1 — Health endpoint is reachable over HTTPS:**
Given the API is deployed to Railway
When `GET https://<app>.up.railway.app/health` is called
Then the response is `{"status": "ok"}` with HTTP 200 over HTTPS

**AC2 — All required environment variables are configured:**
Given Railway is configured
When the service settings are inspected
Then the following environment variables are set: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `OPENROUTER_API_KEY`

**AC3 — Health check monitoring is active:**
Given Railway is configured
When the service deploy settings are inspected
Then health check path is `/health` and restart policy is enabled on unhealthy status

**AC4 — HTTP requests are redirected to HTTPS:**
Given an HTTP request to `http://<app>.up.railway.app/health`
When the request hits Railway's edge
Then it is redirected to HTTPS (Railway handles TLS termination — no app-level config required)

## Tasks / Subtasks

- [x] Task 1: Fix `database.py` URL scheme for production (AC: 1)
  - [x] Add `postgresql://` → `postgresql+asyncpg://` replacement to `database.py` (see Dev Notes)
  - [x] This ensures the app works whether `DATABASE_URL` uses either scheme

- [x] Task 2: Create `api/railway.toml` with explicit build and deploy config (AC: 1, 3)
  - [x] Create `api/railway.toml` with start command, health check path, and restart policy (see Dev Notes)

- [x] Task 3: Push code to GitHub (prerequisite for Railway)
  - [x] Ensure the project is in a GitHub repository (create one if not already)
  - [x] Commit and push all changes from Stories 1.1–1.5

- [x] Task 4: Create Railway project and connect to GitHub (AC: 1, 3, 4)
  - [x] Sign in to railway.app (create free account if needed)
  - [x] New Project → Deploy from GitHub repo → select your repository
  - [x] In the service settings, set **Root Directory** to `api` (see Dev Notes)
  - [x] Railway will auto-detect Python via `pyproject.toml`

- [x] Task 5: Configure all environment variables in Railway (AC: 2)
  - [x] In the Railway service: Variables tab → add each variable (see Dev Notes for exact values)
  - [x] `DATABASE_URL` — use `postgresql+asyncpg://` scheme (see Dev Notes)
  - [x] `SUPABASE_URL` — from Supabase project settings
  - [x] `SUPABASE_SERVICE_ROLE_KEY` — from Supabase project settings → API → service_role key
  - [x] `SUPABASE_JWT_SECRET` — from Supabase project settings → API → JWT Settings → JWT Secret
  - [x] `OPENROUTER_API_KEY` — from openrouter.ai → Keys

- [x] Task 6: Configure health check and restart policy (AC: 3)
  - [x] Service settings → Deploy tab → Health check path: `/health`
  - [x] Restart policy: "On failure" (Railway default — verify it is set)
  - [x] Note: `railway.toml` already sets these; this step confirms they appear in the UI

- [x] Task 7: Deploy and verify (AC: 1, 4)
  - [x] Trigger deployment (Railway deploys automatically on push, or click "Deploy" manually)
  - [x] Watch build logs — confirm `uv sync` and startup succeed
  - [x] Wait for service to become "Active" (green)
  - [x] Run: `curl https://<your-app>.up.railway.app/health`
  - [x] Expected: `{"status":"ok"}` with HTTP 200

## Dev Notes

### Prerequisite: Stories 1.2 and 1.4 Must Be Complete

This story deploys the API scaffolded in Story 1.2 against the Supabase database created in Story 1.4:
- `src/opentaion_api/main.py` must exist (Story 1.2)
- Supabase project must exist with `DATABASE_URL` available (Story 1.4)
- `api/.env.example` from Story 1.4 lists all required env vars

### Fix `database.py` — URL Scheme Replacement

Railway provides the Supabase `DATABASE_URL` as `postgresql://...`. The async SQLAlchemy engine requires `postgresql+asyncpg://...`. Add the same replacement logic that `alembic/env.py` already uses:

```python
# src/opentaion_api/database.py
import os
from collections.abc import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()

_raw_url = os.environ.get("DATABASE_URL", "")

# Railway provides postgresql:// but asyncpg requires postgresql+asyncpg://
DATABASE_URL = (
    _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if _raw_url.startswith("postgresql://")
    else _raw_url
)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

This is defensive — if `DATABASE_URL` is already set with `postgresql+asyncpg://` (e.g., you set it that way in Railway), the replacement is a no-op. Both forms work.

### Create `api/railway.toml`

This file tells Railway exactly how to build and run the API. Without it, Railway may guess incorrectly or use wrong defaults for a uv-based project:

```toml
# api/railway.toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "uv run fastapi run src/opentaion_api/main.py --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 10
```

**Why `fastapi run` (not `fastapi dev`)?**
- `fastapi dev` is the development server — it has auto-reload, debug mode, and verbose output
- `fastapi run` is the production server — no hot-reload, proper worker handling

**Why `--host 0.0.0.0`?**
Railway containers bind to all interfaces. Without `0.0.0.0`, the server only listens on `127.0.0.1` inside the container and Railway's load balancer can't reach it.

**Why `$PORT`?**
Railway injects a `PORT` environment variable dynamically. Hard-coding `8000` will fail.

**Why `healthcheckTimeout = 300`?**
Railway free tier has cold starts. 300 seconds gives the container time to wake up before Railway considers it unhealthy.

### Setting `Root Directory` in Railway

When connecting your GitHub repo, Railway will try to deploy from the repo root. Since the API lives in `api/`, set the root directory to keep Railway from trying to run it from the wrong place:

1. In Railway: Service → Settings → Source → Root Directory → set to `api`
2. Railway will now treat `api/` as the project root
3. `railway.toml` at `api/railway.toml` will be detected automatically

If you set the root directory AFTER the first deployment attempt, Railway will rebuild.

### Environment Variables to Set in Railway

Go to your Railway service → Variables tab → add each one:

| Variable | Where to get it | Notes |
|---|---|---|
| `DATABASE_URL` | Supabase → Settings → Database → Connection string (URI) | **Use the direct connection, port 5432** — or set to `postgresql+asyncpg://...` directly |
| `SUPABASE_URL` | Supabase → Settings → API → Project URL | Format: `https://[ref].supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Settings → API → `service_role` key (secret) | **Never expose this client-side** — Railway env only |
| `SUPABASE_JWT_SECRET` | Supabase → Settings → API → JWT Settings → JWT Secret | Used by `verify_supabase_jwt()` in Story 2.1 |
| `OPENROUTER_API_KEY` | openrouter.ai → Keys | The master key — never in CLI or web |

**Shortcut for DATABASE_URL:** To avoid the URL scheme issue entirely, copy the Supabase connection string and manually change `postgresql://` to `postgresql+asyncpg://` before pasting into Railway. The `database.py` fix handles this either way, but being explicit is cleaner.

**SUPABASE_SERVICE_ROLE_KEY security rule:** This key bypasses all RLS policies — treat it like a root database password. It belongs exclusively in Railway environment variables. It must never appear in logs, responses, commits, or `.env` files that get committed.

### What Railway Free Tier Does and Doesn't Do

**Does:**
- Auto-deploys on every GitHub push to the connected branch
- Handles TLS termination — `*.up.railway.app` URLs are HTTPS automatically
- Restarts the service when health check fails (with `railway.toml` config)
- Provides logs accessible in the Railway dashboard

**Doesn't / Limitations:**
- Free tier services sleep after inactivity — cold start can take 10–30 seconds
- The CLI's single-retry mechanism (Story 3.5) is the mitigation for this
- Sleeping behavior does NOT affect this story's AC — a single `curl` will wake it

### Verifying Deployment in Build Logs

After triggering deploy, watch the Railway build logs for:

```
✔ Nixpacks: detecting
✔ Python detected
✔ Running uv sync
✔ Installing packages...
✔ Build complete
Starting service...
INFO:     Uvicorn running on http://0.0.0.0:XXXX
```

If you see `ModuleNotFoundError: No module named 'opentaion_api'`:
- The `Root Directory` in Railway is not set to `api/`
- Or `pyproject.toml` doesn't have the `src` layout correctly configured

If you see `asyncpg: invalid DSN: scheme must be ...`:
- `DATABASE_URL` still uses `postgresql://` and the `database.py` fix wasn't deployed
- Or set `DATABASE_URL` to `postgresql+asyncpg://...` directly in Railway

If the health check fails after deploy:
- Check Railway logs — the service may have crashed on startup
- Common cause: missing environment variable (check all 5 are set)
- Run `curl https://<app>.up.railway.app/health` manually to test

### Running `alembic upgrade head` Against Production

Story 1.4 ran migrations against the Supabase database locally. If Story 1.4 was done before this story, migrations are already applied. If not:

```bash
# From api/ with DATABASE_URL pointing to Supabase
alembic upgrade head
```

The Railway deployment itself doesn't run migrations automatically — migrations are always run manually as a one-time operation per environment. Do NOT add migration commands to the Railway start command.

### Architecture Cross-References

From `architecture.md`:
- Railway: free tier, auto-restart on `/health` failure [Source: architecture.md#Infrastructure Decisions]
- Health check: `GET /health` returns `{"status": "ok"}` [Source: architecture.md#API Contract]
- HTTPS enforcement: Railway and Vercel handle TLS termination [Source: architecture.md#Implementation Patterns]
- `SUPABASE_SERVICE_ROLE_KEY` in Railway env vars only — never in code [Source: architecture.md#Authentication & Security]
- Cold start behavior: up to ~30s on free tier; CLI single-retry is the mitigation [Source: architecture.md#Technical Constraints]
- `PORT` environment variable: Railway injects this; must bind to `0.0.0.0:$PORT` [Source: architecture.md#Infrastructure Decisions]

From `epics.md`:
- NFR6: "All client-server communication must use HTTPS; the API must not accept or serve unencrypted HTTP requests" — Railway handles this at the edge [Source: epics.md#NFR6]
- NFR11: "The API must expose a /health endpoint that Railway can poll; the service must restart automatically on unhealthy status" [Source: epics.md#NFR11]
- FR25: "The API exposes a health check endpoint that returns a successful response when the service is operational" [Source: epics.md#FR25]

### What This Story Does NOT Include

Do NOT implement any of the following — they belong to later stories:

- Vercel deployment for the web SPA (Story 1.6)
- Homebrew tap setup (Story 1.6)
- A `Dockerfile` — Railway's Nixpacks handles Python detection automatically
- Running migrations as part of the start command — always manual
- Custom Railway domain setup — the default `*.up.railway.app` domain is sufficient for V1
- Any API routes beyond `/health` — those come in Stories 2.x, 3.x, 4.x
- CI/CD pipeline for automated testing before deploy

### Final Modified/Created Files

```
api/
├── railway.toml                      # NEW — build/deploy/health check config
└── src/
    └── opentaion_api/
        └── database.py               # MODIFIED — added URL scheme replacement
```

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

_none_

### Completion Notes List

- Task 1: `database.py` URL scheme replacement was already correctly implemented in Story 1.2. Added `tests/test_database_url.py` (5 tests) to verify the normalization logic: postgresql:// → postgresql+asyncpg://, no-op for already-correct scheme, empty string, non-postgresql schemes, and single-replacement guarantee.
- Task 2: Created `api/railway.toml` with nixpacks builder, `fastapi run` production start command, `0.0.0.0:$PORT` binding, `/health` healthcheck with 300s timeout, and `on_failure` restart policy with 10 retries.
- Tasks 3–7 (manual): GitHub push, Railway project setup with Root Directory=api, 5 env vars configured, Nixpacks build succeeded, health endpoint verified: GET /health → {"status":"ok"} HTTP 200.
- Railpack 0.22.0 could not detect the uv project — resolved by restoring builder="nixpacks" in railway.toml and setting Root Directory to "api" in Railway UI.

### File List

- `api/railway.toml` (NEW)
- `api/tests/test_database_url.py` (NEW)
- `api/Procfile` (NEW)
- `api/start.sh` (NEW)
- `.gitignore` (NEW)
