# Story 1.6: Deploy Web to Vercel and Set Up Homebrew Tap

Status: done

## Story

As a developer building OpenTalon,
I want the web SPA deployed to Vercel and the Homebrew tap repository created with a working formula,
So that the dashboard is publicly accessible and the CLI can be installed on macOS with a single Homebrew command.

## Acceptance Criteria

**AC1 — Web SPA is deployed and renders:**
Given the web is deployed to Vercel
When the Vercel URL is opened in a browser
Then the shell App renders without console errors and `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` are set as Vercel environment variables

**AC2 — CLI installs via Homebrew:**
Given a macOS machine with Homebrew
When `brew tap opentaion/tap` followed by `brew install opentaion` is run
Then the CLI installs successfully and `opentaion --version` prints the version string (e.g. `opentaion 0.1.0`)

**AC3 — Formula is valid:**
Given the Homebrew tap repository (`opentaion/homebrew-tap`) is created on GitHub
When `brew audit --tap opentaion/tap` is run
Then the formula passes without errors

## Tasks / Subtasks

### Part A — Vercel Deployment

- [x] Task 1: Build and verify locally before deploying (AC: 1)
  - [x] Run `npm run build` from `web/` — confirm exits 0 and `dist/` is created
  - [x] This is the same build Vercel will run remotely

- [x] Task 2: Deploy web to Vercel (AC: 1)
  - [x] Sign in to vercel.com (create free account if needed)
  - [x] New Project → Import from GitHub → select your repository
  - [x] Set **Root Directory** to `web` (see Dev Notes)
  - [x] Framework Preset will auto-detect as **Vite** — confirm it is selected
  - [x] Build command: `npm run build` (auto-detected)
  - [x] Output directory: `dist` (auto-detected)

- [x] Task 3: Configure Vercel environment variables (AC: 1)
  - [x] In Vercel project settings → Environment Variables:
  - [x] Add `VITE_SUPABASE_URL` = your Supabase project URL
  - [x] Add `VITE_SUPABASE_ANON_KEY` = your Supabase anon key
  - [x] Redeploy after adding env vars (first deploy may fail without them)

- [x] Task 4: Verify Vercel deployment (AC: 1)
  - [x] Open the `*.vercel.app` URL in a browser
  - [x] Confirm page loads without console errors (open DevTools → Console)
  - [x] Expected: renders "Login" text (unauthenticated state from `App.tsx` stub)

### Part B — Homebrew Tap

- [x] Task 5: Create a GitHub Release of the CLI (prerequisite for formula)
  - [x] Tag the release: `git tag v0.1.0 && git push origin v0.1.0`
  - [x] On GitHub: Releases → Create a new release from tag `v0.1.0`
  - [x] Build the CLI source distribution: `cd cli && uv build` → generates `cli/dist/opentaion-0.1.0.tar.gz`
  - [x] Upload `opentaion-0.1.0.tar.gz` as a release artifact
  - [x] Note the download URL (format: `https://github.com/USERNAME/REPO/releases/download/v0.1.0/opentaion-0.1.0.tar.gz`)
  - [x] Get the SHA256: `shasum -a 256 cli/dist/opentaion-0.1.0.tar.gz`

- [x] Task 6: Create the `homebrew-tap` GitHub repository (AC: 2, 3)
  - [x] Create a new GitHub repository named exactly `homebrew-tap` under your GitHub username/org
  - [x] The tap name follows the pattern: `USERNAME/homebrew-tap` → installed as `brew tap USERNAME/tap`
  - [x] Initialize with a README

- [x] Task 7: Generate Homebrew resource entries using `poet` (AC: 2, 3)
  - [x] Install `homebrew-pypi-poet`: `pip install homebrew-pypi-poet`
  - [x] Run: `poet opentaion` from a clean Python environment
  - [x] Copy the generated `resource` blocks (see Dev Notes for what this looks like)

- [x] Task 8: Write the Homebrew formula (AC: 2, 3)
  - [x] Create `Formula/opentaion.rb` in the `homebrew-tap` repository (see Dev Notes for exact content)
  - [x] Fill in `url`, `sha256`, and all `resource` blocks from Task 7
  - [x] Commit and push to `homebrew-tap`

- [x] Task 9: Test the formula locally (AC: 2, 3)
  - [x] `brew tap Miao-tech/tap`
  - [x] `brew install opentaion`
  - [x] Confirm: `opentaion --version` prints `opentaion 0.1.0`
  - [x] Run: `brew audit --tap Miao-tech/tap` — fix any reported issues

## Dev Notes

### Prerequisite: Stories 1.1 and 1.3 Must Be Complete

- Story 1.1 must be done: `cli/` must have `pyproject.toml` and `uv build` must work
- Story 1.3 must be done: `web/` must have `npm run build` working

### Part A: Vercel

#### Setting Root Directory in Vercel

The repository is a monorepo. Vercel needs to know to deploy from `web/`, not the repo root:

1. During import: **Root Directory** field → set to `web`
2. Alternatively: after deployment, go to Project Settings → General → Root Directory

If Root Directory is not set, Vercel will try to build from the repo root, find no `package.json`, and fail.

#### Vercel Auto-Detection for Vite

With Root Directory set to `web`, Vercel detects Vite automatically and uses:
- **Build Command:** `npm run build`
- **Output Directory:** `dist`
- **Install Command:** `npm install`

These are correct. Do not override them unless you see errors.

#### Environment Variables in Vercel

| Variable | Where to get it | When needed |
|---|---|---|
| `VITE_SUPABASE_URL` | Supabase → Settings → API → Project URL | Now (Story 1.6) |
| `VITE_SUPABASE_ANON_KEY` | Supabase → Settings → API → anon/public key | Now (Story 1.6) |
| `VITE_API_BASE_URL` | Your Railway API URL (e.g. `https://app.up.railway.app`) | Story 2.3+ (not needed yet) |

**Without** `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`, the Supabase client in `App.tsx` will be initialized with empty strings and the app will throw console errors. Add them before testing.

**`VITE_SUPABASE_ANON_KEY` is safe to expose.** Unlike the service role key (Railway only), the anon key is designed for browser use — it is public and has RLS restrictions enforced on it.

#### Vercel HTTPS

All `*.vercel.app` domains are HTTPS automatically. No app-level configuration needed.

#### What the Deployed App Should Look Like

The Story 1.3 `App.tsx` stub renders:
- `"Login"` text — when no Supabase session exists (expected for most visitors)
- `"Dashboard"` text — when a valid session is detected (unlikely without Story 2.3)

No component library, no styling yet. The raw text is correct — full UI comes in Stories 2.3, 2.4, 2.5.

---

### Part B: Homebrew Tap

#### How Homebrew Taps Work

A tap is a GitHub repository named `homebrew-*` that contains Homebrew formulas:

```
GitHub repo: USERNAME/homebrew-tap
                ↓
brew tap USERNAME/tap        ← adds the tap
brew install USERNAME/tap/opentaion  ← installs the formula
brew install opentaion       ← works if tap is added first
```

The formula file lives at `Formula/opentaion.rb` inside the `homebrew-tap` repo.

#### Building the CLI Release Artifact

`uv build` generates a standard Python source distribution (sdist) and wheel:

```bash
cd cli
uv build
# Creates:
#   dist/opentaion-0.1.0.tar.gz   ← source distribution (use this in the formula)
#   dist/opentaion-0.1.0-py3-none-any.whl
```

Upload `opentaion-0.1.0.tar.gz` to the GitHub Release (not the wheel — the sdist is what Homebrew's `virtualenv_install_with_resources` expects).

Get the SHA256:
```bash
shasum -a 256 dist/opentaion-0.1.0.tar.gz
```

#### Using `homebrew-pypi-poet` to Generate Resource Entries

The Homebrew virtualenv approach requires listing every Python dependency (and their deps) as `resource` blocks. `poet` generates these automatically:

```bash
# Install poet in a temporary environment
pip install homebrew-pypi-poet

# Generate resource blocks for all opentaion dependencies
# Run this from a venv that has opentaion installed
cd cli && uv sync
uv run poet opentaion
```

`poet` outputs something like:
```ruby
resource "click" do
  url "https://files.pythonhosted.org/packages/.../click-8.1.8.tar.gz"
  sha256 "abcdef..."
end

resource "rich" do
  url "https://files.pythonhosted.org/packages/.../rich-13.9.0.tar.gz"
  sha256 "abcdef..."
end

resource "httpx" do
  ...
end

resource "python-dotenv" do
  ...
end

# ... plus all transitive dependencies (httpcore, h11, anyio, sniffio, certifi, etc.)
```

Copy ALL generated resource blocks into the formula.

**Note:** `poet` outputs resources for the installed versions from the lock file. These SHA256s are version-specific — you cannot reuse the blocks from another project. Always regenerate with `poet` for each release.

#### The Homebrew Formula

Create `Formula/opentaion.rb` in your `homebrew-tap` repository:

```ruby
# Formula/opentaion.rb
class Opentaion < Formula
  include Language::Python::Virtualenv

  desc "Agentic coding assistant CLI"
  homepage "https://github.com/USERNAME/opentaion"
  url "https://github.com/USERNAME/opentaion/releases/download/v0.1.0/opentaion-0.1.0.tar.gz"
  sha256 "REPLACE_WITH_ACTUAL_SHA256"
  license "MIT"

  depends_on "python@3.12"

  # ── Paste all resource blocks from `poet opentaion` here ───────────────────
  resource "click" do
    url "https://files.pythonhosted.org/packages/.../click-VERSION.tar.gz"
    sha256 "REPLACE"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/.../rich-VERSION.tar.gz"
    sha256 "REPLACE"
  end

  # ... all other resources from poet output ...
  # ───────────────────────────────────────────────────────────────────────────

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "opentaion 0.1.0", shell_output("#{bin}/opentaion --version")
  end
end
```

**Required substitutions:**
- `USERNAME` → your GitHub username or org
- `REPLACE_WITH_ACTUAL_SHA256` → SHA256 from `shasum -a 256 opentaion-0.1.0.tar.gz`
- All `resource` blocks → replace ENTIRELY with `poet opentaion` output

#### Running `brew audit`

After pushing the formula to `homebrew-tap`:

```bash
brew tap USERNAME/tap
brew audit --tap USERNAME/tap
```

Common `brew audit` issues and fixes:

| Issue | Fix |
|---|---|
| `description: begins with an article` | Remove "A" or "An" from `desc` |
| `formula: url is not at a stable URL` | Ensure URL is a tagged release, not a branch |
| `formula: homepage is not reachable` | Ensure the GitHub repo is public |
| `formula: no test block` | Add the `test do ... end` block |
| `resource "X": url not from a known host` | Use exact PyPI URL from `poet` output |

`brew audit --tap` is less strict than `brew audit` (which is for homebrew-core). Tap formulas don't need to meet the full homebrew-core standards.

#### Testing Locally Before Publishing

Before sharing with anyone else, test the full install flow on your own machine:

```bash
# Add the tap
brew tap USERNAME/tap

# Install (this takes a few minutes — builds a virtualenv)
brew install USERNAME/tap/opentaion

# Verify
opentaion --version
# Expected: opentaion 0.1.0

# Uninstall (for clean re-test)
brew uninstall opentaion
brew untap USERNAME/tap
```

If `brew install` fails with Python dependency errors, the most common cause is a mismatch between the resource SHA256 values and the actual PyPI package contents. Re-run `poet opentaion` and regenerate the resource blocks.

#### When `uv run poet opentaion` Doesn't Work

`poet` looks up packages on PyPI. If the package isn't published to PyPI (which it isn't at V1), run `poet` against the installed package in the uv virtualenv:

```bash
cd cli
uv sync
# poet needs the package installed in the active env:
uv run pip install homebrew-pypi-poet
uv run poet opentaion
```

Alternatively, generate resources from the `uv.lock` file by hand — each `[[package]]` entry with `sdist` source maps to a resource block.

### Architecture Cross-References

From `architecture.md`:
- Web hosting: Vercel, static SPA deployment [Source: architecture.md#Infrastructure Decisions]
- CLI distribution: Homebrew tap — `brew install opentaion/tap/opentaion` [Source: architecture.md#Infrastructure Decisions]
- macOS-only in V1 — no Windows, no Linux; Homebrew tap only [Source: architecture.md#Technical Constraints]
- HTTPS enforcement: Railway and Vercel handle TLS termination [Source: architecture.md#Implementation Patterns]
- Vercel env vars needed: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_BASE_URL` [Source: architecture.md#Environment Variables]

From `epics.md`:
- FR24: "Developer can install the CLI on macOS using a single Homebrew command" [Source: epics.md#FR24]
- NFR6: "All client-server communication must use HTTPS" — Vercel handles this [Source: epics.md#NFR6]

### What This Story Does NOT Include

Do NOT implement any of the following — they belong to later stories:

- Setting `VITE_API_BASE_URL` in Vercel — that env var is not consumed by the current `App.tsx` stub (Story 2.3+ adds actual API calls)
- Publishing the CLI to PyPI — Homebrew tap is the V1 distribution path
- A custom domain for Vercel or Railway — `*.vercel.app` and `*.up.railway.app` are sufficient for V1
- CI/CD workflows for automated Homebrew formula updates on release
- Linux/Windows distribution
- Automatic formula bumping scripts — manual process for V1

### This Completes Epic 1

After Story 1.6 is done, Epic 1 is complete:
- CLI: scaffolded and installable via Homebrew
- API: deployed to Railway with health check monitoring
- Web: deployed to Vercel with Supabase auth client initialized
- Database: schema in Supabase with RLS policies

Epic 2 (Developer Authentication & API Key Management) can begin — its first story (2.1) implements the real `verify_api_key()` and `verify_supabase_jwt()` auth dependencies.

### Final Modified/Created Files

```
cli/
└── dist/
    └── opentaion-0.1.0.tar.gz        # NEW — built by uv build, uploaded to GitHub Releases

homebrew-tap/ (separate GitHub repository)
└── Formula/
    └── opentaion.rb                   # NEW — Homebrew formula

(No changes to api/ or web/ code — this story is pure deployment)
```

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

_none_

### Completion Notes List

- Task 1: `npm run build` passes — 71 modules, 337KB JS bundle, exits 0.
- Task 2–4: Vercel deployed with Root Directory=web, Vite auto-detected. VITE_SUPABASE_ANON_KEY warning from Vercel is a false positive — anon key is safe for browser. After adding env vars and redeploying, page renders "Login" (unauthenticated state). AC1 satisfied.
- Task 5: `uv build` produced `opentaion-0.1.0.tar.gz` (SHA256: ba871cc948b27b1ad8d39c5dd1a336ff3b16440e6483704637e940d0b0bdbe4c). Uploaded to GitHub Release v0.1.0.
- Task 6: `Miao-tech/homebrew-tap` repo created on GitHub.
- Task 7: `homebrew-pypi-poet` could not run (missing `gsl-config` system dep on Linux). Resources generated manually from `uv.lock` — 19 runtime resource blocks (excludes dev deps: pytest, black, ruff, hypothesis).
- Task 8: `homebrew-tap/Formula/opentaion.rb` written with all 19 resource blocks. Formula uploaded to `Miao-tech/homebrew-tap`.
- Task 9: `brew install opentaion` succeeded. `opentaion --version` → "opentaion, version 0.1.0". `brew audit --tap Miao-tech/tap` passed with no formula errors. Required `depends_on "rust" => :build` because tiktoken has a Rust extension that must be compiled from source.

### File List

- `homebrew-tap/Formula/opentaion.rb` (NEW — in this repo for reference; live copy in Miao-tech/homebrew-tap)
- `cli/dist/opentaion-0.1.0.tar.gz` (NEW — uploaded to GitHub Release v0.1.0)
- `cli/dist/opentaion-0.1.0-py3-none-any.whl` (NEW)
