# Using OpenTalon with Opencode

[Opencode](https://opencode.ai) is an open-source, terminal-based AI coding agent (similar to Claude Code). This guide shows how to point it at your OpenTalon API so that all LLM calls are authenticated, proxied through your Railway backend, and logged in your OpenTalon dashboard.

## How it works

```
opencode  →  OpenTalon API (Railway)  →  OpenRouter  →  LLM (nvidia/nemotron, etc.)
                  ↓
           Usage logged to dashboard
```

Opencode sends standard OpenAI-compatible requests. Your OpenTalon API authenticates the `ot_` key, swaps in the OpenRouter key, forwards the request, and logs token usage — all transparently.

---

## Prerequisites

- Opencode installed (see below)
- An OpenTalon account — sign in at `https://opentaion.vercel.app`
- An OpenTalon API key (`ot_...`) — Dashboard → **API Keys** → **Generate Key**

---

## 1. Install opencode

```bash
# macOS / Linux via npm
npm install -g opencode-ai

# macOS via Homebrew (if available)
brew install opencode
```

Verify:

```bash
opencode --version
```

---

## 2. Set your API key

Add this to your shell profile (`~/.zshrc`, `~/.bashrc`, or `~/.profile`):

```bash
export OPENTAION_API_KEY=ot_...   # paste your key here
```

Then reload:

```bash
source ~/.zshrc   # or source ~/.bashrc
```

---

## 3. Create the opencode configuration

Opencode reads `opencode.json` from your project directory or from the global config path.

**Option A — Per-project** (recommended): create `opencode.json` in your project root.

**Option B — Global**: create `~/.config/opencode/opencode.json` (applies to all projects).

Paste this content:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "opentaion": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "OpenTalon",
      "options": {
        "baseURL": "https://opentaion-production.up.railway.app/v1",
        "apiKey": "{env:OPENTAION_API_KEY}"
      },
      "models": {
        "nvidia/nemotron-3-super-120b-a12b:free": {
          "name": "Nemotron 120B (free)",
          "limit": {
            "context": 128000,
            "output": 4096
          }
        }
      }
    }
  }
}
```

> **Note:** `{env:OPENTAION_API_KEY}` tells opencode to read the key from your shell environment — your key is never written to the config file.

---

## 4. Run opencode

```bash
cd your-project
opencode
```

When prompted to select a provider and model, choose:
- Provider: **OpenTalon**
- Model: **Nemotron 120B (free)**

You can now run coding tasks as normal:

```
> fix the type error in src/auth.py
> write tests for the login function
> explain what this regex does: ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$
```

---

## 5. Verify usage is being logged

After running a task, go to your OpenTalon dashboard:

1. Sign in at `https://opentaion.vercel.app`
2. Navigate to **Usage** in the sidebar
3. You should see the token usage from your opencode session in the bar chart and table

If the usage row shows `nvidia/nemotron-3-super-120b-a12b:free` with a cost of `$0.00`, everything is working correctly.

---

## Using a different model

OpenRouter provides access to many free models. To use a different one, add it to the `models` section of your config and update the model ID:

```json
"models": {
  "nvidia/nemotron-3-super-120b-a12b:free": {
    "name": "Nemotron 120B (free)",
    "limit": { "context": 128000, "output": 4096 }
  },
  "deepseek/deepseek-r1:free": {
    "name": "DeepSeek R1 (free)",
    "limit": { "context": 128000, "output": 8192 }
  },
  "meta-llama/llama-3.3-70b-instruct:free": {
    "name": "Llama 3.3 70B (free)",
    "limit": { "context": 128000, "output": 4096 }
  }
}
```

> **Which model to use?** If a model returns errors or slow responses, it is likely rate-limited on OpenRouter's free tier. Switch to another free model. `nvidia/nemotron-3-super-120b-a12b:free` has been the most reliable in testing.

---

## Troubleshooting

### 401 Unauthorized

Your `OPENTAION_API_KEY` is not set or is incorrect.

```bash
echo $OPENTAION_API_KEY   # should print your ot_... key
```

If empty, re-run `source ~/.zshrc` or open a new terminal.

### 502 / 503 from the API

The upstream model is rate-limited. Switch to a different free model in your config.

Verify the API is healthy:

```bash
curl https://opentaion-production.up.railway.app/health
# Expected: {"status":"ok"}
```

### No usage appearing in dashboard

Check the Railway logs for `[WARNING] write_usage_log failed`. This usually means a temporary database connection issue — the request still succeeds, only logging is affected.

### opencode can't find the provider

Make sure `opencode.json` is in the directory where you run `opencode`, or use the global config path `~/.config/opencode/opencode.json`.
