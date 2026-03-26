# OpenTalon — User & Deployment Guide

## Contents

1. [What is OpenTalon?](#1-what-is-opentaion)
2. [User Guide — Using the CLI](#2-user-guide--using-the-cli)
3. [User Guide — Using the Web Dashboard](#3-user-guide--using-the-web-dashboard)
4. [Deployment Guide — Self-Hosting](#4-deployment-guide--self-hosting)
   - [Supabase](#41-supabase)
   - [OpenRouter](#42-openrouter)
   - [Railway (API)](#43-railway-api)
   - [Vercel (Web)](#44-vercel-web)
   - [Environment Variables Reference](#45-environment-variables-reference)
5. [Troubleshooting](#5-troubleshooting)

---

## 1. What is OpenTalon?

OpenTalon is an agentic coding assistant with three components:

| Component | What it is |
|-----------|-----------|
| **CLI** | Terminal agent — you describe a task, it plans and executes tool calls (read files, run commands, edit code) until done |
| **API** | FastAPI proxy on Railway — authenticates your requests, forwards them to OpenRouter, logs usage |
| **Web dashboard** | Vercel app — sign in with magic link, manage API keys, view token usage and cost |

All LLM calls go through [OpenRouter](https://openrouter.ai), which provides access to free models (no credit card required).

---

## 2. User Guide — Using the CLI

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- An OpenTalon account (sign up at the web dashboard)
- An OpenTalon API key (generated from the web dashboard)

### Installation

```bash
git clone https://github.com/Miao-tech/opentaion.git
cd opentaion/cli
```

### Login

```bash
uv run python -m opentaion login
```

You will be prompted for:

- **Proxy URL** — the Railway API URL, e.g. `https://opentaion-production.up.railway.app`
- **OpenTalon API Key** — the `ot_...` key you generated from the web dashboard

Credentials are saved to `~/.opentaion/config.json` (permissions: 600).

### Running a task

```bash
uv run python -m opentaion effort "<your task description>"
```

**Examples:**

```bash
# List files
uv run python -m opentaion effort "list all Python files in this project"

# Fix a bug
uv run python -m opentaion effort "find and fix the bug in src/auth.py"

# Refactor
uv run python -m opentaion effort "refactor the database connection code to use a context manager"

# Explain code
uv run python -m opentaion effort "explain what the agent loop in agent.py does"
```

### What the CLI does

The agent loop works as follows:

1. Sends your prompt to the LLM via the OpenTalon proxy
2. The LLM responds with a plan and tool calls (read file, run command, edit file, etc.)
3. The CLI executes the tool calls locally on your machine
4. Results are sent back to the LLM for the next iteration
5. The loop continues until the LLM produces a final answer with no tool calls

### Available tools

| Tool | What it does |
|------|-------------|
| `read_file` | Read the contents of a file |
| `write_file` | Write content to a file |
| `edit_file` | Make a targeted edit to a specific part of a file |
| `glob_files` | Find files matching a pattern (e.g. `**/*.py`) |
| `search_files` | Search file contents with a regex pattern |
| `run_bash` | Execute a shell command |

### Cost

All default models are free (no credit card required). The cost summary at the end of each task shows `$0.0000` for free-tier models. Usage is also logged in your web dashboard.

### Effort tiers

The CLI supports three tiers that select the model:

```bash
uv run python -m opentaion effort --tier low "your task"    # default
uv run python -m opentaion effort --tier medium "your task"
uv run python -m opentaion effort --tier high "your task"
```

All tiers currently use `nvidia/nemotron-3-super-120b-a12b:free`. This can be overridden per-tier via Railway environment variables (`OPENROUTER_EFFORT_MODEL_LOW`, `OPENROUTER_EFFORT_MODEL_MEDIUM`, `OPENROUTER_EFFORT_MODEL_HIGH`).

---

## 3. User Guide — Using the Web Dashboard

### Signing in

1. Go to `https://opentaion.vercel.app`
2. Enter your email address
3. Click **Send magic link**
4. Check your email and click the link — you are now signed in

> The magic link expires after a few minutes. If it doesn't work, request a new one.

### Managing API keys

Navigate to **API Keys** in the sidebar.

**Generate a key:**
1. Click **Generate Key**
2. Copy the full key immediately — it is shown only once
3. The key starts with `ot_` and is 35 characters long

**Revoke a key:**
- Click the revoke button next to any key
- Revoked keys cannot be un-revoked — generate a new one if needed

### Viewing usage

Navigate to **Usage** in the sidebar to see:

- A bar chart of token usage over time
- A table breaking down usage by model
- Total cost in USD (always $0.00 for free-tier models)

---

## 4. Deployment Guide — Self-Hosting

This section covers how to deploy your own instance of OpenTalon from scratch. You will need accounts on Supabase, OpenRouter, Railway, and Vercel — all have free tiers.

### 4.1 Supabase

Supabase provides the database (PostgreSQL) and authentication (magic links).

**Create a project:**

1. Go to [supabase.com](https://supabase.com) → New project
2. Choose a name and region close to you
3. Save your database password

**Run the database migration:**

In Supabase → **SQL Editor**, paste and run:

```sql
-- API keys table
CREATE TABLE public.api_keys (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    key_hash    TEXT        NOT NULL,
    key_prefix  TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at  TIMESTAMPTZ NULL
);
CREATE INDEX idx_api_keys_prefix ON public.api_keys (key_prefix);
CREATE INDEX idx_api_keys_user   ON public.api_keys (user_id);

-- Usage logs table
CREATE TABLE public.usage_logs (
    id                UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID          NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    model             TEXT          NOT NULL,
    prompt_tokens     INTEGER       NOT NULL,
    completion_tokens INTEGER       NOT NULL,
    cost_usd          NUMERIC(10,8) NOT NULL,
    created_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_usage_logs_user_date ON public.usage_logs (user_id, created_at DESC);

-- Row Level Security
ALTER TABLE public.api_keys   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.usage_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own keys"   ON public.api_keys FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can create own keys" ON public.api_keys FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can revoke own keys" ON public.api_keys FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
REVOKE UPDATE ON public.api_keys FROM authenticated;
GRANT UPDATE (revoked_at) ON public.api_keys TO authenticated;

CREATE POLICY "Users can view own usage" ON public.usage_logs FOR SELECT USING (auth.uid() = user_id);
```

**Configure auth:**

- Supabase → **Authentication → URL Configuration**
- Set **Site URL** to your Vercel URL (e.g. `https://opentaion.vercel.app`)
- Add the same URL to **Redirect URLs**

**Collect credentials:**

From **Project Settings → API**:

| Variable | Where to find it |
|----------|-----------------|
| `VITE_SUPABASE_URL` | Project URL |
| `VITE_SUPABASE_ANON_KEY` | anon / public key |
| `SUPABASE_JWT_PUBLIC_KEY` | Project Settings → API → JWT signing keys → Public Key (JSON Web Key format) |

From **Project Settings → Database → Connection string → Transaction pooler**:

| Variable | Where to find it |
|----------|-----------------|
| `DATABASE_URL` | Transaction pooler URI — change `postgresql://` to `postgresql+asyncpg://` |

> The transaction pooler uses port **6543**. Make sure you copy this URL, not the direct connection (port 5432).

---

### 4.2 OpenRouter

OpenRouter provides access to free LLMs with a single API key.

1. Go to [openrouter.ai](https://openrouter.ai) → Sign up
2. **Keys → Create Key**
3. Copy the key — this is your `OPENROUTER_API_KEY`

No credit card required. Free models include nvidia/nemotron, DeepSeek R1, Llama 3.3, and Qwen 2.5.

---

### 4.3 Railway (API)

Railway hosts the FastAPI backend.

**Deploy:**

1. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
2. Select your `opentaion` repo
3. Set **Root Directory** to `api`
4. Railway auto-detects `railway.toml` and deploys

**Set environment variables** (Railway → your service → Variables):

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres.xxx:PASSWORD@aws-X-REGION.pooler.supabase.com:6543/postgres` |
| `SUPABASE_JWT_PUBLIC_KEY` | Full JSON Web Key from Supabase (e.g. `{"kty":"EC","alg":"ES256",...}`) |
| `OPENROUTER_API_KEY` | `sk-or-...` |
| `CORS_ORIGINS` | `https://your-app.vercel.app` |

**Verify:**

```bash
curl https://your-api.up.railway.app/health
# Expected: {"status":"ok"}
```

**Optional model overrides:**

```
OPENROUTER_EFFORT_MODEL_LOW    = nvidia/nemotron-3-super-120b-a12b:free
OPENROUTER_EFFORT_MODEL_MEDIUM = nvidia/nemotron-3-super-120b-a12b:free
OPENROUTER_EFFORT_MODEL_HIGH   = nvidia/nemotron-3-super-120b-a12b:free
```

---

### 4.4 Vercel (Web)

Vercel hosts the React web dashboard.

**Deploy:**

1. Go to [vercel.com](https://vercel.com) → New Project → Import your `opentaion` repo
2. Set **Root Directory** to `web`
3. Framework is auto-detected as Vite

**Set environment variables** (Vercel → your project → Settings → Environment Variables):

| Variable | Value |
|----------|-------|
| `VITE_SUPABASE_URL` | `https://xxx.supabase.co` |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon public key |
| `VITE_API_BASE_URL` | `https://your-api.up.railway.app` |

**After deploying:**

- Go back to Supabase → Authentication → URL Configuration
- Update **Site URL** and **Redirect URLs** to your Vercel URL

---

### 4.5 Environment Variables Reference

#### API (Railway)

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | Supabase PostgreSQL connection string (asyncpg format, port 6543) |
| `SUPABASE_JWT_PUBLIC_KEY` | Yes | EC public key in JWK JSON format for JWT verification |
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key for LLM access |
| `CORS_ORIGINS` | Yes | Comma-separated list of allowed origins (your Vercel URL) |
| `OPENROUTER_EFFORT_MODEL_LOW` | No | Override the low-tier model (default: nvidia/nemotron free) |
| `OPENROUTER_EFFORT_MODEL_MEDIUM` | No | Override the medium-tier model |
| `OPENROUTER_EFFORT_MODEL_HIGH` | No | Override the high-tier model |

#### Web (Vercel)

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_SUPABASE_URL` | Yes | Your Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Yes | Supabase anon public key |
| `VITE_API_BASE_URL` | Yes | Railway API URL |

---

## 5. Troubleshooting

### Magic link redirects to wrong URL

**Symptom:** Clicking the magic link opens localhost instead of your Vercel app.

**Fix:** Supabase → Authentication → URL Configuration → update **Site URL** and **Redirect URLs** to your Vercel URL. Then request a new magic link (each link is single-use).

### 401 Unauthorized when generating API key

**Symptom:** `POST /api/keys` returns 401 after logging in.

**Fix:** Check that `SUPABASE_JWT_PUBLIC_KEY` in Railway matches the **JWT signing keys → Public Key (JSON Web Key format)** in Supabase → Project Settings → API. Paste the entire JSON object as the value.

### 503 Service Unavailable from the API

**Symptom:** Requests to `/v1/chat/completions` return 503.

**Causes and fixes:**

| Cause | Fix |
|-------|-----|
| `DATABASE_URL` wrong format | Must start with `postgresql+asyncpg://`, use port 6543 (transaction pooler), correct region prefix |
| Model rate-limited | Switch to a different free model on OpenRouter |
| Railway app not deployed | Check Railway deploy logs for startup errors |

### "Proxy unreachable" from the CLI

**Symptom:** `opentaion effort` prints `✗ Proxy unreachable`.

**Fix:** Run `opentaion login` and verify the proxy URL is your Railway URL (e.g. `https://opentaion-production.up.railway.app`). Test it with:

```bash
curl https://your-api.up.railway.app/health
```

If health returns `{"status":"ok"}` but effort still fails, the issue is with the LLM model being rate-limited. Try a different model.

### Database connection error (Tenant or user not found)

**Symptom:** Railway logs show `Tenant or user not found`.

**Fix:** The `DATABASE_URL` host is wrong. Copy the exact transaction pooler URL from Supabase → Project Settings → Database → Connection string. Do not change the region prefix (e.g. `aws-1-` is correct for some projects).

### DuplicatePreparedStatementError

**Symptom:** Requests fail with `prepared statement already exists`.

**Fix:** The `statement_cache_size=0` setting must be present in `database.py`. This is required for PgBouncer transaction mode (which Supabase uses). It is already set in the current codebase.
