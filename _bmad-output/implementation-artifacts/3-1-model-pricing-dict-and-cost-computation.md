# Story 3.1: Model Pricing Dict and Cost Computation

Status: done

## Story

As a developer building OpenTalon,
I want a `MODEL_PRICING` Python dict and `EFFORT_MODELS` mapping defined in `api/src/opentaion_api/services/cost.py`,
So that cost can be computed server-side from raw token counts at the moment of every usage log write, and the effort tier system has a single authoritative model routing table.

## Acceptance Criteria

**AC1 — Known model returns correct Decimal cost:**
Given an OpenRouter model ID present in `MODEL_PRICING`
When `compute_cost(model, prompt_tokens, completion_tokens)` is called
Then it returns a `decimal.Decimal` cost derived exclusively from `MODEL_PRICING` — no external API call, no float arithmetic (satisfies NFR13)

**AC2 — Free model returns exactly Decimal("0"):**
Given a `:free` model ID such as `"deepseek/deepseek-r1:free"` (cost `(0.0, 0.0)` per million tokens)
When `compute_cost()` is called with any token counts
Then it returns `Decimal("0")`

**AC3 — Unknown model returns Decimal("0") and logs a warning:**
Given a model ID not present in `MODEL_PRICING`
When `compute_cost()` is called
Then it returns `Decimal("0")` and prints a warning to stdout containing the unknown model ID (graceful degradation — usage record is still written at $0)

**AC4 — Effort tier mapping is correct:**
Given `EFFORT_MODELS` is imported from `services/cost.py`
When the mapping is inspected
Then:
- `EFFORT_MODELS["low"]` resolves to `"deepseek/deepseek-r1:free"` (or `OPENROUTER_EFFORT_MODEL_LOW` env var if set)
- `EFFORT_MODELS["medium"]` resolves to `"meta-llama/llama-3.3-70b-instruct:free"` (or `OPENROUTER_EFFORT_MODEL_MEDIUM` env var if set)
- `EFFORT_MODELS["high"]` resolves to `"qwen/qwen-2.5-72b-instruct:free"` (or `OPENROUTER_EFFORT_MODEL_HIGH` env var if set)

**AC5 — Tests pass:**
Given tests are run
When `uv run pytest` is executed from `api/`
Then unit tests pass for: known model cost calculation (paid model), free model returns $0, unknown model graceful fallback, all three tier-to-model mappings, env var override for effort tier

## Tasks / Subtasks

- [ ] Task 1: Write tests FIRST in `tests/test_cost.py` — confirm they fail (TDD)
  - [ ] Tests for AC1–AC5 all fail before `services/cost.py` exists
  - [ ] Cover: paid model calculation, free model = $0, unknown model = $0 + warning, all three tier mappings, env var override

- [ ] Task 2: Create `api/src/opentaion_api/services/__init__.py` (empty)

- [ ] Task 3: Create `api/src/opentaion_api/services/cost.py` (AC: 1–4)
  - [ ] `MODEL_PRICING` dict with all three free models + one paid model example
  - [ ] `EFFORT_MODELS` dict reading from env vars with defaults
  - [ ] `compute_cost()` using `decimal.Decimal` throughout — never float arithmetic

- [ ] Task 4: Run tests green (AC: 5)
  - [ ] `uv run pytest tests/test_cost.py -v`
  - [ ] `uv run pytest` — full suite passes (test_auth.py + test_keys.py + test_cost.py)

## Dev Notes

### No New Dependencies

`decimal` is part of the Python standard library. No `uv add` required. No changes to `api/pyproject.toml`.

### File Location — `services/cost.py`

```
api/src/opentaion_api/
├── services/
│   ├── __init__.py    ← NEW (empty)
│   └── cost.py        ← NEW — MODEL_PRICING, EFFORT_MODELS, compute_cost()
```

This location matches the architecture spec: `api/src/opentaion_api/services/cost.py`. Story 3.2 and 3.3 will import `compute_cost` and `EFFORT_MODELS` from this module.

### `services/cost.py` — Full Implementation

```python
# api/src/opentaion_api/services/cost.py
import os
from decimal import Decimal

# ── Model pricing table ────────────────────────────────────────────────────────
# Keyed by OpenRouter model ID.
# Values: (cost_per_million_prompt_tokens, cost_per_million_completion_tokens)
# All :free models are (0.0, 0.0). Updating pricing requires a redeploy only —
# never a DB migration (architecture decision: model_pricing as Python dict).
#
# Pricing source: https://openrouter.ai/models (verify before redeploy)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # Free tier models (no credit card required — all V1 default models)
    "deepseek/deepseek-r1:free":               (0.0, 0.0),
    "meta-llama/llama-3.3-70b-instruct:free":  (0.0, 0.0),
    "qwen/qwen-2.5-72b-instruct:free":         (0.0, 0.0),
    # Paid model example — used in tests and available for future tiers
    # Prices as of 2026-03-24: $0.55/M prompt, $2.19/M completion
    "deepseek/deepseek-r1":                    (0.55, 2.19),
}

# ── Effort tier → model mapping ───────────────────────────────────────────────
# These are the defaults. Override per-tier with env vars in Railway for
# experiments or pricing changes without modifying code.
EFFORT_MODELS: dict[str, str] = {
    "low":    os.environ.get("OPENROUTER_EFFORT_MODEL_LOW",    "deepseek/deepseek-r1:free"),
    "medium": os.environ.get("OPENROUTER_EFFORT_MODEL_MEDIUM", "meta-llama/llama-3.3-70b-instruct:free"),
    "high":   os.environ.get("OPENROUTER_EFFORT_MODEL_HIGH",   "qwen/qwen-2.5-72b-instruct:free"),
}


def compute_cost(model: str, prompt_tokens: int, completion_tokens: int) -> Decimal:
    """Compute cost in USD from token counts and MODEL_PRICING.

    Returns Decimal("0") for unknown models (graceful degradation).
    Never accepts cost from external sources — all computation is local (NFR13).
    Uses Decimal arithmetic throughout — never float (avoids rounding errors in cost_usd).
    """
    if model not in MODEL_PRICING:
        print(f"[WARNING] compute_cost: unknown model {model!r} — defaulting cost to 0")
        return Decimal("0")

    prompt_price, completion_price = MODEL_PRICING[model]
    cost = (
        Decimal(str(prompt_tokens)) / Decimal("1000000") * Decimal(str(prompt_price))
        + Decimal(str(completion_tokens)) / Decimal("1000000") * Decimal(str(completion_price))
    )
    return cost
```

### Why `Decimal(str(float_val))` — Not `Decimal(float_val)` Directly?

```python
>>> from decimal import Decimal
>>> Decimal(2.19)
Decimal('2.189999999999999991118215802998747587203979492187500')
>>> Decimal(str(2.19))
Decimal('2.19')
```

`Decimal(float_val)` captures the binary floating-point representation exactly — which is almost never what you want for monetary values. `Decimal(str(float_val))` parses the decimal string representation, which matches the literal value in the source code. Always use `Decimal(str(...))` when converting from float literals or variables.

### Why Python Dict, Not a DB Table?

From architecture.md:
> `model_pricing` is a Python dict, not a DB table. A DB table requires a migration every time OpenRouter adjusts pricing. A redeploy is sufficient at V1 scale. No ORM query in the request path.

The dict is the source of truth for:
1. **CLI terminal output** — Story 3.4 reads `usage.completion_tokens` from the proxy response and calls `compute_cost()` to display the task cost
2. **Usage log writes** — Story 3.3 calls `compute_cost()` inside the `BackgroundTask` to store `cost_usd`
3. **Dashboard cost table** — Story 4.1 aggregates `cost_usd` from the `usage_logs` table (already stored at write time — no recomputation needed)

### Why `EFFORT_MODELS` Is Constructed at Import Time (Not a Function)

`EFFORT_MODELS` reads `os.environ.get()` at module import, not inside a function. This means:
- In production: Railway env vars are read once at startup — correct behavior
- In tests: use `monkeypatch.setenv()` BEFORE importing `cost.py`, or reload the module after patching

The test fixture section below shows how to handle this in tests.

### Model ID Discrepancy: Epics vs Architecture

The epics.md Story 3.1 AC specifies `low → "deepseek/deepseek-r1"` (without `:free`). The architecture.md pricing dict example uses `"deepseek/deepseek-r1:free"`. These are **different models on OpenRouter**:
- `deepseek/deepseek-r1` — paid model (~$0.55/M prompt, ~$2.19/M completion)
- `deepseek/deepseek-r1:free` — free tier, rate-limited, no credit card required

**Resolution:** Use `"deepseek/deepseek-r1:free"` as the `low` tier default. This aligns with the architecture intent ("Readers do not need a credit card to follow along") and the CLAUDE.md constraint (OpenRouter free tier). The paid variant is included in `MODEL_PRICING` as a reference entry for paid-tier testing and future use.

### `compute_cost()` Error Path — Why `print()` Not `console.print()` or `logging`

The `cost.py` service module is shared API infrastructure — not CLI code. It uses `print()` for its warning because:
1. No dependency on the CLI's Rich `console` — services must not import from CLI packages
2. No `logging` setup exists in the API yet — adding it is a future story
3. FastAPI routes `print()` to stdout, which Railway captures and shows in deploy logs
4. The architecture spec explicitly says: "Background task failure must be logged to stdout, never propagated to the response" — the same stdout convention applies here

### Tests — `tests/test_cost.py`

Write BEFORE implementing `cost.py`. All tests fail initially (import error from missing module).

```python
# tests/test_cost.py
import os
from decimal import Decimal

import pytest


# ── Module reload helper for env var tests ─────────────────────────────────────
# EFFORT_MODELS is built at import time from os.environ. To test env var
# overrides, we must patch the env before the module loads, then reload it.

def reload_cost_module():
    """Force-reload cost module so EFFORT_MODELS re-reads current env."""
    import importlib
    import opentaion_api.services.cost as cost_module
    importlib.reload(cost_module)
    return cost_module


# ── compute_cost: free model ───────────────────────────────────────────────────

def test_compute_cost_free_model_r1():
    from opentaion_api.services.cost import compute_cost
    result = compute_cost("deepseek/deepseek-r1:free", prompt_tokens=1000, completion_tokens=500)
    assert result == Decimal("0")
    assert isinstance(result, Decimal)


def test_compute_cost_free_model_llama():
    from opentaion_api.services.cost import compute_cost
    result = compute_cost("meta-llama/llama-3.3-70b-instruct:free", prompt_tokens=100_000, completion_tokens=10_000)
    assert result == Decimal("0")


def test_compute_cost_free_model_qwen():
    from opentaion_api.services.cost import compute_cost
    result = compute_cost("qwen/qwen-2.5-72b-instruct:free", prompt_tokens=50_000, completion_tokens=25_000)
    assert result == Decimal("0")


# ── compute_cost: paid model ───────────────────────────────────────────────────

def test_compute_cost_paid_model_exact_million_tokens():
    """1M prompt + 1M completion of deepseek/deepseek-r1 = $0.55 + $2.19 = $2.74"""
    from opentaion_api.services.cost import compute_cost
    result = compute_cost("deepseek/deepseek-r1", prompt_tokens=1_000_000, completion_tokens=1_000_000)
    # 1_000_000 / 1_000_000 * 0.55 + 1_000_000 / 1_000_000 * 2.19 = 2.74
    assert result == Decimal("2.74")


def test_compute_cost_paid_model_partial_tokens():
    """500K prompt + 100K completion of deepseek/deepseek-r1"""
    from opentaion_api.services.cost import compute_cost
    result = compute_cost("deepseek/deepseek-r1", prompt_tokens=500_000, completion_tokens=100_000)
    # 500_000 / 1_000_000 * 0.55 + 100_000 / 1_000_000 * 2.19
    # = 0.275 + 0.219 = 0.494
    expected = Decimal("0.5") * Decimal("0.55") + Decimal("0.1") * Decimal("2.19")
    assert result == expected


def test_compute_cost_returns_decimal_not_float():
    from opentaion_api.services.cost import compute_cost
    result = compute_cost("deepseek/deepseek-r1", prompt_tokens=1000, completion_tokens=500)
    assert isinstance(result, Decimal)


# ── compute_cost: unknown model ────────────────────────────────────────────────

def test_compute_cost_unknown_model_returns_zero(capsys):
    from opentaion_api.services.cost import compute_cost
    result = compute_cost("unknown/model-xyz:free", prompt_tokens=1000, completion_tokens=500)
    assert result == Decimal("0")


def test_compute_cost_unknown_model_logs_warning(capsys):
    from opentaion_api.services.cost import compute_cost
    compute_cost("unknown/model-xyz:free", prompt_tokens=1000, completion_tokens=500)
    captured = capsys.readouterr()
    assert "unknown/model-xyz:free" in captured.out
    assert "WARNING" in captured.out


# ── EFFORT_MODELS: default mappings ───────────────────────────────────────────

def test_effort_models_low_default():
    from opentaion_api.services.cost import EFFORT_MODELS
    assert EFFORT_MODELS["low"] == "deepseek/deepseek-r1:free"


def test_effort_models_medium_default():
    from opentaion_api.services.cost import EFFORT_MODELS
    assert EFFORT_MODELS["medium"] == "meta-llama/llama-3.3-70b-instruct:free"


def test_effort_models_high_default():
    from opentaion_api.services.cost import EFFORT_MODELS
    assert EFFORT_MODELS["high"] == "qwen/qwen-2.5-72b-instruct:free"


def test_effort_models_all_tiers_present():
    from opentaion_api.services.cost import EFFORT_MODELS
    assert set(EFFORT_MODELS.keys()) == {"low", "medium", "high"}


def test_effort_models_all_in_model_pricing():
    """Every model referenced by EFFORT_MODELS must exist in MODEL_PRICING."""
    from opentaion_api.services.cost import EFFORT_MODELS, MODEL_PRICING
    for tier, model_id in EFFORT_MODELS.items():
        assert model_id in MODEL_PRICING, (
            f"EFFORT_MODELS[{tier!r}] = {model_id!r} not found in MODEL_PRICING"
        )


# ── EFFORT_MODELS: env var overrides ──────────────────────────────────────────

def test_effort_models_env_var_override_low(monkeypatch):
    monkeypatch.setenv("OPENROUTER_EFFORT_MODEL_LOW", "custom/model-low:free")
    cost_module = reload_cost_module()
    assert cost_module.EFFORT_MODELS["low"] == "custom/model-low:free"


def test_effort_models_env_var_override_medium(monkeypatch):
    monkeypatch.setenv("OPENROUTER_EFFORT_MODEL_MEDIUM", "custom/model-medium:free")
    cost_module = reload_cost_module()
    assert cost_module.EFFORT_MODELS["medium"] == "custom/model-medium:free"


def test_effort_models_env_var_override_high(monkeypatch):
    monkeypatch.setenv("OPENROUTER_EFFORT_MODEL_HIGH", "custom/model-high:free")
    cost_module = reload_cost_module()
    assert cost_module.EFFORT_MODELS["high"] == "custom/model-high:free"
```

### Test Notes

**`capsys` fixture (not `capfd`):** pytest's `capsys` captures `sys.stdout` / `sys.stderr` written via Python's `print()`. `capfd` captures at the file descriptor level and is needed for C extensions. Use `capsys` since `cost.py` uses `print()`.

**`importlib.reload()` for env var tests:** `EFFORT_MODELS` is module-level state built from `os.environ.get()` at import time. `monkeypatch.setenv()` updates the environment, but the module's `EFFORT_MODELS` dict is already constructed. Reload forces re-evaluation. Without reload, `monkeypatch.setenv()` has no effect on `EFFORT_MODELS`.

**No `conftest.py` changes needed:** All tests use standard pytest fixtures only. No async fixtures, no test DB, no app client — this story is pure unit tests.

**`capsys` ordering:** Call `capsys.readouterr()` AFTER the function call, not before. The fixture accumulates output; `readouterr()` drains and returns it.

### Architecture Cross-References

From `architecture.md`:
- `services/cost.py` — `MODEL_PRICING dict, compute_cost(model, tokens)` [Source: architecture.md#Project Structure]
- `model_pricing` is a Python dict (not DB table) — redeploy to update, no migration [Source: architecture.md#Core Architectural Decisions]
- `cost_usd` stored at write time from server-side dict — not recomputed on query [Source: architecture.md#Core Architectural Decisions]
- Use `EFFORT_MODELS` and `MODEL_PRICING` from `services/cost.py` as the single source of truth [Source: architecture.md#Coherence Validation]
- Store `cost_per_million_prompt_tokens` and `cost_per_million_completion_tokens` per model ID [Source: architecture.md#Gaps Resolved]
- All `:free` models default to `(0.0, 0.0)` [Source: architecture.md#Gaps Resolved]

From `epics.md`:
- FR18: "The system computes cost server-side from stored token counts using a model pricing table; cost is never accepted from the client" [Source: epics.md#FR18]
- NFR13: "Cost calculation must derive exclusively from token counts in the OpenRouter response metadata; cost must not depend on any external pricing API call in the request path" [Source: epics.md#NFR13]
- Additional Requirements: "`model_pricing` as Python dict: Pricing table is a hardcoded Python dict keyed by OpenRouter model ID. Updating pricing requires a redeploy, not a DB migration." [Source: epics.md#Additional Requirements]
- Additional Requirements: "`cost_usd` stored at write time: Computed from the `model_pricing` dict at the moment of the usage log write. Not recomputed on query." [Source: epics.md#Additional Requirements]

### What This Story Does NOT Include

- `POST /v1/chat/completions` proxy endpoint — that is Story 3.2
- `BackgroundTasks` usage log write — that is Story 3.3
- `opentaion /effort` CLI command — that is Story 3.4
- Any changes to `routers/`, `dependencies/`, or `models/` — pure service layer
- Any new `api/pyproject.toml` dependencies — `decimal` is stdlib

### Downstream Consumers of This Module

After this story is done, the following stories import from `services/cost.py`:

| Story | Import | Purpose |
|---|---|---|
| 3.2 | `from opentaion_api.services.cost import EFFORT_MODELS` | Map model ID to effort tier in proxy — NOT used in 3.2; the CLI sends model directly |
| 3.3 | `from opentaion_api.services.cost import compute_cost` | Compute `cost_usd` in background task |
| 3.4 (CLI) | n/a — CLI reads model from response, calls compute_cost via proxy response | CLI never imports from API services |
| 4.1 | None — `cost_usd` already stored in `usage_logs` at write time | No re-computation in query |

Note: `EFFORT_MODELS` is used by the **CLI** `effort` command to determine which model ID to include in the request body — but the CLI doesn't import from the API package. The CLI will define its own `EFFORT_MODELS`-equivalent mapping in Story 3.4. The `EFFORT_MODELS` dict in `services/cost.py` is authoritative for the **API** (e.g., for future server-side routing or validation).

### Final Modified/Created Files

```
api/
└── src/opentaion_api/
    └── services/
        ├── __init__.py    ← NEW (empty)
        └── cost.py        ← NEW — MODEL_PRICING, EFFORT_MODELS, compute_cost()
tests/
└── test_cost.py           ← NEW — unit tests for cost computation + tier mapping
```

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

_none_

### Completion Notes List

- TDD red phase: all 16 tests failed on missing module (import error) — confirmed before implementation
- `services/` directory and `__init__.py` created; `cost.py` implemented per spec
- All 16 cost tests pass; full suite (39 tests) passes

### File List

- `api/src/opentaion_api/services/__init__.py` — NEW (empty)
- `api/src/opentaion_api/services/cost.py` — NEW: MODEL_PRICING, EFFORT_MODELS, compute_cost()
- `api/tests/test_cost.py` — NEW: 16 unit tests
