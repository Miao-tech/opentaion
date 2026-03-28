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
# Only paid models need entries here — any model ending in ":free" is handled
# automatically by compute_cost() without needing an explicit entry.
# Prices as of 2026-03-24. Source: https://openrouter.ai/models
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "deepseek/deepseek-r1": (0.55, 2.19),
}

# ── Effort tier → model mapping ───────────────────────────────────────────────
# These are the defaults. Override per-tier with env vars in Railway for
# experiments or pricing changes without modifying code.
EFFORT_MODELS: dict[str, str] = {
    "low":    os.environ.get("OPENROUTER_EFFORT_MODEL_LOW",    "nvidia/nemotron-3-super-120b-a12b:free"),
    "medium": os.environ.get("OPENROUTER_EFFORT_MODEL_MEDIUM", "nvidia/nemotron-3-super-120b-a12b:free"),
    "high":   os.environ.get("OPENROUTER_EFFORT_MODEL_HIGH",   "nvidia/nemotron-3-super-120b-a12b:free"),
}


def compute_cost(model: str, prompt_tokens: int, completion_tokens: int) -> Decimal:
    """Compute cost in USD from token counts and MODEL_PRICING.

    Resolution order:
    1. Any model ending in ":free" → $0 (covers all providers, including dated
       variants like "nvidia/nemotron-...-20230311:free")
    2. Exact match in MODEL_PRICING → compute from per-million-token prices
    3. Unknown model → $0 silently (cost data unavailable for external providers)

    Never accepts cost from external sources — all computation is local (NFR13).
    Uses Decimal arithmetic throughout — never float (avoids rounding errors).
    """
    if model.endswith(":free"):
        return Decimal("0")

    if model not in MODEL_PRICING:
        return Decimal("0")

    prompt_price, completion_price = MODEL_PRICING[model]
    return (
        Decimal(str(prompt_tokens)) / Decimal("1000000") * Decimal(str(prompt_price))
        + Decimal(str(completion_tokens)) / Decimal("1000000") * Decimal(str(completion_price))
    )
