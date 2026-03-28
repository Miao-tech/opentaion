# tests/test_providers.py
import pytest
from opentaion_api.services.providers import load_providers, resolve_provider


# ── load_providers ─────────────────────────────────────────────────────────────

def test_load_providers_single_provider(monkeypatch):
    monkeypatch.setenv("PROVIDER_SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    monkeypatch.setenv("PROVIDER_SILICONFLOW_API_KEY", "sf-key-123")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    providers = load_providers()
    assert "siliconflow" in providers
    assert providers["siliconflow"]["base_url"] == "https://api.siliconflow.cn/v1"
    assert providers["siliconflow"]["api_key"] == "sf-key-123"


def test_load_providers_strips_trailing_slash(monkeypatch):
    monkeypatch.setenv("PROVIDER_SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1/")
    monkeypatch.setenv("PROVIDER_SILICONFLOW_API_KEY", "sf-key-123")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    providers = load_providers()
    assert providers["siliconflow"]["base_url"] == "https://api.siliconflow.cn/v1"


def test_load_providers_multiple_providers(monkeypatch):
    monkeypatch.setenv("PROVIDER_SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    monkeypatch.setenv("PROVIDER_SILICONFLOW_API_KEY", "sf-key")
    monkeypatch.setenv("PROVIDER_GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai")
    monkeypatch.setenv("PROVIDER_GEMINI_API_KEY", "AIza-key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    providers = load_providers()
    assert "siliconflow" in providers
    assert "gemini" in providers


def test_load_providers_excludes_provider_without_api_key(monkeypatch):
    monkeypatch.setenv("PROVIDER_SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    monkeypatch.delenv("PROVIDER_SILICONFLOW_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    providers = load_providers()
    assert "siliconflow" not in providers


def test_load_providers_legacy_openrouter_fallback(monkeypatch):
    """OPENROUTER_API_KEY alone (no new-style vars) → openrouter provider created."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-legacy")
    monkeypatch.delenv("PROVIDER_OPENROUTER_BASE_URL", raising=False)
    monkeypatch.delenv("PROVIDER_OPENROUTER_API_KEY", raising=False)
    providers = load_providers()
    assert "openrouter" in providers
    assert providers["openrouter"]["base_url"] == "https://openrouter.ai/api/v1"
    assert providers["openrouter"]["api_key"] == "sk-or-legacy"


def test_load_providers_new_style_overrides_legacy(monkeypatch):
    """New-style PROVIDER_OPENROUTER_* takes precedence over OPENROUTER_API_KEY."""
    monkeypatch.setenv("PROVIDER_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("PROVIDER_OPENROUTER_API_KEY", "sk-or-new")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-legacy")
    providers = load_providers()
    assert providers["openrouter"]["api_key"] == "sk-or-new"


def test_load_providers_empty_when_no_config(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    # Remove any PROVIDER_* vars that might be set in test environment
    for key in list(__import__("os").environ.keys()):
        if key.startswith("PROVIDER_"):
            monkeypatch.delenv(key, raising=False)
    providers = load_providers()
    assert providers == {}


# ── resolve_provider ───────────────────────────────────────────────────────────

PROVIDERS = {
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "api_key": "or-key"},
    "siliconflow": {"base_url": "https://api.siliconflow.cn/v1", "api_key": "sf-key"},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "api_key": "gemini-key"},
}


def test_resolve_provider_matching_prefix_routes_to_provider():
    base_url, api_key, model = resolve_provider("siliconflow/Qwen/Qwen2.5-72B", PROVIDERS, "openrouter")
    assert base_url == "https://api.siliconflow.cn/v1"
    assert api_key == "sf-key"


def test_resolve_provider_strips_prefix_from_model():
    _, _, model = resolve_provider("siliconflow/Qwen/Qwen2.5-72B", PROVIDERS, "openrouter")
    assert model == "Qwen/Qwen2.5-72B"


def test_resolve_provider_gemini_prefix():
    base_url, api_key, model = resolve_provider("gemini/gemini-2.0-flash", PROVIDERS, "openrouter")
    assert base_url == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert model == "gemini-2.0-flash"


def test_resolve_provider_no_prefix_uses_default():
    base_url, api_key, model = resolve_provider("nvidia/nemotron-3-super-120b-a12b:free", PROVIDERS, "openrouter")
    assert base_url == "https://openrouter.ai/api/v1"
    assert api_key == "or-key"


def test_resolve_provider_no_prefix_model_unchanged():
    _, _, model = resolve_provider("nvidia/nemotron-3-super-120b-a12b:free", PROVIDERS, "openrouter")
    assert model == "nvidia/nemotron-3-super-120b-a12b:free"


def test_resolve_provider_unknown_prefix_falls_back_to_default():
    """'unknown/model' — 'unknown' is not a configured provider → use default."""
    base_url, api_key, model = resolve_provider("unknown/some-model", PROVIDERS, "openrouter")
    assert base_url == "https://openrouter.ai/api/v1"
    assert model == "unknown/some-model"


def test_resolve_provider_prefix_case_insensitive():
    base_url, _, _ = resolve_provider("SiliconFlow/Qwen/Qwen2.5-72B", PROVIDERS, "openrouter")
    assert base_url == "https://api.siliconflow.cn/v1"


def test_resolve_provider_missing_default_returns_empty_strings():
    _, api_key, _ = resolve_provider("some-model", {}, "openrouter")
    assert api_key == ""
