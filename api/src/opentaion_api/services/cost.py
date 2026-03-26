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
