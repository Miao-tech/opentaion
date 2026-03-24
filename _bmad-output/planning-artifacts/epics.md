---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories', 'step-04-final-validation']
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
---

# opentaion - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for opentaion, decomposing the requirements from the PRD, UX Design, and Architecture into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: Developer can authenticate the CLI by receiving a magic link at their email address and confirming it in a browser
FR2: Developer can generate a new OpenTalon API key from the web dashboard (displayed once at creation)
FR3: Developer can view a list of their active API keys with a truncated preview of each key
FR4: Developer can revoke an API key by ID from the web dashboard
FR5: Developer can authenticate the web dashboard by receiving a magic link at their email address
FR6: Developer can invoke an agentic coding task from the terminal using a natural language prompt
FR7: Developer can specify a model cost tier (low, medium, or high) per task to control which model OpenRouter uses
FR8: Developer can view the total token count and computed cost for each completed task, printed in the terminal immediately after the task finishes
FR9: The CLI automatically retries a failed proxy connection once before reporting failure
FR10: The CLI exits with a non-zero status code and an actionable error message when the proxy is unreachable after the retry
FR11: The CLI stores its proxy URL and API key in a persistent global config file, available across all project directories on the machine
FR12: The proxy validates the developer's OpenTalon API key on every incoming request before forwarding it
FR13: The proxy forwards LLM requests to OpenRouter using the server's master OpenRouter API key, not the developer's key
FR14: The proxy returns the OpenRouter response to the CLI without modification
FR15: The proxy records usage data for each request asynchronously, without blocking the LLM response being returned to the CLI
FR16: The system records prompt token count, completion token count, and model ID for each proxied LLM call
FR17: The system records a timestamp for each proxied LLM call
FR18: The system computes cost server-side from stored token counts using a model pricing table; cost is never accepted from the client
FR19: The system associates each usage record with the authenticated developer who made the request
FR20: Developer can view a bar chart of their token usage for the last 30 days, grouped by day and broken down by model
FR21: Developer can view a per-model cost summary table for their last 30 days of usage
FR22: The dashboard fetches and renders usage data automatically when the authenticated view loads
FR23: Developer can access API key management (generate, list, revoke) from the authenticated dashboard
FR24: Developer can install the CLI on macOS using a single Homebrew command
FR25: The API exposes a health check endpoint that returns a successful response when the service is operational
FR26: The CLI displays a confirmation message in the terminal upon successful first-time authentication

### NonFunctional Requirements

NFR1: The API proxy must add less than 200ms of overhead to any LLM API call, measured from request receipt to response forwarding. Hard requirement — not a target.
NFR2: GET /api/usage must return a response within 2 seconds for a standard 30-day dataset.
NFR3: The web dashboard must display usage data within 3 seconds of page load on a standard broadband connection.
NFR4: OpenTalon API keys must be stored bcrypt-hashed in the database; plaintext keys must never be persisted.
NFR5: A generated API key must be displayed exactly once at creation; it must not be retrievable after the creation response.
NFR6: All client-server communication must use HTTPS; the API must not accept or serve unencrypted HTTP requests.
NFR7: The master OpenRouter API key must be stored exclusively as a server-side environment variable; it must never appear in any response, log output, or client-accessible resource.
NFR8: User email address is the only PII stored in the system; no passwords are stored anywhere.
NFR9: Usage logging failures must not delay or prevent the LLM response being returned to the CLI. The logging write is asynchronous and its failure must be silent to the end user.
NFR10: The CLI must surface a deterministic error message and exit within 5 seconds of a proxy connection failure, after one retry attempt.
NFR11: The API must expose a /health endpoint that Railway can poll; the service must restart automatically on unhealthy status.
NFR12: The proxy endpoint must accept any syntactically valid OpenRouter-compatible request body without modification; the API must not reject requests based on unrecognized fields.
NFR13: Cost calculation must derive exclusively from token counts in the OpenRouter response metadata; cost must not depend on any external pricing API call in the request path.

### Additional Requirements

- **Database schema (blocks everything):** Two tables required before any endpoint can be implemented: `api_keys` (id, user_id, key_hash, key_prefix, created_at, revoked_at) and `usage_logs` (id, user_id, model, prompt_tokens, completion_tokens, cost_usd, created_at). Indexes: `idx_api_keys_prefix` on `key_prefix`, `idx_api_keys_user` on `user_id`, `idx_usage_logs_user_date` on `(user_id, created_at DESC)`.
- **No `public.users` mirror table:** All FK references point to `auth.users(id)` directly via `auth.uid()`. Supabase Auth manages identity.
- **Supabase RLS policies:** Row-level security on both tables. API keys: users can SELECT/INSERT/UPDATE their own rows. Usage logs: users can SELECT only; INSERT is service-role-only (no INSERT policy = no direct access).
- **Dual authentication pattern:** `verify_api_key()` (bcrypt, cost factor 10) for CLI routes; `verify_supabase_jwt()` (JWT secret validation) for web routes. Auth always via FastAPI dependency injection, never inline in route body.
- **bcrypt cost factor:** Use cost factor 10 (not 12) for key validation in the proxy hot path. Key generation uses cost 12 (infrequent).
- **`model_pricing` as Python dict:** Pricing table is a hardcoded Python dict keyed by OpenRouter model ID. Updating pricing requires a redeploy, not a DB migration.
- **`cost_usd` stored at write time:** Computed from the `model_pricing` dict at the moment of the usage log write. Not recomputed on query.
- **`revoked_at` timestamp pattern:** API key revocation sets `revoked_at = NOW()`, not a boolean `is_active`. Preserves audit history.
- **API key format:** `ot_` prefix + 32 url-safe random chars = `"ot_" + secrets.token_urlsafe(24)`. Key prefix for bcrypt lookup = first 12 characters.
- **FastAPI BackgroundTasks for usage logging:** Usage write is always passed as a background task in the `/v1/chat/completions` handler. Never awaited. Failure is logged to stdout, never propagated to the response.
- **Proxy body forwarding as raw bytes:** The proxy reads `await request.body()` and forwards raw bytes to OpenRouter. Never parses or validates the request body (supports NFR12).
- **FastAPI uses `SUPABASE_SERVICE_ROLE_KEY`** for all DB operations (Railway env var only). Service role bypasses RLS; FastAPI is trusted infrastructure.
- **CLI entry point:** Single `asyncio.run()` in `__main__.py`. All async work flows from this entry point. `httpx.AsyncClient` created once per command invocation.
- **All CLI output via Rich Console:** Never bare `print()`. Errors use `err_console` (stderr). Exit via `sys.exit(1)`.
- **Starter templates:** CLI via `uv init cli` + `uv add click rich httpx python-dotenv`; API via manual FastAPI structure + `uv add "fastapi[standard]>=0.110" ...`; Web via `npm create vite@latest web -- --template react-ts` + Tailwind + Recharts.
- **Implementation sequence (order matters):** (1) Supabase schema migrations → (2) API auth dependencies → (3) `/v1/chat/completions` proxy + BackgroundTasks → (4) `/api/keys` CRUD + `/api/usage` → (5) CLI httpx client → (6) Web Supabase auth + dashboard.
- **Infrastructure:** Railway (API, auto-restart via /health), Vercel (Web SPA), Supabase (PostgreSQL + Auth), OpenRouter (master API key in Railway env vars only), Homebrew tap (CLI distribution).
- **API JSON format:** snake_case throughout (not camelCase). Datetimes as ISO 8601 UTC strings. Cost as `Decimal` serialized as string (8 decimal places). UUIDs as lowercase strings.

### UX Design Requirements

UX-DR1: Implement `<Sidebar>` component — fixed 220px width (`w-[220px]`), two navigation items ("Dashboard" / "API Keys"), active state via `bg-blue-50 text-blue-600 rounded-md`, `<aside>` landmark with `<nav aria-label="Main navigation">`, active item has `aria-current="page"`, all items are `<button>` elements.
UX-DR2: Implement `<LoginForm>` component — two states: form (email input + "Send magic link" primary button) and post-send (confirmation text with 10-minute expiry notice). Error state displays `text-red-600 text-sm` with `role="alert"`. State toggles on successful Supabase `signInWithOtp` call.
UX-DR3: Implement `<UsageChart>` component using Recharts `<BarChart>` with `<ResponsiveContainer height={192}>`, hidden Y-axis, tooltip showing exact values, empty state ("No usage yet. Run your first task."), and accessibility attributes: `role="img" aria-label="30-day token usage bar chart"`.
UX-DR4: Implement `<ModelTable>` component — per-model breakdown with columns (Model, Tokens, Cost). Tokens formatted via `toLocaleString()`. Cost formatted as `$${cost.toFixed(4)}`. Total row in `<tfoot>` with `bg-gray-50 font-medium`. Proper `<th scope="col">` for column headers, `<th scope="row">` for total row label.
UX-DR5: Implement `<ApiKeyList>` component — key preview in `font-mono text-xs text-gray-600`, revoke button as `text-sm text-red-600 hover:text-red-700` with no confirmation modal. Three states: populated / empty ("No API keys yet. Generate one to connect your CLI.") / revoking in-flight (button shows "Revoking..." + disabled). Proper `<th scope="col">` for table headers.
UX-DR6: Implement `<NewKeyBanner>` component — shown once after key generation. Displays full plaintext key with "Copy this key now — it won't be shown again." instruction. Copy button with `aria-label="Copy API key to clipboard"`. 2-second "Copied ✓" feedback on copy. `role="alert"` so screen readers announce appearance. `shadow-sm` visual prominence.
UX-DR7: Implement `<GenerateKeyButton>` component — loading state changes button text to "Generating..." with `opacity-75 cursor-not-allowed`. Disabled during in-flight request. Triggers key generation and passes result via `onKeyGenerated` callback.
UX-DR8: Implement all CLI Rich output renderers: CostSummaryLine (`[bold]✓ Task complete.[/bold]` + `[dim]Tokens: {n:,}[/dim]` + `[bold cyan]Cost: ${cost:.4f}[/bold cyan]`), ProgressBullet (`[dim]  ◆ {message}[/dim]`), ErrorLine (`[bold red]✗ {title}[/bold red]` + dimmed detail + cyan recovery command), SetupPrompt (Click prompts with `hide_input=True` for API key), SuccessLine (bold config file path reference).
UX-DR9: Apply design token system throughout the web surface — only the defined 6-color palette: `bg-gray-50` (page), `bg-white` (surfaces), `border-gray-200` (borders), `text-gray-900` (primary text), `text-gray-500` (secondary text), `bg-blue-600`/`text-blue-600` (accent), `bg-blue-50` (accent subtle), `text-red-600` (destructive only). Typography scale: page heading `text-xl font-semibold text-gray-900`, section label `text-xs font-medium text-gray-500 uppercase tracking-widest`, body `text-sm text-gray-900`, metadata `text-sm text-gray-500`, monospace `font-mono text-xs text-gray-600`.
UX-DR10: All interactive elements must use consistent focus styles: `focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2`. No custom overrides. Button hover transitions: `transition-colors duration-150`.
UX-DR11: Semantic HTML structure throughout — `<table>` with `<thead>/<tbody>/<tfoot>`, `<th scope="col">` for column headers, `<label>` associated to inputs via `htmlFor`. Bar chart uses accessible attributes. No placeholder-only labeling on form inputs.
UX-DR12: Three-tier button hierarchy (one per view maximum for primary): Primary (`bg-blue-600 hover:bg-blue-700 text-white`), Secondary (`bg-white hover:bg-gray-100 text-gray-700 border border-gray-200`), Destructive text (`text-red-600 hover:text-red-700` with no background). No icon-only buttons. Disabled state: `opacity-50 cursor-not-allowed`.

### FR Coverage Map

FR1: Epic 2 — CLI `opentaion login` — magic link + CLI confirmation
FR2: Epic 2 — API key generation from web dashboard
FR3: Epic 2 — API key list with truncated preview
FR4: Epic 2 — API key revocation by ID
FR5: Epic 2 — Web dashboard magic link auth
FR6: Epic 3 — CLI invokes agentic task with natural language prompt
FR7: Epic 3 — `/effort [low|medium|high]` model tier routing
FR8: Epic 3 — Token count + cost printed in terminal after task
FR9: Epic 3 — Single retry on proxy connection failure
FR10: Epic 3 — Exit code 1 + actionable error after retry failure
FR11: Epic 2 — Config stored in `~/.opentaion/config.json`
FR12: Epic 3 — Proxy validates OpenTalon API key on every request
FR13: Epic 3 — Proxy swaps user key for master OpenRouter key
FR14: Epic 3 — Proxy returns OpenRouter response unmodified
FR15: Epic 3 — Usage logging is async, does not block response
FR16: Epic 3 — Prompt tokens, completion tokens, model ID recorded
FR17: Epic 3 — Timestamp recorded per proxied call
FR18: Epic 3 — Cost computed server-side from pricing dict
FR19: Epic 3 — Usage record associated to authenticated user
FR20: Epic 4 — 30-day bar chart grouped by day + model
FR21: Epic 4 — Per-model cost summary table
FR22: Epic 4 — Dashboard fetches usage data on authenticated load
FR23: Epic 2 — API key management accessible from authenticated dashboard
FR24: Epic 1 — CLI installable via single Homebrew command
FR25: Epic 1 — `/health` endpoint returns 200 OK
FR26: Epic 2 — CLI prints confirmation on successful login

## Epic List

### Epic 1: Project Foundation & Deployable Infrastructure
All three components (CLI, API, Web) exist as initialized projects, are deployed to their respective platforms, and the system health is verifiable. This is the scaffolding that makes every subsequent epic possible.
**FRs covered:** FR24, FR25
**NFRs addressed:** NFR6 (HTTPS via Railway/Vercel), NFR11 (health check + auto-restart)

### Epic 2: Developer Authentication & API Key Management
A developer can register and sign in to the web dashboard via magic link, generate and manage their API keys in the web UI, and authenticate the CLI against their deployed API — completing the full onboarding ceremony.
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR11, FR23, FR26
**NFRs addressed:** NFR4 (bcrypt), NFR5 (display once), NFR8 (email-only PII)

### Epic 3: Metered Task Execution
A developer can invoke an agentic coding task from the terminal with an explicit effort tier, have it routed to the correct model via the proxy, and see the total token count and cost in the terminal the moment the task completes.
**FRs covered:** FR6, FR7, FR8, FR9, FR10, FR12, FR13, FR14, FR15, FR16, FR17, FR18, FR19
**NFRs addressed:** NFR1 (< 200ms overhead), NFR7 (master key never leaves server), NFR9 (async log, no blocking), NFR10 (exit within 5s), NFR12 (body pass-through), NFR13 (server-side cost)

### Epic 4: Usage Visibility Dashboard
A developer can open their web dashboard and immediately see a 30-day bar chart of token usage and a per-model cost breakdown table — allowing them to identify spending patterns and cost spikes at a glance.
**FRs covered:** FR20, FR21, FR22
**NFRs addressed:** NFR2 (usage endpoint < 2s), NFR3 (dashboard < 3s load)

---

## Epic 1: Project Foundation & Deployable Infrastructure

All three components (CLI, API, Web) exist as initialized projects, are deployed to their respective platforms, and the system health is verifiable. This is the scaffolding that makes every subsequent epic possible.

### Story 1.1: Initialize CLI Python Package

As a developer building OpenTalon,
I want the CLI project scaffolded with its package structure, dependencies, and a working `--version` command,
So that the foundation for all subsequent CLI commands exists and can be verified locally.

**Acceptance Criteria:**

**Given** a macOS machine with `uv` installed
**When** `uv run python -m opentaion --version` is executed from `cli/`
**Then** the CLI prints the version string (e.g. `opentaion 0.1.0`) and exits with code 0

**Given** the project is initialized
**When** the `cli/` directory is examined
**Then** it contains: `src/opentaion/__main__.py` (single `asyncio.run()` entry point), `src/opentaion/console.py` (module-level `Console` + `err_console` instances, no bare `print()`), `src/opentaion/commands/` directory, `src/opentaion/core/` directory, `tests/` directory mirroring `src/` structure, `uv.lock`, and `pyproject.toml` with dependencies: `click>=8.0`, `rich>=13.0`, `httpx`, `python-dotenv`, and dev dependencies: `pytest`, `pytest-asyncio`

**Given** a test is run
**When** `uv run pytest` is executed from `cli/`
**Then** the test suite passes (at minimum a smoke test asserting the CLI can be imported)

### Story 1.2: Initialize API FastAPI Service with Health Check

As a developer building OpenTalon,
I want the API project scaffolded with FastAPI, Alembic, async SQLAlchemy, and a working `/health` endpoint,
So that Railway can monitor service health and the API is deployable from day one.

**Acceptance Criteria:**

**Given** the API project is initialized
**When** `api/` is examined
**Then** it contains: `src/opentaion_api/main.py` (FastAPI app instance), `src/opentaion_api/routers/` directory, `src/opentaion_api/deps.py` (placeholder for auth dependencies), `src/opentaion_api/database.py` (async engine + `get_db` dependency), `alembic/` directory with `env.py` configured for async SQLAlchemy, `uv.lock`, and `pyproject.toml` with dependencies: `fastapi[standard]>=0.110`, `sqlalchemy[asyncio]>=2.0`, `alembic`, `asyncpg`, `bcrypt`, `httpx`, `python-dotenv`, `supabase`, and dev dependencies: `pytest`, `pytest-asyncio`, `httpx`

**Given** the API server is running locally via `fastapi dev`
**When** `GET /health` is called
**Then** the response is `{"status": "ok"}` with HTTP 200

**Given** a test is run
**When** `uv run pytest` is executed from `api/`
**Then** the test for `GET /health` passes using FastAPI's `TestClient`

### Story 1.3: Initialize Web SPA with Tailwind and Recharts

As a developer building OpenTalon,
I want the web project scaffolded with Vite + React-TS, Tailwind configured, Recharts installed, and a shell App component,
So that the web surface is deployable and ready for authenticated/unauthenticated view implementation.

**Acceptance Criteria:**

**Given** the web project is initialized
**When** `web/` is examined
**Then** it contains: a Vite + React-TS project structure, `tailwind.config.js` configured with `content: ["./src/**/*.{ts,tsx}"]`, `postcss.config.js`, `recharts` and `@supabase/supabase-js` in `package.json`, and `src/App.tsx` with a conditional render stub: `user ? <div>Dashboard</div> : <div>Login</div>`

**Given** `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` are set in `.env.local`
**When** `npm run dev` is executed from `web/`
**Then** the dev server starts without errors and the shell renders in a browser

**Given** `npm run build` is executed
**When** the build completes
**Then** it exits with code 0 and produces a `dist/` directory

### Story 1.4: Supabase Schema Migrations (Database Foundation)

As a developer building OpenTalon,
I want the `api_keys` and `usage_logs` tables created in Supabase via Alembic migrations with all required indexes and RLS policies,
So that all subsequent API endpoints have a correct, secured data layer to work against.

**Acceptance Criteria:**

**Given** a Supabase project is configured and `DATABASE_URL` is set
**When** `alembic upgrade head` is run from `api/`
**Then** the migration applies without error and the following exist in the database:
- Table `public.api_keys`: `id` (UUID PK), `user_id` (UUID FK → `auth.users(id)` ON DELETE CASCADE), `key_hash` (TEXT NOT NULL), `key_prefix` (TEXT NOT NULL), `created_at` (TIMESTAMPTZ NOT NULL DEFAULT NOW()), `revoked_at` (TIMESTAMPTZ NULL)
- Table `public.usage_logs`: `id` (UUID PK), `user_id` (UUID FK → `auth.users(id)` ON DELETE CASCADE), `model` (TEXT NOT NULL), `prompt_tokens` (INTEGER NOT NULL), `completion_tokens` (INTEGER NOT NULL), `cost_usd` (NUMERIC(10,8) NOT NULL), `created_at` (TIMESTAMPTZ NOT NULL DEFAULT NOW())
- Index `idx_api_keys_prefix` on `api_keys(key_prefix)`
- Index `idx_api_keys_user` on `api_keys(user_id)`
- Index `idx_usage_logs_user_date` on `usage_logs(user_id, created_at DESC)`

**Given** the migrations have run
**When** RLS policy status is checked
**Then** RLS is enabled on both tables AND: `api_keys` has SELECT/INSERT/UPDATE policies scoped to `auth.uid() = user_id`; `usage_logs` has a SELECT policy scoped to `auth.uid() = user_id` and no INSERT policy (service role only)

### Story 1.5: Deploy API to Railway with Auto-Restart

As a developer building OpenTalon,
I want the API deployed to Railway with environment variables configured, health check monitoring active, and HTTPS enforced,
So that the proxy is reachable from the CLI and Railway automatically restarts the service on failure.

**Acceptance Criteria:**

**Given** the API is deployed to Railway
**When** `GET https://<app>.railway.app/health` is called
**Then** the response is `{"status": "ok"}` with HTTP 200 over HTTPS

**Given** Railway is configured
**When** the project settings are inspected
**Then** the following environment variables are set: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `OPENROUTER_API_KEY`, `DATABASE_URL`; health check path is `/health`; auto-restart on unhealthy status is enabled

**Given** an HTTP (non-HTTPS) request is attempted
**When** the request reaches Railway's edge
**Then** it is redirected to HTTPS (Railway handles TLS termination)

### Story 1.6: Deploy Web to Vercel and Set Up Homebrew Tap

As a developer building OpenTalon,
I want the web SPA deployed to Vercel and the Homebrew tap repository created with a working formula,
So that the dashboard is publicly accessible and the CLI can be installed on macOS with a single Homebrew command.

**Acceptance Criteria:**

**Given** the web is deployed to Vercel
**When** the Vercel URL is opened in a browser
**Then** the shell App renders without console errors and `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` are set as Vercel environment variables

**Given** a macOS machine with Homebrew
**When** `brew tap opentaion/tap` followed by `brew install opentaion` is run
**Then** the CLI installs successfully and `opentaion --version` prints the version string

**Given** the Homebrew tap repository (`opentaion/homebrew-tap`) is created on GitHub
**When** the formula file is examined
**Then** it references the correct CLI release artifact and passes `brew audit`

---

## Epic 2: Developer Authentication & API Key Management

A developer can register and sign in to the web dashboard via magic link, generate and manage their API keys in the web UI, and authenticate the CLI against their deployed API — completing the full onboarding ceremony.

### Story 2.1: API Auth Dependencies (Key Validation + JWT Validation)

As a developer building OpenTalon,
I want the two FastAPI auth dependencies — `verify_api_key()` and `verify_supabase_jwt()` — implemented and tested,
So that all subsequent API endpoints can declare their auth method via dependency injection.

**Acceptance Criteria:**

**Given** a valid `Authorization: Bearer ot_<key>` header where the key is active (not revoked)
**When** `verify_api_key()` is called as a dependency
**Then** it returns the `user_id` UUID associated with that key

**Given** the key prefix lookup runs
**When** `verify_api_key()` resolves candidates from `api_keys` by `key_prefix`
**Then** it uses `bcrypt.checkpw` with cost factor 10 and raises HTTP 401 if no match or if `revoked_at IS NOT NULL`

**Given** a valid Supabase Auth JWT in the `Authorization: Bearer` header
**When** `verify_supabase_jwt()` is called as a dependency
**Then** it verifies against `SUPABASE_JWT_SECRET`, extracts the `sub` claim as a UUID, and returns it

**Given** an invalid or expired token
**When** either auth dependency is called
**Then** it raises `HTTPException(status_code=401, detail="Unauthorized")`

**Given** tests are run
**When** `uv run pytest` is executed from `api/`
**Then** unit tests for both dependencies pass (valid key, revoked key, expired JWT, missing header)

### Story 2.2: API Key CRUD Endpoints

As a developer building OpenTalon,
I want `POST /api/keys`, `GET /api/keys`, and `DELETE /api/keys/{key_id}` endpoints implemented,
So that the web dashboard can generate, list, and revoke API keys for the authenticated user.

**Acceptance Criteria:**

**Given** an authenticated web user (valid Supabase JWT)
**When** `POST /api/keys` is called
**Then** a new API key is generated in the format `ot_` + `secrets.token_urlsafe(24)`, the full plaintext key is returned exactly once in the response (`{"id": "...", "key": "ot_...", "key_prefix": "...", "created_at": "..."}`), the `key_hash` (bcrypt cost 12) and `key_prefix` (first 12 chars) are stored in `api_keys`, and the plaintext key is never persisted (satisfies FR2, NFR4, NFR5)

**Given** an authenticated web user
**When** `GET /api/keys` is called
**Then** all active keys (`revoked_at IS NULL`) for the user are returned as a list with fields `id`, `key_prefix`, `created_at` — no `key_hash` exposed (satisfies FR3)

**Given** an authenticated web user with an existing active key
**When** `DELETE /api/keys/{key_id}` is called with a valid key ID belonging to the user
**Then** `revoked_at` is set to `NOW()` for that key and HTTP 204 is returned (satisfies FR4)

**Given** a key ID belonging to a different user
**When** `DELETE /api/keys/{key_id}` is called
**Then** HTTP 404 is returned (no cross-user key access)

**Given** tests are run
**When** `uv run pytest` is executed from `api/`
**Then** tests for all three endpoints pass (happy path, not found, unauthorized)

### Story 2.3: Web Auth Shell — Login Page with Magic Link

As a developer building OpenTalon,
I want the web login page implemented with a Supabase magic link flow,
So that a new developer can authenticate and reach the dashboard.

**Acceptance Criteria:**

**Given** the web app is loaded and the user is unauthenticated
**When** the page renders
**Then** the `<LoginForm>` component displays: a centered card with the "OpenTalon" heading, an email input with `<label>` association, and a "Send magic link" primary button (satisfies UX-DR2, UX-DR9, UX-DR11, UX-DR12)

**Given** the user enters a valid email and clicks "Send magic link"
**When** the Supabase `signInWithOtp` call succeeds
**Then** the form state transitions to the post-send confirmation: button is replaced with "✉ Check your email for a sign-in link. The link expires in 10 minutes."

**Given** the user clicks a valid magic link in their email
**When** the Supabase session is established
**Then** `supabase.auth.onAuthStateChange()` fires, `user` state is set, and the authenticated view renders (satisfies FR5)

**Given** the `signInWithOtp` call fails
**When** the error occurs
**Then** an error message is shown in `text-red-600 text-sm` with `role="alert"` below the input

**Given** an authenticated session already exists (browser refresh)
**When** the app loads
**Then** the user is taken directly to the authenticated view without re-entering email

**Given** all interactive elements
**When** navigated via keyboard
**Then** all elements have visible focus rings: `focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2` (satisfies UX-DR10)

### Story 2.4: Web Authenticated Shell — Sidebar Navigation

As a developer building OpenTalon,
I want the authenticated app shell implemented with the `<Sidebar>` and conditional view rendering,
So that an authenticated user can navigate between the Dashboard and API Keys views.

**Acceptance Criteria:**

**Given** the user is authenticated
**When** the app renders
**Then** the two-panel layout displays: a `<aside>` with `w-[220px]` fixed sidebar containing the "OpenTalon" logo label, a `<nav aria-label="Main navigation">` with "Dashboard" and "API Keys" `<button>` items, and a main content area (`flex-1 p-6`) rendering the active view (satisfies UX-DR1, UX-DR9)

**Given** the user clicks "Dashboard" in the sidebar
**When** `activeView` state changes to `"dashboard"`
**Then** the Dashboard view renders and the "Dashboard" nav item has `bg-blue-50 text-blue-600 rounded-md` active styling with `aria-current="page"`

**Given** the user clicks "API Keys" in the sidebar
**When** `activeView` state changes to `"keys"`
**Then** the API Keys view renders and the "API Keys" nav item has `bg-blue-50 text-blue-600 rounded-md` active styling with `aria-current="page"`

**Given** the user signs out (via a sign-out action in the sidebar)
**When** `supabase.auth.signOut()` is called
**Then** the session is cleared and the unauthenticated `<LoginForm>` renders

### Story 2.5: Web API Keys View — Generate, List, and Revoke

As a developer building OpenTalon,
I want the API Keys view implemented with key generation, the one-time display banner, the key list, and revoke actions,
So that a developer can generate a key to paste into `opentaion login` and manage their active keys.

**Acceptance Criteria:**

**Given** the user navigates to the API Keys view
**When** the view renders
**Then** a "Generate new key" primary button (`bg-blue-600`) is displayed and the key list shows existing active keys with truncated preview (`font-mono text-xs text-gray-600`) and "Revoke" destructive text buttons (`text-red-600`) (satisfies FR3, UX-DR5, UX-DR12)

**Given** no keys exist
**When** the key list renders
**Then** an empty state message is shown: "No API keys yet. Generate one to connect your CLI."

**Given** the user clicks "Generate new key"
**When** `POST /api/keys` succeeds
**Then** the `<NewKeyBanner>` renders with `role="alert"`, displaying the full plaintext key with "Copy this key now — it won't be shown again." instruction and a copy button (satisfies FR2, NFR5, UX-DR6)

**Given** the user clicks the copy button in `<NewKeyBanner>`
**When** `navigator.clipboard.writeText()` succeeds
**Then** the button shows "Copied ✓" for 2 seconds then reverts to "Copy" (satisfies UX-DR6)

**Given** the user clicks "Revoke" on an active key
**When** `DELETE /api/keys/{key_id}` succeeds
**Then** the key is removed from the list immediately with no confirmation modal (satisfies FR4)

**Given** a revoke is in-flight
**When** the request is pending
**Then** the "Revoke" button for that row shows "Revoking..." and is disabled (satisfies UX-DR5)

### Story 2.6: CLI `opentaion login` Command

As a developer building OpenTalon,
I want the `opentaion login` command implemented,
So that I can authenticate my CLI against my deployed API by entering the proxy URL and pasting my API key.

**Acceptance Criteria:**

**Given** the user runs `opentaion login`
**When** the command starts
**Then** the terminal displays the setup header and sequentially prompts: (1) `Proxy URL (e.g. https://your-api.railway.app):` then (2) `OpenTalon API Key:` (input hidden) — matching the UX-DR8 setup flow exactly

**Given** the user enters a proxy URL and API key
**When** the CLI attempts to reach `GET <proxy_url>/health`
**Then** if reachable: credentials are written to `~/.opentaion/config.json` as `{"proxy_url": "...", "api_key": "...", "user_email": ""}`, and the terminal prints `✓ Connected to <proxy_url>` and `✓ Configuration saved to ~/.opentaion/config.json` (satisfies FR11, FR26, UX-DR8)

**Given** the proxy URL is unreachable
**When** the health check fails
**Then** the terminal prints `✗ Proxy unreachable: <url>` in bold red to stderr, with a hint to check the Railway deployment, and the config file is NOT written (satisfies UX-DR8)

**Given** `~/.opentaion/config.json` already exists
**When** `opentaion login` is run again
**Then** the existing config is overwritten with the new values

**Given** tests are run
**When** `uv run pytest` is executed from `cli/`
**Then** tests pass for: successful login (mocked health check), unreachable proxy (mocked failure), and config file write/overwrite

---

## Epic 3: Metered Task Execution

A developer can invoke an agentic coding task from the terminal with an explicit effort tier, have it routed to the correct model via the proxy, and see the total token count and cost in the terminal the moment the task completes.

### Story 3.1: Model Pricing Dict and Cost Computation

As a developer building OpenTalon,
I want a `model_pricing` Python dict defined in the API with per-token prices for all supported OpenRouter models,
So that cost can be computed server-side from raw token counts at the moment of every usage log write.

**Acceptance Criteria:**

**Given** an OpenRouter model ID (e.g. `"deepseek/deepseek-r1"`)
**When** `compute_cost(model, prompt_tokens, completion_tokens)` is called
**Then** it returns a `decimal.Decimal` cost derived exclusively from the `model_pricing` dict — no external API call in the computation path (satisfies NFR13)

**Given** a model ID not present in the dict
**When** `compute_cost()` is called
**Then** it returns `Decimal("0")` and logs a warning to stdout (graceful degradation — usage record is still written)

**Given** the effort tier mapping is defined
**When** `/effort low`, `/effort medium`, or `/effort high` is specified
**Then** the tier maps to a specific OpenRouter model ID: `low` → `deepseek/deepseek-r1`, `medium` → `meta-llama/llama-3.3-70b-instruct:free`, `high` → `qwen/qwen-2.5-72b-instruct:free` (configurable via env var override)

**Given** tests are run
**When** `uv run pytest` is executed from `api/`
**Then** unit tests pass for: known model cost calculation, unknown model graceful fallback, all three tier-to-model mappings

### Story 3.2: `POST /v1/chat/completions` Transparent Proxy

As a developer building OpenTalon,
I want the `POST /v1/chat/completions` endpoint implemented as a transparent proxy to OpenRouter,
So that the CLI can send LLM requests that are validated, key-swapped, forwarded, and returned unmodified.

**Acceptance Criteria:**

**Given** a request with a valid `Authorization: Bearer ot_<key>` header
**When** `POST /v1/chat/completions` is called with any syntactically valid OpenRouter-compatible body
**Then** the request body is read as raw bytes and forwarded to OpenRouter unmodified — no JSON parsing, no field validation (satisfies FR12, FR13, FR14, NFR12)

**Given** the proxy forwards the request
**When** the key swap occurs
**Then** the `Authorization` header sent to OpenRouter contains the server's `OPENROUTER_API_KEY` environment variable — the user's `ot_` key never reaches OpenRouter (satisfies NFR7)

**Given** OpenRouter returns a response
**When** the proxy handler returns
**Then** the OpenRouter response is returned to the CLI unmodified with the same status code and headers (satisfies FR14)

**Given** OpenRouter returns an error (e.g. 429, 502)
**When** the proxy receives it
**Then** the error is forwarded to the CLI with status `{"detail": "Proxy error: <status>"}` (uniform error shape)

**Given** the proxy latency is measured
**When** 100 requests are processed (excluding OpenRouter response time)
**Then** the median proxy overhead is under 200ms (satisfies NFR1)

**Given** tests are run
**When** `uv run pytest` is executed from `api/`
**Then** tests pass for: valid key + body forwarded, invalid key rejected (401), raw bytes forwarded (no body parsing), OpenRouter error propagation — all using `httpx` mock

### Story 3.3: Async Usage Logging

As a developer building OpenTalon,
I want usage data written to `usage_logs` asynchronously via FastAPI `BackgroundTasks` after every proxied LLM call,
So that token counts and cost are recorded without blocking the response being returned to the CLI.

**Acceptance Criteria:**

**Given** OpenRouter returns a successful response
**When** the proxy handler returns the response to the CLI
**Then** a `BackgroundTasks` task is enqueued to write a `usage_logs` record — the response is returned to the CLI before the write completes (satisfies FR15, NFR9)

**Given** the background task runs
**When** it writes the usage record
**Then** the record contains: `user_id` (from `verify_api_key`), `model` (from the OpenRouter response `model` field), `prompt_tokens` (from `usage.prompt_tokens`), `completion_tokens` (from `usage.completion_tokens`), `cost_usd` (computed via `compute_cost()` from Story 3.1), `created_at` (server-side `NOW()`) (satisfies FR16, FR17, FR18, FR19)

**Given** the background write fails (e.g. DB connection error)
**When** the exception is raised
**Then** the error is logged to stdout only — it does not propagate to the CLI and does not affect the already-returned response (satisfies NFR9)

**Given** `cost_usd` is stored
**When** the value is written
**Then** it is a `NUMERIC(10,8)` derived from `compute_cost()` using `decimal.Decimal` — never a float, never client-provided (satisfies FR18, NFR13)

**Given** tests are run
**When** `uv run pytest` is executed from `api/`
**Then** tests pass for: successful write with correct fields, write failure does not raise (logged only), cost_usd type is Decimal

### Story 3.4: CLI `/effort` Command — Multi-Turn Agent Loop with Tool Execution

As a developer building OpenTalon,
I want the `opentaion /effort [low|medium|high] "<prompt>"` command implemented as a true multi-turn agent loop with tool execution,
So that I can run agentic coding tasks that read and modify files across multiple LLM iterations and see the total accumulated cost immediately when the task completes.

**Acceptance Criteria:**

**Given** `~/.opentaion/config.json` exists with `proxy_url` and `api_key`
**When** `opentaion /effort low "add docstrings to utils.py"` is run
**Then** the CLI prints `[dim]  ◆ Model: deepseek/deepseek-r1 (low tier)[/dim]` and begins the agent loop by sending the initial user message to `<proxy_url>/v1/chat/completions` with `Authorization: Bearer <api_key>`, the mapped model ID, and the tool definitions included in the request body (satisfies FR6, FR7, UX-DR8)

**Given** the tool definitions are included in the request
**When** the request body is constructed
**Then** it includes at minimum three tools with OpenRouter-compatible JSON schemas:
- `read_file(path: str) → str` — reads and returns file contents
- `write_file(path: str, content: str) → str` — writes content to file, returns confirmation
- `run_command(command: str) → str` — executes a shell command, returns stdout + stderr (capped at 4000 chars)

**Given** the LLM response contains `tool_calls`
**When** the agent loop processes the response
**Then** for each tool call: the CLI prints `[dim]  ◆ {tool_name}({args_summary})[/dim]`, executes the tool locally, appends the `assistant` message with tool_calls and a `tool` result message to the messages list, and sends the updated messages list in the next proxy request — accumulating `prompt_tokens + completion_tokens` from each iteration's `usage` field

**Given** the LLM response contains no `tool_calls` (the model returns a final text response)
**When** the loop detects termination
**Then** the loop exits cleanly — this is the normal completion path

**Given** the loop has run 20 iterations without terminating
**When** the 20th iteration completes
**Then** the loop is forcibly terminated with a warning: `[dim]  ◆ Max iterations reached. Stopping.[/dim]` — this is a safety limit against runaway loops (prevents unbounded token spend)

**Given** the loop terminates (either naturally or via max iterations)
**When** the cost summary is displayed
**Then** the terminal prints `[bold]✓ Task complete.[/bold]  [dim]Tokens: {total:,}[/dim]  [dim]|[/dim]  [bold cyan]Cost: ${cost:.4f}[/bold cyan]` where `total` and `cost` are the **sum across all loop iterations** — not a single call's values (satisfies FR8, UX-DR8)

**Given** no `/effort` flag is provided (e.g. `opentaion "fix the bug"`)
**When** the command runs
**Then** the `low` tier is used silently as the default — no error, no warning

**Given** the config file does not exist
**When** any `/effort` command is run
**Then** the CLI prints an error directing the user to run `opentaion login` first and exits with code 1

**Given** tests are run
**When** `uv run pytest` is executed from `cli/`
**Then** tests pass for: correct model mapped per tier, single-iteration task completes correctly, two-iteration task with tool call executes and accumulates tokens, max iterations safety limit triggers, missing config error, cost summary reflects accumulated totals across iterations

### Story 3.5: CLI Retry Logic and Proxy Error Handling

As a developer building OpenTalon,
I want the CLI to automatically retry a failed proxy connection once on the first call and exit cleanly with an actionable error on any unrecoverable failure,
So that transient failures (e.g. Railway cold start) recover automatically and permanent failures fail visibly without leaving partial state.

**Acceptance Criteria:**

**Given** the very first proxy request in a task fails with a connection error
**When** the CLI detects the failure
**Then** it silently retries that same request once — no error output on the first attempt (satisfies FR9)

**Given** the retry of the first call also fails
**When** the second connection error occurs
**Then** the CLI prints to stderr: `[bold red]✗ Proxy unreachable: <proxy_url>[/bold red]` followed by `  Could not connect to the OpenTalon API server.\n  Check that your Railway deployment is running.\n\n  Run [cyan]\`opentaion login\`[/cyan] to update your proxy URL.` and exits with code 1 within 5 seconds of the initial failure — no cost summary is shown (satisfies FR10, NFR10, UX-DR8)

**Given** the first call fails but the retry succeeds
**When** the retry response is received
**Then** execution continues normally with the agent loop — the user sees only progress bullets and the final cost summary

**Given** a connection error occurs mid-loop (after one or more iterations have already completed successfully)
**When** the error is detected
**Then** the task fails immediately with the same `✗ Proxy unreachable` error message and exits with code 1 — no retry is attempted mid-loop, no partial cost summary is shown, and no partial results are presented (clean failure semantics: the metering contract holds or the command fails)

**Given** the proxy returns HTTP 401 (invalid API key)
**When** the error is received at any point in the loop
**Then** the CLI prints `✗ Authentication failed: invalid API key. Run \`opentaion login\` to reconfigure.` and exits with code 1 — no retry on auth failures

**Given** tests are run
**When** `uv run pytest` is executed from `cli/`
**Then** tests pass for: retry on first-call connection error + success, retry on first-call connection error + second failure (exit 1, message, timing), mid-loop connection error fails immediately without retry, no retry on 401

---

## Epic 4: Usage Visibility Dashboard

A developer can open their web dashboard and immediately see a 30-day bar chart of token usage and a per-model cost breakdown table — allowing them to identify spending patterns and cost spikes at a glance.

### Story 4.1: `GET /api/usage` Endpoint

As a developer building OpenTalon,
I want the `GET /api/usage` endpoint implemented,
So that the web dashboard can fetch 30 days of my usage records aggregated by model and day in a single request.

**Acceptance Criteria:**

**Given** an authenticated web user (valid Supabase JWT)
**When** `GET /api/usage` is called
**Then** the response contains all `usage_logs` records for that user from the last 30 days with the shape: `{"records": [{"date": "2026-03-24", "model": "...", "prompt_tokens": N, "completion_tokens": N, "cost_usd": "0.00000000"}], "total_cost_usd": "0.00120000", "period_days": 30}` (satisfies FR20, FR21)

**Given** the query runs
**When** the database is queried
**Then** it uses the `idx_usage_logs_user_date` index and returns within 2 seconds for a standard 30-day dataset (satisfies NFR2)

**Given** the user has no usage records
**When** `GET /api/usage` is called
**Then** the response is `{"records": [], "total_cost_usd": "0.00000000", "period_days": 30}` — no error

**Given** all monetary values in the response
**When** serialized
**Then** `cost_usd` and `total_cost_usd` are decimal strings with 8 decimal places (e.g. `"0.00120000"`) — never floats

**Given** tests are run
**When** `uv run pytest` is executed from `api/`
**Then** tests pass for: populated 30-day window, empty result, JWT auth required (401 without token), decimal string serialization

### Story 4.2: Web Dashboard View — Usage Chart and Model Table

As a developer building OpenTalon,
I want the Dashboard view implemented with a 30-day bar chart and per-model cost summary table,
So that I can see my spending patterns and identify cost spikes at a glance within 3 seconds of page load.

**Acceptance Criteria:**

**Given** the user navigates to the Dashboard view
**When** the view mounts
**Then** a single `useEffect` fires a `GET /api/usage` request with the Supabase session JWT in the `Authorization` header — no polling, no refetch on focus (satisfies FR22)

**Given** the API response arrives
**When** the data renders
**Then** the `<UsageChart>` component displays a Recharts `<BarChart>` inside `<ResponsiveContainer height={192}>` with one bar per day, bar fill `bg-blue-600`, no Y-axis label, and a tooltip showing exact token count and cost on hover (satisfies FR20, UX-DR3)

**Given** the chart renders
**When** inspected for accessibility
**Then** the chart wrapper has `role="img" aria-label="30-day token usage bar chart"` (satisfies UX-DR3)

**Given** the API response arrives
**When** the data renders
**Then** the `<ModelTable>` displays a `<table>` with `<thead>` columns (Model, Tokens, Cost), `<tbody>` rows for each model with tokens formatted via `toLocaleString()` and cost as `$${cost.toFixed(4)}`, and a `<tfoot>` total row with `bg-gray-50 font-medium` — all `<th>` elements have correct `scope` attributes (satisfies FR21, UX-DR4, UX-DR11)

**Given** the user has no usage data
**When** the Dashboard view renders
**Then** the chart shows an empty state: "No usage yet. Run your first task." and the model table shows no rows

**Given** the page loads on a standard broadband connection
**When** time-to-interactive is measured
**Then** the chart and table are rendered within 3 seconds (satisfies NFR3)

**Given** the page heading and section structure
**When** examined
**Then** the view uses `text-xl font-semibold text-gray-900` for the "Usage — Last 30 Days" heading, `space-y-6` between sections, and `bg-white rounded-lg border border-gray-200 p-6` for card containers (satisfies UX-DR9)
