---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
lastStep: 8
status: 'complete'
completedAt: '2026-03-24'
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
  - _bmad-output/planning-artifacts/product-brief-opentaion-2026-03-23.md
workflowType: 'architecture'
project_name: 'opentaion'
user_name: 'Miao'
date: '2026-03-24'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements (26 total):**

- **Authentication & Identity (FR1–FR5):** Dual auth surfaces — CLI via magic link +
  API key paste; web via magic link + Supabase session. API key CRUD (generate,
  list, revoke) is a first-class feature, not an afterthought. The cross-context
  key handoff (browser → terminal during `opentaion login`) is the highest-friction
  onboarding moment and must be explicitly supported by the web UI layout.

- **Task Execution & Effort Routing (FR6–FR11):** The `/effort [low|medium|high]`
  command is the product's core interaction primitive. The CLI stores credentials
  globally (`~/.opentaion/config.json`), not per-project. Single retry then hard
  exit on proxy failure — no silent degradation.

- **LLM Proxying (FR12–FR15):** Transparent gateway pattern — the API does not
  transform the request body. Key swap is the only mutation: user's OpenTalon key
  → server's master OpenRouter key. Usage logging is async and must not block the
  response path.

- **Usage Metering & Storage (FR16–FR19):** Raw token counts always stored; cost
  is always derived server-side from a model pricing table. Cost is never accepted
  from the client. This is both a security constraint and the accuracy guarantee.

- **Usage Visibility & Distribution (FR20–FR26):** 30-day usage chart + per-model
  cost table + API key management in the authenticated web view. Homebrew as the
  CLI install surface.

**Non-Functional Requirements:**

- **Performance:** <200ms proxy overhead (hard limit, not target — shapes async
  design throughout). <2s for `/api/usage`. <3s dashboard load.
- **Security:** bcrypt key hashing; keys displayed once only; HTTPS-only; master
  OpenRouter key never leaves server environment.
- **Reliability:** Async logging failures are silent to the user. CLI exits within
  5 seconds of proxy failure after one retry. Railway health check required.
- **Integration:** Accept any syntactically valid OpenRouter-compatible body without
  inspection. Server-side pricing computation only (no external pricing API in
  request path).

**Scale & Complexity:**

- Primary domain: Developer tooling (CLI + API + SPA)
- Complexity level: Low — no regulated domain, no multi-tenancy, standard
  relational data, single external integration (OpenRouter)
- Architectural components: 3 (CLI, API, Web) + 1 managed service (Supabase)

### Technical Constraints & Dependencies

- **OpenRouter dependency:** All LLM calls route through OpenRouter. The API's
  model pricing table must be keyed by OpenRouter model IDs. Free-tier model
  availability is an external risk.
- **Railway free-tier cold start:** Up to ~30 seconds to wake. The CLI's single-retry
  mechanism is the mitigation. Not an architecture problem — a documented operational
  behavior.
- **Supabase as both auth and database:** Supabase Auth handles magic links for both
  CLI (web confirmation) and web dashboard. Supabase PostgreSQL stores users, API
  keys (bcrypt-hashed), and usage records. This creates a single managed dependency
  for auth + data.
- **macOS-only in V1:** No Windows, no Linux. CLI distribution is Homebrew tap only.
- **No streaming:** Output is printed after task completion, not incrementally.
  Simplifies the proxy — no SSE/chunked transfer handling needed in V1.

### Cross-Cutting Concerns Identified

1. **Dual authentication model:** CLI path (bcrypt key validation) and web path
   (Supabase JWT validation) must map to the same `user_id` in every table. Every
   endpoint must declare which auth method it accepts.
2. **Async logging reliability:** The `POST /v1/chat/completions` handler must return
   the OpenRouter response before the usage write completes. Background task failure
   must be logged to stdout but not propagate to the response. This pattern appears
   once in the codebase but is the product's reliability contract.
3. **Server-side cost computation:** A model pricing table (keyed by model ID) must
   be maintained in the API. This table is the source of truth for all cost figures
   in the system — CLI display, dashboard chart, and per-model summary table all
   derive from it.
4. **HTTPS enforcement:** All three components must enforce HTTPS in production.
   Railway and Vercel handle TLS termination. The API must not serve HTTP.
5. **Clean failure propagation:** The CLI must exit with code 1 and a specific error
   message on proxy failure. No silent fallbacks to direct API calls — the metering
   contract must hold or the command must fail visibly.

## Starter Template Evaluation

### Primary Technology Domain

Multi-component developer tooling: Python CLI + Python API backend + TypeScript SPA.
Tech stack is fully pre-specified. This section documents initialization commands
and structural decisions per component — not a comparison of alternatives.

### Component Initialization

#### CLI — Python Package (uv)

```bash
cd opentaion
uv init cli
cd cli
uv add click rich httpx python-dotenv
uv add --dev pytest pytest-asyncio
```

**Architectural decisions established:**
- **Package manager:** uv (not pip, not poetry) — lock file is `uv.lock`
- **Entry point:** `cli/src/opentaion/__main__.py` — enables `uv run python -m opentaion`
- **Config storage:** `~/.opentaion/config.json` — global, not project-scoped
- **Output:** Rich Console — all terminal output routed through a single Console instance
- **Async HTTP:** `httpx.AsyncClient` running in an asyncio event loop — all network
  calls (proxy forwarding, OpenRouter requests) are async. No streaming responses in V1,
  but the async foundation is in place for future use.

#### API — FastAPI (no official scaffold; manual structure)

```bash
cd opentaion/api
uv init .
uv add "fastapi[standard]>=0.110" "sqlalchemy[asyncio]>=2.0" alembic \
        asyncpg bcrypt python-dotenv httpx supabase
uv add --dev pytest pytest-asyncio httpx
alembic init alembic
```

**Architectural decisions established:**
- **No scaffolding tool** — FastAPI has no official `create` command; structure is manual
- **Async SQLAlchemy** — `create_async_engine`, `AsyncSession` throughout
- **Alembic** — migration history lives in `api/alembic/versions/`
- **Two auth dependencies:** `verify_api_key()` (bcrypt) for CLI routes;
  `verify_supabase_jwt()` for web routes — each declared explicitly per endpoint
- **Background tasks via FastAPI's `BackgroundTasks`** — usage write passed as
  background task in `/v1/chat/completions` handler; no Celery, no Redis

#### Web — Vite + React + TypeScript

```bash
cd opentaion
npm create vite@latest web -- --template react-ts
cd web
npm install
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
npm install recharts
```

**Architectural decisions established:**
- **No router** — two views (unauthenticated / authenticated) use conditional
  rendering on Supabase auth state: `user ? <Dashboard /> : <LoginPage />`
- **No component library** — raw Tailwind utility classes only (no shadcn/ui)
- **Single data fetch** — `GET /api/usage` on mount; no polling, no WebSocket
- **Layout:** Two-panel authenticated view — 220px fixed sidebar + main content area,
  both as plain Tailwind `div`s

### No Starter Ambiguity

All three components use well-established initialization patterns with no competing
options to evaluate. The tech stack decisions are locked in the project's `CLAUDE.md`
and this PRD.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Database schema with FK strategy and index design
- Dual authentication dependency injection pattern
- `key_prefix` + bcrypt lookup flow for API key validation
- FastAPI service role access (bypasses RLS; FastAPI is trusted infrastructure)

**Important Decisions (Shape Architecture):**
- `model_pricing` as Python dict (not DB table) — redeploy to update, no migration
- `revoked_at` timestamp instead of boolean `is_active` — preserves audit history
- `cost_usd` stored at write time from server-side dict — not recomputed on query
- No `public.users` mirror table — reference `auth.uid()` directly

**Deferred Decisions (Post-MVP):**
- Dead-letter table for failed async usage writes
- Session-level cost attribution (Phase 2)
- Per-project cost keys (Phase 2)

### Data Architecture

**No `public.users` mirror table.** All FK references point to `auth.users(id)` via
`auth.uid()`. Supabase Auth manages identity; no mirror needed for V1's single-user-
per-account model.

**`model_pricing` is a Python dict, not a DB table.** A DB table requires a migration
every time OpenRouter adjusts pricing. A redeploy is sufficient at V1 scale. No ORM
query in the request path.

```sql
-- api_keys
CREATE TABLE public.api_keys (
    id          UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID          NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    key_hash    TEXT          NOT NULL,       -- bcrypt hash of full key (cost=12)
    key_prefix  TEXT          NOT NULL,       -- first 12 chars e.g. "ot_abc12345"
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    revoked_at  TIMESTAMPTZ   NULL            -- NULL = active; set to NOW() on revoke
);
CREATE INDEX idx_api_keys_prefix ON public.api_keys(key_prefix);
CREATE INDEX idx_api_keys_user   ON public.api_keys(user_id);

-- usage_logs
CREATE TABLE public.usage_logs (
    id                UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID          NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    model             TEXT          NOT NULL,  -- OpenRouter model ID
    prompt_tokens     INTEGER       NOT NULL,
    completion_tokens INTEGER       NOT NULL,
    cost_usd          NUMERIC(10,8) NOT NULL,  -- derived server-side at write time
    created_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_usage_logs_user_date ON public.usage_logs(user_id, created_at DESC);
```

**Design rationale:**
- `key_prefix` enables fast prefix-lookup before bcrypt comparison — keeps auth latency acceptable
- `revoked_at` (not `is_active` boolean) preserves revocation audit history
- `cost_usd` stored at write time — no recomputation on every dashboard query
- No `total_tokens` computed column — sum in query when needed; don't store derived data twice
- Index on `(user_id, created_at DESC)` covers the 30-day dashboard query exactly

### Authentication & Security

**Dual dependency injection — one dependency per auth path:**

```python
# CLI routes: bcrypt key validation
async def verify_api_key(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db)
) -> uuid.UUID:
    key = authorization.removeprefix("Bearer ").strip()
    prefix = key[:12]
    # 1. Lookup candidates by key_prefix (fast, indexed)
    # 2. bcrypt.checkpw(key, candidate.key_hash) for each
    # 3. Reject if revoked_at is not None
    # 4. Return user_id or raise HTTP 401

# Web routes: Supabase JWT validation
async def verify_supabase_jwt(
    authorization: str = Header(...),
) -> uuid.UUID:
    token = authorization.removeprefix("Bearer ").strip()
    # Verify with SUPABASE_JWT_SECRET → return sub as UUID
    # Raise HTTP 401 on any failure
```

**bcrypt cost factor: 12.** Standard for server-side key hashing. Not in the hot path
(key generation is infrequent; not called on every proxy request — only on CLI auth).

Wait — bcrypt IS called on every `/v1/chat/completions` request for key validation.
Cost factor 12 adds ~300ms per verify on commodity hardware. **Decision: use cost
factor 10** for the API key path to stay under the 200ms proxy overhead NFR.
Key generation (infrequent) can use cost 12.

**FastAPI uses `SUPABASE_SERVICE_ROLE_KEY` for all DB operations.** Railway environment
variable only — never in code, never in logs. Service role bypasses RLS; FastAPI is
trusted infrastructure. RLS is defense-in-depth, not the primary security layer.

### Supabase RLS Policies

```sql
ALTER TABLE public.api_keys   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.usage_logs ENABLE ROW LEVEL SECURITY;

-- api_keys: authenticated web users can manage their own keys
CREATE POLICY "Users can view own keys"
    ON public.api_keys FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can create own keys"
    ON public.api_keys FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can revoke own keys"
    ON public.api_keys FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- usage_logs: web users can read; INSERT is service-role-only (no policy = no access)
CREATE POLICY "Users can view own usage"
    ON public.usage_logs FOR SELECT
    USING (auth.uid() = user_id);
```

**No INSERT policy on `usage_logs`.** Only FastAPI (service role) writes usage records.
A leaked JWT cannot insert fabricated usage records — zero surface for usage inflation.

### API Contract

| Method | Path | Auth Dependency | Notes |
|---|---|---|---|
| `POST` | `/v1/chat/completions` | `verify_api_key` | Body forwarded unmodified to OpenRouter |
| `GET` | `/health` | none | Railway health check — returns `{"status": "ok"}` |
| `GET` | `/api/usage` | `verify_supabase_jwt` | Last 30 days aggregated by model + day |
| `GET` | `/api/keys` | `verify_supabase_jwt` | Lists active keys (revoked_at IS NULL) |
| `POST` | `/api/keys` | `verify_supabase_jwt` | Generates key; returns plaintext once |
| `DELETE` | `/api/keys/{key_id}` | `verify_supabase_jwt` | Sets revoked_at = NOW() |

**`GET /api/usage` response:**
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

**`POST /api/keys` response** (key shown once, never retrievable again):
```json
{
  "id": "uuid",
  "key": "ot_abc123...",
  "key_prefix": "ot_abc12345",
  "created_at": "2026-03-24T00:00:00Z"
}
```

**Uniform error shape:**
```json
{ "detail": "Unauthorized" }       // HTTP 401
{ "detail": "Proxy error: ..." }   // HTTP 502
```

### Frontend Architecture

**State:** No state management library. Two pieces of state only:
1. `user` — from `supabase.auth.onAuthStateChange()` — drives view switching
2. `activeView` — `"dashboard" | "api-keys"` — drives sidebar navigation

**View switching:** `user ? <AuthenticatedApp /> : <LoginPage />` — conditional render
at the root. No router. No URL changes.

**Data fetching:** Single `useEffect` on `<Dashboard />` mount calls `GET /api/usage`
with the Supabase session JWT. Result stored in local state. No caching layer, no
refetch on focus — manual browser refresh to see new data (by design, per PRD).

### Infrastructure & Deployment

| Concern | Decision | Notes |
|---|---|---|
| API hosting | Railway | Free tier; auto-restart on `/health` failure |
| Web hosting | Vercel | Static SPA deployment |
| Auth + DB | Supabase | Service role key for FastAPI; anon key for web auth only |
| LLM routing | OpenRouter | Master API key in Railway env vars only |
| Secrets | Railway/Vercel env vars | Never committed, never logged |
| CLI distribution | Homebrew tap | `brew install opentaion/tap/opentaion` |

### Decision Impact Analysis

**Implementation sequence (order matters):**
1. Supabase project setup + schema migrations (everything depends on this)
2. API `verify_api_key` + `verify_supabase_jwt` dependencies (block all other endpoints)
3. `/v1/chat/completions` proxy + `BackgroundTasks` usage write
4. `/api/keys` CRUD + `/api/usage` read endpoints
5. CLI `httpx.AsyncClient` against the live API
6. Web Supabase auth + dashboard data fetch

**Cross-component dependencies:**
- CLI → API: `proxy_url` + `api_key` in `~/.opentaion/config.json`
- Web → API: Supabase session JWT in `Authorization` header
- API → Supabase: service role key for all DB operations
- API → OpenRouter: master API key (env var); user key never leaves the API

## Implementation Patterns & Consistency Rules

### Naming Patterns

**Database — snake_case everywhere:**
- Tables: `api_keys`, `usage_logs` (plural, snake_case)
- Columns: `user_id`, `key_hash`, `created_at`, `cost_usd`
- Indexes: `idx_{table}_{column}` e.g. `idx_api_keys_prefix`
- FKs: `{table_singular}_id` e.g. `user_id`, never `fk_user`

**API JSON — snake_case throughout (not camelCase):**
FastAPI + Pydantic uses snake_case natively. The frontend must accept snake_case.
No automatic camelCase aliasing. Consistent with the DB layer; one mental model.
```json
// ✅ correct
{ "key_prefix": "ot_abc12345", "created_at": "2026-03-24T00:00:00Z" }
// ❌ wrong
{ "keyPrefix": "ot_abc12345", "createdAt": "2026-03-24T00:00:00Z" }
```

**API endpoints — plural nouns, kebab-case:**
`/api/keys`, `/api/usage` — not `/api/key`, not `/api/apiKeys`

**Python (CLI + API) — snake_case for all identifiers:**
`verify_api_key`, `usage_logs`, `get_db` — never camelCase in Python files.

**TypeScript/React — camelCase for variables/functions, PascalCase for components:**
`isLoading`, `usageData`, `fetchUsage()` — component files: `Dashboard.tsx`, `LoginPage.tsx`

### Format Patterns

**Datetimes — ISO 8601 UTC strings everywhere:**
```python
# API responses
"created_at": "2026-03-24T00:00:00Z"  # ✅
"created_at": 1742774400               # ❌ no Unix timestamps
```
Pydantic serializes `datetime` as ISO 8601 by default. Store as `TIMESTAMPTZ` in Postgres.
Frontend parses with `new Date(record.created_at)`.

**Cost — decimal string, never float:**
```python
# Pydantic model
cost_usd: Decimal  # serializes as "0.00120000"
# ✅ preserves 8 decimal places
# ❌ never: cost_usd: float  (rounding at 8dp)
```
Use Python's `decimal.Decimal` for all cost arithmetic. JSON serializes as a string.
Frontend displays with `parseFloat(record.cost_usd).toFixed(8)` — for display only,
never for arithmetic.

**UUIDs — lowercase string:**
```json
"id": "550e8400-e29b-41d4-a716-446655440000"  // ✅
"id": "550E8400-E29B-41D4-A716-446655440000"  // ❌ uppercase
```

**API key format:**
`ot_` prefix + 32 url-safe random chars = `"ot_" + secrets.token_urlsafe(24)`.
Prefix for lookup = first 12 characters of full key (including `ot_`).

### Process Patterns

**CLI: async entry point — one `asyncio.run()` at the top:**
```python
# cli/src/opentaion/__main__.py
import asyncio
import click

@click.command()
def cli():
    asyncio.run(main())  # ✅ single event loop entry point

# ❌ never: asyncio.run() inside a helper or called multiple times
```
All async work flows from this single `asyncio.run()`. No nested event loops.
The CLI's `httpx.AsyncClient` is created once per command invocation, used, and closed.

**CLI: all user-visible output through Rich Console — never bare `print()`:**
```python
# cli/src/opentaion/console.py — single module-level Console instance
from rich.console import Console
console = Console()
err_console = Console(stderr=True)

# All output: console.print(), console.log(), console.rule()
# ❌ never: print("something")  — bypasses Rich formatting and stderr routing
```
Errors use `err_console.print(..., style="red")`. Exit via `sys.exit(1)`.

**FastAPI: errors via `HTTPException` — never return error dicts:**
```python
# ✅ correct
raise HTTPException(status_code=401, detail="Unauthorized")

# ❌ wrong — bypasses FastAPI's error middleware
return {"error": "Unauthorized"}
```

**FastAPI: auth always via dependency injection — never checked inside route body:**
```python
# ✅ correct
@router.get("/api/usage")
async def get_usage(
    user_id: uuid.UUID = Depends(verify_supabase_jwt),
    db: AsyncSession = Depends(get_db)
):
    ...

# ❌ wrong — auth logic inside the route body
@router.get("/api/usage")
async def get_usage(authorization: str = Header(...)):
    if not check_jwt(authorization):
        ...
```

**FastAPI: usage logging ALWAYS via `BackgroundTasks` — never awaited:**
```python
# ✅ correct — response returns immediately; log write happens after
@router.post("/v1/chat/completions")
async def proxy(
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: uuid.UUID = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    response = await forward_to_openrouter(request)
    background_tasks.add_task(write_usage_log, db, user_id, response)
    return response

# ❌ wrong — blocks the response, violates NFR9
    await write_usage_log(db, user_id, response)
    return response
```

**FastAPI: proxy body — forward as raw bytes, never parse or validate:**
```python
# ✅ correct
body = await request.body()  # raw bytes forwarded directly

# ❌ wrong — rejects unknown OpenRouter fields, violates NFR12
data = await request.json()
validated = OpenRouterRequest(**data)
```

### Structure Patterns

**Python project layout (CLI and API share the convention):**
```
cli/
  src/opentaion/
    __main__.py       ← asyncio.run() entry point
    commands/         ← one file per Click command
    core/             ← business logic (agent loop, cost calc)
    console.py        ← single Rich Console + err_console instances
  tests/              ← mirrors src/ structure

api/
  app/
    main.py           ← FastAPI app + router registration
    routers/          ← one file per domain: proxy.py, keys.py, usage.py
    dependencies/     ← auth.py (verify_api_key, verify_supabase_jwt), db.py
    models/           ← SQLAlchemy ORM models
    schemas/          ← Pydantic request/response models
    services/         ← business logic: cost.py (model_pricing dict)
  tests/              ← mirrors app/ structure
  alembic/
    versions/         ← migration files
```

**Tests: always in a separate `tests/` directory, never co-located.**

**Pydantic schemas vs SQLAlchemy models — never mix:**
Routes receive Pydantic schemas → service functions → SQLAlchemy models.
No ORM model ever appears in a route response. No Pydantic schema ever reaches the DB.

### Enforcement Guidelines

**All agents implementing any component MUST:**

1. Use `snake_case` for all JSON field names — never camelCase in API payloads
2. Represent `cost_usd` as `decimal.Decimal` in Python; serialize as string in JSON — never float
3. Route all CLI user-visible output through the shared `Console` instance — never `print()`
4. Raise `HTTPException` for all API errors — never return error dicts
5. Place auth as a `Depends(...)` argument on the route — never inline auth logic
6. Add usage logging as `background_tasks.add_task(...)` — never `await` the write
7. Forward the proxy request body as raw bytes — never parse or reconstruct it
8. Use `asyncio.run()` exactly once in the CLI, in `__main__.py`
9. Serialize datetimes as ISO 8601 UTC strings; store as `TIMESTAMPTZ`
10. Generate API keys with `"ot_" + secrets.token_urlsafe(24)` — never `random`

**Anti-patterns agents must never introduce:**
- `import random` for key generation → use `secrets` only
- `float` for cost arithmetic → use `decimal.Decimal`
- `print()` in CLI → use `console.print()`
- `return {"error": ...}` in FastAPI → use `raise HTTPException`
- Parsing proxy request body → forward raw bytes
- `await write_usage_log(...)` in proxy route → must be `background_tasks.add_task`

## Project Structure & Boundaries

### Complete Project Directory Structure

```
opentaion/
├── CLAUDE.md                          # Project constitution
├── cli/
│   ├── CLAUDE.md                      ✅ Component rules
│   ├── SPEC.md                        ✅ Feature specification
│   ├── pyproject.toml                 ✅ uv/hatchling config
│   ├── uv.lock                        ✅
│   ├── src/
│   │   └── opentaion/
│   │       ├── __init__.py            ✅ (empty)
│   │       ├── __main__.py            🔲 asyncio.run() entry point; Click group
│   │       ├── agent.py               ✅ AgentLoop — refactor to use proxy_url
│   │       ├── llm.py                 ✅ OpenRouterClient — refactor to proxy client
│   │       ├── context.py             ✅ Context/config helpers
│   │       ├── config.py              🔲 Config dataclass; read/write ~/.opentaion/config.json
│   │       └── commands/
│   │           ├── __init__.py        🔲
│   │           ├── login.py           🔲 opentaion login — magic link + config write
│   │           └── effort.py          🔲 opentaion /effort [low|medium|high] "<prompt>"
│   └── tests/
│       ├── test_agent.py              ✅
│       ├── test_context.py            ✅
│       ├── test_llm.py                ✅
│       ├── test_config.py             🔲
│       └── test_commands/
│           ├── test_login.py          🔲
│           └── test_effort.py         🔲
│
├── api/
│   ├── CLAUDE.md                      ✅ Component rules (update endpoint paths to /api/keys, /api/usage)
│   ├── pyproject.toml                 🔲 uv config; package name: opentaion_api
│   ├── uv.lock                        🔲
│   ├── .env.example                   🔲 SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
│   │                                     OPENROUTER_API_KEY, JWT_SECRET
│   ├── app/
│   │   ├── __init__.py                🔲
│   │   ├── main.py                    🔲 FastAPI app, router registration, CORS
│   │   ├── routers/
│   │   │   ├── __init__.py            🔲
│   │   │   ├── proxy.py               🔲 POST /v1/chat/completions + GET /health
│   │   │   ├── keys.py                🔲 GET|POST|DELETE /api/keys
│   │   │   └── usage.py               🔲 GET /api/usage
│   │   ├── dependencies/
│   │   │   ├── __init__.py            🔲
│   │   │   ├── auth.py                🔲 verify_api_key(), verify_supabase_jwt()
│   │   │   └── db.py                  🔲 get_db() AsyncSession
│   │   ├── models/
│   │   │   ├── __init__.py            🔲
│   │   │   ├── api_key.py             🔲 ApiKey SQLAlchemy model
│   │   │   └── usage_log.py           🔲 UsageLog SQLAlchemy model
│   │   ├── schemas/
│   │   │   ├── __init__.py            🔲
│   │   │   ├── keys.py                🔲 KeyCreate, KeyResponse, KeyListResponse
│   │   │   └── usage.py               🔲 UsageRecord, UsageResponse
│   │   └── services/
│   │       ├── __init__.py            🔲
│   │       └── cost.py                🔲 MODEL_PRICING dict, compute_cost(model, tokens)
│   ├── alembic/
│   │   ├── env.py                     🔲
│   │   ├── script.py.mako             🔲
│   │   └── versions/
│   │       └── 0001_initial_schema.py 🔲 api_keys + usage_logs tables + indexes
│   └── tests/
│       ├── conftest.py                🔲 async test client, test DB fixtures
│       ├── test_proxy.py              🔲
│       ├── test_keys.py               🔲
│       ├── test_usage.py              🔲
│       └── test_auth.py               🔲
│
└── web/
    ├── CLAUDE.md                      🔲 Component rules
    ├── package.json                   ✅
    ├── vite.config.ts                 ✅
    ├── tailwind.config.ts             ✅
    ├── tsconfig.json                  ✅
    ├── index.html                     ✅
    ├── .env.example                   🔲 VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY,
    │                                     VITE_API_BASE_URL
    └── src/
        ├── main.tsx                   ✅ Vite entry point
        ├── index.css                  ✅ Tailwind directives
        ├── App.tsx                    ✅ Root: Supabase auth state → view switch
        ├── Login.tsx                  ✅ Magic link form
        ├── Dashboard.tsx              ✅ 30-day chart + per-model table
        ├── ApiKeys.tsx                🔲 Key generation, list, revocation UI
        ├── types/
        │   └── api.ts                 🔲 UsageRecord, ApiKey TS types (snake_case)
        └── hooks/
            ├── useUsage.ts            🔲 Fetch GET /api/usage on mount
            └── useApiKeys.ts          🔲 Fetch/create/revoke keys
```

### Architectural Boundaries

**CLI → API boundary:**
All LLM calls from the CLI go through `POST {proxy_url}/v1/chat/completions` with
`Authorization: Bearer ot_...`. The CLI never calls OpenRouter directly in production.
Config in `~/.opentaion/config.json` provides `proxy_url` and `api_key`.
`agent.py` and `llm.py` must be refactored during implementation to use this path.

**Web → API boundary:**
All data reads (`GET /api/usage`, `GET /api/keys`) go through the FastAPI API with
the Supabase session JWT in the `Authorization` header.
Supabase JS SDK is used only for auth (magic link, session management).
The web never reads Supabase tables directly.

**API → Supabase boundary:**
FastAPI uses the service role key for all DB operations (bypasses RLS).
The service role key lives exclusively in Railway environment variables.

**API → OpenRouter boundary:**
The proxy swaps the user's `ot_...` key for the master OpenRouter key (Railway env var)
and forwards the request body unmodified. The master key never leaves the server.

### Requirements to Structure Mapping

| FR Category | Primary Files |
|---|---|
| Auth & Identity (FR1–FR5) | `cli/commands/login.py`, `api/dependencies/auth.py`, `api/routers/keys.py`, `web/src/Login.tsx`, `web/src/ApiKeys.tsx` |
| Task Execution & Effort Routing (FR6–FR11) | `cli/commands/effort.py`, `cli/agent.py`, `cli/config.py` |
| LLM Proxying (FR12–FR15) | `api/routers/proxy.py`, `api/services/cost.py` |
| Usage Metering & Storage (FR16–FR19) | `api/models/usage_log.py`, `api/services/cost.py`, `alembic/versions/0001_*` |
| Usage Visibility (FR20–FR23) | `api/routers/usage.py`, `api/schemas/usage.py`, `web/src/Dashboard.tsx`, `web/src/hooks/useUsage.ts` |
| Distribution & Ops (FR24–FR26) | `cli/pyproject.toml` (Homebrew tap), `api/routers/proxy.py` (`/health`) |

### Data Flow

```
Developer terminal
  └─► cli/__main__.py (asyncio.run)
        └─► commands/effort.py (parse /effort tier + prompt)
              └─► agent.py AgentLoop (reads proxy_url + api_key from config.py)
                    └─► POST {proxy_url}/v1/chat/completions
                          └─► api/routers/proxy.py
                                ├─► dependencies/auth.py → verify_api_key → user_id
                                ├─► forward to OpenRouter (master key)
                                ├─► return response to CLI ◄────────────────────
                                └─► BackgroundTasks: services/cost.py → usage_log write

Web browser
  └─► web/src/App.tsx (Supabase auth state)
        ├─► Login.tsx → supabase.auth.signInWithOtp
        └─► Dashboard.tsx + ApiKeys.tsx
              ├─► hooks/useUsage.ts → GET /api/usage (JWT)
              └─► hooks/useApiKeys.ts → GET|POST|DELETE /api/keys (JWT)
                    └─► api/routers/usage.py | keys.py
                          └─► dependencies/auth.py → verify_supabase_jwt → user_id
```

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:** All three components are compatible. Python 3.12 on CLI +
API. React 18 + TypeScript on web. FastAPI's `BackgroundTasks` requires no additional
infrastructure (no Celery, no Redis). Supabase service role key bypasses RLS cleanly.

**Correction applied — bcrypt cost factor 10 uniformly:**
bcrypt embeds the cost factor in the hash at generation time; verification always takes
as long as the factor chosen at generation. Cost factor 12 (~300ms per verify) would
violate NFR1. **All API key generation uses cost factor 10.** Verification time ~100ms,
well within the 200ms proxy overhead budget.

**Pattern Consistency:** snake_case flows from DB columns → Pydantic schemas → JSON →
TypeScript types. Dual auth dependencies cleanly partition CLI and web paths.
`BackgroundTasks` for usage logging is consistent with async SQLAlchemy session pattern.

### Requirements Coverage ✅

All 26 FRs traced to specific files. All 13 NFRs architecturally addressed.

| FR | Covered by |
|---|---|
| FR1 (CLI magic link) | `commands/login.py` + Supabase |
| FR2–FR4 (API key CRUD) | `api/routers/keys.py` + `web/src/ApiKeys.tsx` |
| FR5 (web magic link) | `web/src/Login.tsx` + Supabase JS SDK |
| FR6–FR8 (effort routing + cost display) | `commands/effort.py` + `agent.py` + `console.py` |
| FR9–FR11 (retry, exit, config) | `commands/effort.py` + `config.py` |
| FR12–FR15 (proxy auth, key swap, async log) | `dependencies/auth.py` + `routers/proxy.py` |
| FR16–FR19 (metering, cost, user attribution) | `models/usage_log.py` + `services/cost.py` |
| FR20–FR23 (chart, table, key management) | `Dashboard.tsx` + `ApiKeys.tsx` + `hooks/` |
| FR24–FR26 (Homebrew, health, auth confirm) | `pyproject.toml` + `routers/proxy.py` + `commands/login.py` |

### Gaps Resolved

**Effort tier → model mapping (confirmed):**

```python
# api/app/services/cost.py
EFFORT_MODELS = {
    "low":    "meta-llama/llama-3.3-70b-instruct:free",
    "medium": "qwen/qwen-2.5-72b-instruct:free",
    "high":   "deepseek/deepseek-r1:free",
}
```

**Model pricing table approach (confirmed):**
Store `cost_per_million_prompt_tokens` and `cost_per_million_completion_tokens` per
model ID. All `:free` models default to `0.0`. Pricing is a Python dict — updating
prices requires only a redeploy, never a migration.

```python
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # model_id: (cost_per_M_prompt_tokens, cost_per_M_completion_tokens)
    "meta-llama/llama-3.3-70b-instruct:free": (0.0, 0.0),
    "qwen/qwen-2.5-72b-instruct:free":        (0.0, 0.0),
    "deepseek/deepseek-r1:free":               (0.0, 0.0),
}
```

**httpx timeout (confirmed):**
```python
# cli/src/opentaion/config.py or commands/effort.py
PROXY_TIMEOUT = httpx.Timeout(connect=5.0, read=120.0)
# 5s connect: detects Railway cold start / unreachable proxy quickly
# 120s read: allows reasoning models (DeepSeek R1) full think time
```

**Chart type (confirmed — single-color wins):**
`Dashboard.tsx` renders a single-color Recharts `<BarChart>` with total tokens per day.
No stacked bars in V1. Per-model breakdown is in the data table below the chart only.
This is a deliberate UX decision: "show spikes, not model mix."

### Architecture Completeness Checklist

**✅ Requirements Analysis**
- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed
- [x] Technical constraints identified
- [x] Cross-cutting concerns mapped

**✅ Architectural Decisions**
- [x] Critical decisions documented with rationale
- [x] Technology stack fully specified
- [x] Dual auth pattern defined
- [x] Database schema with indexes specified
- [x] RLS policies defined
- [x] API contract with payload shapes specified
- [x] bcrypt cost factor corrected to 10

**✅ Implementation Patterns**
- [x] Naming conventions established (snake_case throughout API/DB)
- [x] Async patterns specified (BackgroundTasks, asyncio.run, httpx.AsyncClient)
- [x] Anti-patterns documented (10 mandatory rules + anti-pattern list)
- [x] Error handling pattern specified (HTTPException only)

**✅ Project Structure**
- [x] Complete directory structure with ✅/🔲 markers
- [x] Requirements to structure mapping complete
- [x] Data flow diagram documented
- [x] Existing code discrepancies flagged (llm.py/agent.py proxy refactor)

**✅ All Gaps Closed**
- [x] Effort tier → model mapping confirmed
- [x] Model pricing table structure confirmed
- [x] httpx timeout values confirmed
- [x] Chart type confirmed (single-color)

### Architecture Readiness Assessment

**Overall Status: READY FOR IMPLEMENTATION**

**Confidence Level: High** — All decisions are specific, traceable to requirements,
and leave no room for agent interpretation drift.

**Key Strengths:**
- Zero-infrastructure async pattern (BackgroundTasks, no Celery)
- Dual auth cleanly partitioned by dependency injection
- Snake_case uniformity eliminates the most common CLI/web/API naming conflict
- All three free-tier OpenRouter models confirmed; readers need no credit card
- Single-color chart keeps V1 UX focused on the core value (cost spikes)

**Deferred to Phase 2:**
- Stacked bar chart (per-model breakdown in chart)
- Dead-letter table for failed async usage writes
- Session-level cost attribution
- Per-project cost keys

### Implementation Handoff

**AI agents implementing this system must:**
1. Follow the 10 mandatory rules in the Implementation Patterns section
2. Use `EFFORT_MODELS` and `MODEL_PRICING` from `services/cost.py` as the single
   source of truth for model routing and cost computation
3. Refactor `agent.py` and `llm.py` to route through `proxy_url` (not direct OpenRouter)
4. Use bcrypt cost factor 10 for all API key generation
5. Update `api/CLAUDE.md` endpoint paths to `/api/keys` and `/api/usage`

**First implementation priority:**
Supabase project setup + Alembic migration `0001_initial_schema.py` — everything
else depends on the DB tables existing.
