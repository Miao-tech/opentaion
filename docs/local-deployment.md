# Running OpenTalon Locally

This guide shows how to run the full OpenTalon stack on your own machine — no Railway, no Vercel, no cloud.

## Architecture (local)

```
Browser  →  http://localhost:5173  (Vite dev server — web)
CLI      →  http://localhost:8000  (uvicorn — API)
API      →  http://localhost:54322 (Supabase local — PostgreSQL)
Magic links → http://127.0.0.1:54324  (Mailpit — local email server)
```

## Why Docker is required

Supabase is not a single process — it is a stack of ~8 services (PostgreSQL, an auth server, an email trap, an API gateway, and more). The `supabase` CLI manages all of them together using **Docker Compose** under the hood. You never write any Docker commands yourself — `supabase start` and `supabase stop` are all you need — but Docker must be installed and running for those commands to work.

```
supabase start
    └── docker compose up   (Supabase manages this for you)
            ├── postgres    → port 54322  (database)
            ├── gotrue      → port 54321  (auth / magic links)
            ├── mailpit     → port 54324  (local email inbox)
            └── + 5 more internal services
```

## Prerequisites

| Tool | Install |
|------|---------|
| Docker | see below |
| Supabase CLI | see below |
| Python 3.12+ with uv | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js 20+ | https://nodejs.org or `sudo apt install nodejs npm` |
| An OpenRouter API key | https://openrouter.ai → Keys → Create Key |

### Install Docker (Ubuntu)

```bash
# Remove old versions if present
sudo apt remove docker docker-engine docker.io containerd runc 2>/dev/null

# Install Docker Engine
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Allow running Docker without sudo (log out and back in after this)
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker run hello-world
```

### Install Supabase CLI (Ubuntu ARM64)

Use the GitHub API to get the exact `.deb` download URL for the latest release:

```bash
# Fetch the exact download URL for linux_arm64.deb from the GitHub releases API
SUPABASE_DEB_URL=$(curl -s https://api.github.com/repos/supabase/cli/releases/latest \
  | grep "browser_download_url.*linux_arm64\.deb" \
  | cut -d'"' -f4)

# Download it
curl -Lo /tmp/supabase.deb "$SUPABASE_DEB_URL"

# Install
sudo dpkg -i /tmp/supabase.deb

# Verify
supabase --version
```

> **Note:** `npm install -g supabase` is not supported on Linux. Use the `.deb` package above, or run without installing via `npx supabase@latest`.

---

## Step 1 — Start Supabase locally

From the project root:

```bash
cd /path/to/opentaion

# First time only: initialise Supabase config
supabase init
```

After `supabase init`, edit `supabase/config.toml` to set the correct site URL for the Vite dev server. Find the `[auth]` section and change:

```toml
site_url = "http://localhost:5173"
additional_redirect_urls = ["http://localhost:5173"]
```

> The default is port `3000`, but Vite runs on port `5173`. Without this change, magic links redirect to the wrong port.

Then start Supabase:

```bash
supabase start
```

This takes ~2 minutes the first time (downloads Docker images). When done you'll see:

```
Started supabase local development setup.

  Development Tools
    Studio     http://127.0.0.1:54323
    Mailpit    http://127.0.0.1:54324   ← local email inbox (replaces Inbucket)

  APIs
    Project URL  http://127.0.0.1:54321

  Database
    URL  postgresql://postgres:postgres@127.0.0.1:54322/postgres

  Authentication Keys
    Publishable  sb_publishable_...     ← this is the anon key
    Secret       sb_secret_...          ← this is the service_role key
```

> **Note:** Newer versions of the Supabase CLI renamed the keys:
> `anon key` → **Publishable** and `service_role key` → **Secret**.

**Save these values** — you'll need the DB URL and the Publishable key.

---

## Step 2 — Get the local JWT public key

```bash
curl -s http://127.0.0.1:54321/auth/v1/.well-known/jwks.json
```

You'll get a JSON object like:
```json
{"keys":[{"kty":"EC","alg":"ES256","crv":"P-256","kid":"...","x":"...","y":"..."}]}
```

Copy the **first object inside `keys`** — just the `{...}` part, not the outer `{"keys":[...]}` wrapper. You'll use this as `SUPABASE_JWT_PUBLIC_KEY`.

---

## Step 3 — Run the database migration

```bash
cd /path/to/opentaion/api
uv run alembic upgrade head
```

Wait — this will fail because the default `DATABASE_URL` in `alembic.ini` points to the wrong place. First set the env var:

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:54322/postgres \
  uv run alembic upgrade head
```

Expected output:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 88a7cdb79508, create api keys and usage logs
```

---

## Step 4 — Configure the API

```bash
cd /path/to/opentaion/api
cp .env.example .env
```

Edit `.env`:

```env
LOCAL=true
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
SUPABASE_JWT_PUBLIC_KEY={"kty":"EC","alg":"ES256","crv":"P-256","kid":"...","x":"...","y":"..."}
OPENROUTER_API_KEY=sk-or-...
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

> Both `localhost` and `127.0.0.1` are listed in `CORS_ORIGINS` because browsers treat them as different origins. Vite may open on either depending on the OS.

Paste the full JWK object you got in Step 2 as the value of `SUPABASE_JWT_PUBLIC_KEY`.

---

## Step 5 — Start the API

```bash
cd /path/to/opentaion/api
uv run uvicorn opentaion_api.main:app --reload --port 8000
```

Verify it's running:

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok"}
```

---

## Step 6 — Configure the web dashboard

```bash
cd /path/to/opentaion/web
cp .env.local.example .env.local
```

Edit `.env.local`:

```env
VITE_SUPABASE_URL=http://127.0.0.1:54321
VITE_SUPABASE_ANON_KEY=sb_publishable_...   # Publishable key from `supabase start` output
VITE_API_BASE_URL=http://localhost:8000
```

---

## Step 7 — Start the web dashboard

```bash
cd /path/to/opentaion/web
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

---

## Step 8 — Sign in with a magic link (locally)

1. Go to http://localhost:5173
2. Enter any email address (e.g. `test@example.com`) — it does not need to be real
3. Click **Send magic link**
4. Open **Mailpit** at http://127.0.0.1:54324 — this is the local email server
5. Find the email in the inbox and click the magic link
6. You are now signed in

> Mailpit is a local email trap — all emails sent by Supabase Auth go here instead of a real inbox. Older Supabase versions called this "Inbucket".

---

## Step 9 — Generate an API key and test the CLI

1. Dashboard → **API Keys** → **Generate Key** → copy the `ot_...` key
2. Log in with the CLI:

```bash
cd /path/to/opentaion/cli
uv run python -m opentaion login
```

Enter:
- **Proxy URL**: `http://localhost:8000`
- **API Key**: the `ot_...` key you just generated

3. Run a task:

```bash
uv run python -m opentaion effort "list all Python files in the current directory"
```

---

## Running everything together

In production, three processes run in separate services. Locally, you run them in three separate terminal tabs:

| Terminal | Command | URL |
|----------|---------|-----|
| 1 | `supabase start` (one-time; stays running) | — |
| 2 | `cd api && uv run uvicorn opentaion_api.main:app --reload` | http://localhost:8000 |
| 3 | `cd web && npm run dev` | http://localhost:5173 |

---

## Stopping

```bash
# Stop Supabase (keeps data)
supabase stop

# Stop Supabase and wipe all local data (fresh start next time)
supabase stop --no-backup
```

---

## Troubleshooting

### `supabase start` fails

Make sure Docker Desktop is running. Supabase requires Docker.

### Alembic migration fails: `relation "auth.users" does not exist`

The `supabase start` must complete fully before running migrations. The `auth` schema is created by Supabase's GoTrue service. Wait for `supabase start` to print the full status output.

### Magic link does not appear in Mailpit

Check that `VITE_SUPABASE_URL` is `http://127.0.0.1:54321` (not your cloud Supabase URL). If it points to the cloud, emails go to your real inbox. Open Mailpit at http://127.0.0.1:54324.

### API returns 401 after signing in

The `SUPABASE_JWT_PUBLIC_KEY` in `api/.env` must come from the **local** Supabase instance (`http://127.0.0.1:54321/auth/v1/.well-known/jwks.json`), not from your cloud project. Local and cloud instances have different key pairs.

### CLI `effort` command fails with SSL error

Make sure `LOCAL=true` is set in `api/.env`. Without it, the API tries to require SSL on the local Postgres connection, which fails.

### Port conflicts

Default Supabase local ports: 54321 (API), 54322 (DB), 54323 (Studio), 54324 (Mailpit).
If any are in use, edit `supabase/config.toml` to change them.

### Docker permission denied (Ubuntu)

If you see `permission denied while trying to connect to the Docker daemon`:

```bash
sudo usermod -aG docker $USER
newgrp docker   # apply without logging out
```

### `supabase start` slow or image pull fails (ARM64)

Supabase maintains official ARM64 images. If a pull fails, make sure you're running Docker Engine 24+ and that `docker buildx` is available:

```bash
docker version        # should show 24+
docker buildx version # should be present
```

If images fail to pull, retry — Docker Hub rate limits can cause transient failures.
