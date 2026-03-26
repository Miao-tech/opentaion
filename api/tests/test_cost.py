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


def test_compute_cost_zero_tokens_paid_model():
    from opentaion_api.services.cost import compute_cost
    result = compute_cost("deepseek/deepseek-r1", prompt_tokens=0, completion_tokens=0)
    assert result == Decimal("0")


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
    assert EFFORT_MODELS["low"] == "nvidia/nemotron-3-super-120b-a12b:free"


def test_effort_models_medium_default():
    from opentaion_api.services.cost import EFFORT_MODELS
    assert EFFORT_MODELS["medium"] == "nvidia/nemotron-3-super-120b-a12b:free"


def test_effort_models_high_default():
    from opentaion_api.services.cost import EFFORT_MODELS
    assert EFFORT_MODELS["high"] == "nvidia/nemotron-3-super-120b-a12b:free"


def test_effort_models_all_tiers_present():
    from opentaion_api.services.cost import EFFORT_MODELS
    assert set(EFFORT_MODELS.keys()) == {"low", "medium", "high"}


def test_effort_models_all_in_model_pricing():
    """Every model referenced by EFFORT_MODELS must exist in MODEL_PRICING."""
    cost_module = reload_cost_module()  # get clean snapshot, not a stale post-override reload
    EFFORT_MODELS = cost_module.EFFORT_MODELS
    MODEL_PRICING = cost_module.MODEL_PRICING
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
