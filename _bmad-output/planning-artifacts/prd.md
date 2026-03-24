---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-02c-executive-summary', 'step-03-success', 'step-04-journeys', 'step-05-domain', 'step-06-innovation', 'step-07-project-type', 'step-08-scoping', 'step-09-functional', 'step-10-nonfunctional', 'step-11-polish', 'step-12-complete']
completedAt: '2026-03-23'
inputDocuments: ['_bmad-output/planning-artifacts/product-brief-opentaion-2026-03-23.md']
briefCount: 1
researchCount: 0
brainstormingCount: 0
projectDocsCount: 0
workflowType: 'prd'
classification:
  projectType: 'cli_tool+api_backend+web_app'
  domain: 'developer_tooling'
  complexity: 'low'
  projectContext: 'greenfield'
---

# Product Requirements Document — OpenTalon

**Author:** Miao
**Date:** 2026-03-23

## Executive Summary

OpenTalon is a macOS CLI agent and companion web dashboard that gives solo developers cost literacy and decision enablement over their AI tool usage. The target user is a budget-conscious solo developer who runs 1–3 AI coding assistants regularly, prefers self-hosted tooling over SaaS, and faces an acute problem: agentic coding tools have an n² token cost curve — context windows grow with every tool call in an agent loop, making costs exponential and unpredictable. Standard API dashboards (OpenAI, Anthropic) meter at the API-key level, making it impossible to know whether today's $5 spend came from a productive architecture session or a runaway loop chasing a CSS bug.

OpenTalon solves this by metering at the agent-loop level. Every LLM call is routed through a local proxy that ties token consumption to the specific task and session. When a task completes, the developer sees the cost immediately in the terminal: `Task complete. Tokens: 4,500. Cost: $0.001.` This closes the feedback loop that no other tool closes.

### What Makes This Special

Three things differentiate OpenTalon from any existing solution:

1. **Loop-level metering.** The proxy intercepts at the agent loop, not the API key. Cost is attributed to the task, not the billing period. This is the debugging primitive that doesn't exist anywhere else.

2. **The `/effort` routing system.** Developers consciously select a model tier per task (`/effort low`, `/effort high`). OpenTalon routes to the appropriate model, executes the loop, and reports actual cost at completion. Control and transparency in a single gesture.

3. **OpenRouter-first architecture.** By routing through OpenRouter, free open-source models (Llama 3.3, Qwen 2.5, DeepSeek R1) are first-class citizens. A solo developer can run real agentic workflows without a credit card. This democratizes agentic engineering for developers who've been priced out.

## Project Classification

- **Project Type:** CLI tool (primary) + API backend (usage proxy) + Web app (dashboard)
- **Domain:** Developer tooling
- **Complexity:** Low — no regulated domain, standard auth, standard relational data
- **Project Context:** Greenfield

## Success Criteria

### User Success

The primary success signal is **behavioral change**: a developer actively selects `/effort low` for boilerplate and scaffolding tasks and `/effort high` for architectural reasoning, rather than defaulting to the most capable model for every prompt. Token economics become a conscious variable in their workflow, not an invisible cost that accumulates offscreen.

The "aha moment" occurs in the terminal, immediately after the first completed agentic loop. Seeing `Tokens: 4,500 | Cost: $0.001` printed directly below generated code makes abstract token economics concrete and personal. This moment — not the dashboard, not the weekly chart — is the product's core value delivery.

Secondary signal: zero billing surprises after the developer's first full month using OpenTalon as their primary coding agent interface.

### Business Success

OpenTalon is open-source and self-hosted with no monetization layer. Business success is measured entirely by reader success with the companion book *OpenTalon: Building an Agentic Coding Assistant with Claude Code.*

**Success means:**
- A reader completes all book chapters and has a working three-component installation: CLI via Homebrew, API on Railway, web dashboard on Vercel
- GitHub stars and reader testimonials are the primary traction metrics
- No feature gaps between the book's prose and the actual codebase — every code example compiles, runs, and produces the documented output

### Technical Success

Proxy latency overhead must stay under 200ms per LLM call (hard requirement, not target), cost attribution must match OpenRouter invoices to the cent, and the Railway-hosted API must have health checks and automatic restarts. These are formalized in NFR1–NFR13.

### Measurable Outcomes

| Metric | Target |
|---|---|
| Proxy latency overhead | < 200ms per LLM call |
| Cost attribution accuracy | 100% match to OpenRouter invoice |
| Book completion | Reader reaches working 3-component deployment |
| CLI install method | Homebrew tap (single command) |
| Deployment targets | Railway (API) + Vercel (Web) |

## User Journeys

Four journeys cover the full interaction surface. Each journey's revealed requirements are captured in the Functional Requirements section.

### Journey 1: The First-Time Installer

**Persona:** Alex, a backend developer who just finished Chapter 10 of the book. The API is live on Railway. The dashboard is deployed to Vercel. The book says: "Now install the CLI."

**Opening Scene:** Alex opens a terminal on their MacBook. They've been following along, building each component, and they're one command away from having all three pieces connected.

**Rising Action:**
```bash
brew install opentaion/tap/opentaion
opentaion login
```
The CLI prints: `Enter your email to receive a magic link:`. Alex types their email. A link arrives. They click it. The browser confirms authentication. Back in the terminal: `✓ Authenticated. OpenTalon is ready.`

**Climax:** Alex runs their first real task:
```bash
opentaion /effort low "scaffold a FastAPI health check endpoint"
```
The agent loop executes. Code appears. Then: `Tokens: 2,100 | Cost: $0.0002`. First metered task. The loop is closed.

**Resolution:** Alex has a working three-component installation. The CLI is authenticated against their Railway backend. Every subsequent LLM call will be metered and attributed.

### Journey 2: The Active Developer (Happy Path)

**Persona:** Sam, a solo developer two weeks into daily OpenTalon use. They've internalized the effort tiers.

**Opening Scene:** Sam needs to add input validation to a form handler — routine, mechanical work. They reach for `/effort low` without thinking twice.

**Rising Action:**
```bash
opentaion /effort low "add pydantic validation to the user registration endpoint"
```
OpenTalon routes to a fast, cheap model (Qwen 2.5 via OpenRouter). The loop runs — reads the file, writes the validation, runs the tests. Three tool calls. Context stays small. Task completes in 18 seconds.

**Climax:** `✓ Task complete. Tokens: 3,800 | Cost: $0.0004`

Sam pauses. Yesterday they ran the same category of task with their default model out of habit. That cost $0.04. Same output quality. 100x the cost. The gap is no longer abstract — it has a number.

**Resolution:** Sam opens the dashboard that evening. The bar chart shows two peaks: Wednesday's architectural session (expensive, justified) and today's validation work (cheap, appropriate). The effort tiers are working as intended.

### Journey 3: The Cost-Conscious Developer (Investigation Path)

**Persona:** Jordan, who checks the OpenTalon dashboard every few days. They notice Thursday's bar is unusually tall — $1.20, when a normal day is $0.08.

**Opening Scene:** Jordan opens the dashboard on Friday morning and sees the spike.

**Rising Action:** Jordan scans the per-model breakdown. The spike is entirely on a high-tier model. They remember: Thursday afternoon, they asked the agent to refactor a large legacy module. The loop ran for 40+ minutes, accumulating context with every tool call — the n² curve in action.

**Climax:** The dashboard doesn't explain *why* the spike happened (session-level attribution is a V2 feature), but it tells Jordan *when* and *which model*. The data confirms their intuition.

**Resolution:** Jordan adds a personal rule: anything touching more than two files gets broken into `/effort medium` subtasks. The dashboard has done its job — not by preventing the spike, but by making it visible enough to generate a behavioral change.

### Journey 4: The Broken Environment (Failure Path)

**Persona:** Casey, a developer who just returned from a two-week vacation. Their Railway deployment auto-slept due to inactivity (Railway's free-tier behavior).

**Opening Scene:** Casey runs an OpenTalon task and waits. Nothing happens for three seconds. Then:

```
Error: Could not reach OpenTalon proxy. Please check your Railway deployment.
```

Exit code 1. No LLM call was made. No partial output. Clean failure.

**Rising Action:** Casey recognizes the error — Railway free-tier deployments sleep after inactivity. They open the Railway dashboard, trigger a manual wake, and wait 30 seconds for cold-start.

**Climax:** Casey retries the original command. The proxy responds. `Tokens: 5,200 | Cost: $0.0006`. Business as usual.

**Resolution:** The CLI's clean failure — no fallback, no silent data loss — preserved the integrity of the metering contract. Casey documents the cold-start behavior in their setup notes.

## Innovation & Novel Patterns

### Detected Innovation Areas

**1. Agent-Loop Observability — A New Primitive**

Existing LLM API dashboards (OpenAI usage, Anthropic console) meter at the API-key level and report in billing-period aggregates. OpenTalon introduces **loop-level cost attribution**: token consumption tied to the specific task and session at the moment of execution, not reconciled from a monthly invoice.

**2. The `/effort` Command — Intentional Model Routing**

The `/effort [low|medium|high]` command makes model selection an *explicit developer decision* rather than a hidden configuration. The developer states their intent, the system executes accordingly, and the feedback loop closes immediately with actual cost data. Control, execution, and accountability in a single gesture.

**3. The n² Cost Curve as Product Foundation**

Agentic systems have an n² token cost curve because context windows grow with every tool call in the loop. A developer's cost intuitions — trained on single-turn chatbot interactions — are systematically wrong for agent workflows. OpenTalon makes the n² curve visible in real time, teaching token economics by instrumenting it.

### Market Context & Competitive Landscape

No existing tool occupies this space. The closest alternatives:

- **OpenAI/Anthropic usage dashboards** — API-key-level, billing-period granularity, no task attribution
- **LangSmith / Helicone** — team-oriented tracing tools; require external accounts and incur additional cost
- **Manual logging** — `print(response.usage)` is fragile, inconsistent, and not cumulative

OpenTalon's differentiation is the combination of: local proxy (no external account), loop-level attribution, CLI-driven model routing, and a self-hosted dashboard — designed for a single developer with zero infrastructure overhead.

### Validation Approach

Loop-level metering accuracy is validated by the product's own success criteria: reported cost must match OpenRouter invoices to the cent. Behavioral change (active `/effort` tier usage) validates the routing innovation.

### Innovation Risk Mitigation

- **Proxy adoption**: If setup is too complex, developers won't route through it. Mitigation: single-chapter Railway deployment walkthrough in the book.
- **Cost accuracy**: Token counts depend on OpenRouter response metadata. Mitigation: store raw token counts; recompute cost server-side; never trust client-reported costs.
- **OpenRouter free-tier availability**: If free models become scarce, the "no credit card" pitch weakens. Mitigation: model-tier mapping is configurable in the API; swapping models requires no CLI update.

## Technical Requirements

### Architecture Overview

OpenTalon is a three-component system with minimal coupling. The CLI speaks standard OpenRouter-compatible JSON. The API is a transparent gateway with metering. The dashboard is a read-only view over Supabase data. No component contains logic that belongs to another.

### CLI

**Commands**

| Command | Description |
|---|---|
| `opentaion login` | Prompts for email, sends Supabase magic link, stores proxy URL + API key to config |
| `opentaion /effort [low\|medium\|high] "<prompt>"` | Routes to model tier, executes agent loop, prints cost summary |
| `opentaion --version` | Prints CLI version |

**Config Storage**

Credentials and proxy URL stored in `~/.opentaion/config.json` — global, not project-scoped. The user pastes their OpenTalon API key (generated in the web dashboard) during `opentaion login`.

```json
{
  "proxy_url": "https://your-app.railway.app",
  "api_key": "ot_...",
  "user_email": "user@example.com"
}
```

**Output**

Rich terminal output via the `rich` library. Output printed on task completion (no streaming). Cost summary: `✓ Task complete. Tokens: X,XXX | Cost: $X.XXXX`. Errors to stderr; exit code 1 on proxy failure.

**V1 Exclusions**

No shell tab-completion · No streaming partial results · No conversation history persistence · No multi-file diff view · macOS only

### API

**Endpoint Surface**

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/chat/completions` | Transparent proxy: validates key, swaps for master OpenRouter key, forwards request, logs usage async, returns response |
| `GET` | `/health` | Railway health check — returns 200 OK |
| `GET` | `/api/usage` | Returns last 30 days of usage records for authenticated user |
| `GET` | `/api/keys` | Lists user's active API keys |
| `POST` | `/api/keys` | Generates a new API key |
| `DELETE` | `/api/keys/{key_id}` | Revokes an API key |

**Proxy Flow**

The `/v1/chat/completions` path mimics OpenRouter's exact path. The CLI sends a pre-formed OpenRouter-compatible body — the API does not transform it.

1. Validates `Authorization: Bearer ot_...` header against bcrypt-hashed keys in Supabase
2. Swaps the user's OpenTalon key for the server's master OpenRouter API key
3. Forwards the request to OpenRouter
4. Extracts token counts from response; writes usage record to Supabase **asynchronously** (does not block response)
5. Returns the OpenRouter response unmodified to the CLI

**Authentication**

- **CLI → API**: OpenTalon API key in `Authorization` header (bcrypt-hashed, stored in Supabase)
- **Web → API**: Supabase Auth JWT (magic link sessions), validated via Supabase middleware

**Cost Calculation**

Token counts extracted from `usage.prompt_tokens` and `usage.completion_tokens` in the OpenRouter response. Cost computed server-side from a model pricing table keyed by model ID. Raw token counts always stored; cost is derived, never trusted from the client.

### Web Dashboard

**Architecture**

SPA with two views toggled by Supabase auth state — no router. Unauthenticated: magic link login form. Authenticated: usage dashboard.

**Dashboard View**

- Recharts stacked bar chart: last 30 days of token usage, grouped by model per day
- Per-model cost summary table below the chart
- Data loaded via single `GET /api/usage` call on page render
- No polling, no WebSockets — manual browser refresh to see new data

**Authentication**

Supabase magic link: user enters email → receives link → clicks → session established → dashboard renders. No passwords stored anywhere.

**Browser Support**

Modern evergreen browsers (Chrome, Firefox, Safari, Edge). No IE11. No mobile optimization in V1.

**API Key Management**

Accessible from the authenticated dashboard. Generate new key (displayed once at creation), list active keys with truncated preview, revoke by ID. The generated key is pasted into `opentaion login`.

## Project Scoping & Phased Development

### MVP Strategy

**Approach:** Experience MVP — all three components ship together. The product's value is a complete feedback loop: CLI executes → API meters → dashboard visualizes. No component delivers the core promise in isolation.

**Resource Model:** Solo developer (the book reader) building across 21 chapters using Claude Code. Managed infrastructure (Railway, Vercel, Supabase) eliminates ops overhead.

### MVP Feature Set (Phase 1)

Supports Journey 1 (onboarding), Journey 2 (daily use), and Journey 4 (graceful failure). Journey 3 (cost investigation) is supported at daily + per-model granularity; session-level attribution is Phase 2.

**CLI:** `opentaion login` · `/effort [low|medium|high]` routing · per-task cost summary · single retry + hard exit on proxy failure · `~/.opentaion/config.json` · Homebrew tap

**API:** `POST /v1/chat/completions` transparent proxy · async usage logging · `GET /health` · `GET /api/usage` · `GET|POST|DELETE /api/keys` · bcrypt key hashing · Supabase JWT for web auth

**Web:** Magic link login · 30-day stacked bar chart (Recharts) · per-model cost summary table · API key generation + revocation UI

### Post-MVP Features (Phase 2)

- Token budget alerts (session-level spend threshold notifications)
- Per-project cost attribution (keyed to git repo directory)
- CSV export of usage data
- Homebrew formula auto-update mechanism

### Vision (Phase 3)

- IDE plugin (VS Code / Cursor) with inline cost display
- Multi-provider support (direct Anthropic, OpenAI alongside OpenRouter)
- Cost forecasting from historical usage patterns
- Community model benchmarking: cost-per-quality comparisons across OpenRouter free models

### Risk Mitigation

**Async logging failure:** Usage write fails after LLM response is returned — developer gets code but usage record is lost. Mitigation: log errors to Railway stdout; dead-letter table in Phase 2.

**Railway cold start:** Free-tier deployments sleep after inactivity. CLI's single-retry handles cold-starts up to ~30 seconds. Mitigation: documented in the book; health check endpoint enables monitoring.

**Scope creep:** Strict V1 exclusion list (no Windows, no teams, no non-OpenRouter providers, no streaming, no history) is enforced by `cli/SPEC.md` and this PRD. Any addition requires explicit PRD revision.

**Solo developer resource risk:** If implementation stalls, CLI + API is the minimum shippable unit. Terminal cost display alone delivers the core value. Dashboard is valuable but not required for the "aha moment."

## Functional Requirements

This is the capability contract for OpenTalon V1. Every epic, story, and design decision must trace to a requirement listed here. Any capability not listed is out of scope.

### Authentication & Identity

- **FR1:** Developer can authenticate the CLI by receiving a magic link at their email address and confirming it in a browser
- **FR2:** Developer can generate a new OpenTalon API key from the web dashboard (displayed once at creation)
- **FR3:** Developer can view a list of their active API keys with a truncated preview of each key
- **FR4:** Developer can revoke an API key by ID from the web dashboard
- **FR5:** Developer can authenticate the web dashboard by receiving a magic link at their email address

### Task Execution & Effort Routing

- **FR6:** Developer can invoke an agentic coding task from the terminal using a natural language prompt
- **FR7:** Developer can specify a model cost tier (`low`, `medium`, or `high`) per task to control which model OpenRouter uses
- **FR8:** Developer can view the total token count and computed cost for each completed task, printed in the terminal immediately after the task finishes
- **FR9:** The CLI automatically retries a failed proxy connection once before reporting failure
- **FR10:** The CLI exits with a non-zero status code and an actionable error message when the proxy is unreachable after the retry
- **FR11:** The CLI stores its proxy URL and API key in a persistent global config file, available across all project directories on the machine

### LLM Proxying

- **FR12:** The proxy validates the developer's OpenTalon API key on every incoming request before forwarding it
- **FR13:** The proxy forwards LLM requests to OpenRouter using the server's master OpenRouter API key, not the developer's key
- **FR14:** The proxy returns the OpenRouter response to the CLI without modification
- **FR15:** The proxy records usage data for each request asynchronously, without blocking the LLM response being returned to the CLI

### Usage Metering & Storage

- **FR16:** The system records prompt token count, completion token count, and model ID for each proxied LLM call
- **FR17:** The system records a timestamp for each proxied LLM call
- **FR18:** The system computes cost server-side from stored token counts using a model pricing table; cost is never accepted from the client
- **FR19:** The system associates each usage record with the authenticated developer who made the request

### Usage Visibility

- **FR20:** Developer can view a bar chart of their token usage for the last 30 days, grouped by day and broken down by model
- **FR21:** Developer can view a per-model cost summary table for their last 30 days of usage
- **FR22:** The dashboard fetches and renders usage data automatically when the authenticated view loads
- **FR23:** Developer can access API key management (generate, list, revoke) from the authenticated dashboard

### Distribution & Operations

- **FR24:** Developer can install the CLI on macOS using a single Homebrew command
- **FR25:** The API exposes a health check endpoint that returns a successful response when the service is operational
- **FR26:** The CLI displays a confirmation message in the terminal upon successful first-time authentication

## Non-Functional Requirements

### Performance

- **NFR1:** The API proxy must add less than 200ms of overhead to any LLM API call, measured from request receipt to response forwarding. Hard requirement — not a target.
- **NFR2:** `GET /api/usage` must return a response within 2 seconds for a standard 30-day dataset.
- **NFR3:** The web dashboard must display usage data within 3 seconds of page load on a standard broadband connection.

### Security

- **NFR4:** OpenTalon API keys must be stored bcrypt-hashed in the database; plaintext keys must never be persisted.
- **NFR5:** A generated API key must be displayed exactly once at creation; it must not be retrievable after the creation response.
- **NFR6:** All client-server communication must use HTTPS; the API must not accept or serve unencrypted HTTP requests.
- **NFR7:** The master OpenRouter API key must be stored exclusively as a server-side environment variable; it must never appear in any response, log output, or client-accessible resource.
- **NFR8:** User email address is the only PII stored in the system; no passwords are stored anywhere.

### Reliability

- **NFR9:** Usage logging failures must not delay or prevent the LLM response being returned to the CLI. The logging write is asynchronous and its failure must be silent to the end user.
- **NFR10:** The CLI must surface a deterministic error message and exit within 5 seconds of a proxy connection failure, after one retry attempt.
- **NFR11:** The API must expose a `/health` endpoint that Railway can poll; the service must restart automatically on unhealthy status.

### Integration

- **NFR12:** The proxy endpoint must accept any syntactically valid OpenRouter-compatible request body without modification; the API must not reject requests based on unrecognized fields.
- **NFR13:** Cost calculation must derive exclusively from token counts in the OpenRouter response metadata; cost must not depend on any external pricing API call in the request path.
