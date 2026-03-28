# api/src/opentaion_api/services/providers.py
import os


def load_providers() -> dict[str, dict[str, str]]:
    """Load LLM provider configs from environment variables.

    Each provider requires two env vars:
        PROVIDER_{NAME}_BASE_URL  — the OpenAI-compatible base URL
        PROVIDER_{NAME}_API_KEY   — the API key for that provider

    Providers missing an API key are silently excluded.

    Backward compatibility: if PROVIDER_OPENROUTER_* vars are not set but
    OPENROUTER_API_KEY is present, an openrouter provider is created automatically
    so existing deployments continue to work without any configuration changes.

    Example env vars:
        PROVIDER_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
        PROVIDER_OPENROUTER_API_KEY=sk-or-...
        PROVIDER_SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
        PROVIDER_SILICONFLOW_API_KEY=sk-sf-...
        PROVIDER_GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
        PROVIDER_GEMINI_API_KEY=AIza...
    """
    providers: dict[str, dict[str, str]] = {}

    for key, value in os.environ.items():
        if not (key.startswith("PROVIDER_") and key.endswith("_BASE_URL")):
            continue
        name = key[len("PROVIDER_"):-len("_BASE_URL")].lower()
        api_key = os.environ.get(f"PROVIDER_{name.upper()}_API_KEY", "")
        if api_key:
            providers[name] = {
                "base_url": value.rstrip("/"),
                "api_key": api_key,
            }

    # Backward compatibility: OPENROUTER_API_KEY used by existing deployments
    if "openrouter" not in providers:
        legacy_key = os.environ.get("OPENROUTER_API_KEY", "")
        if legacy_key:
            providers["openrouter"] = {
                "base_url": "https://openrouter.ai/api/v1",
                "api_key": legacy_key,
            }

    return providers


def resolve_provider(
    model: str,
    providers: dict[str, dict[str, str]],
    default: str,
) -> tuple[str, str, str]:
    """Resolve which provider to use based on the model name.

    If the model starts with a known provider name followed by '/'
    (e.g. 'siliconflow/Qwen/Qwen2.5-72B'), routes to that provider
    and strips the prefix from the model name before forwarding.

    Otherwise falls back to the default provider with the model unchanged.

    Returns:
        (base_url, api_key, forwarded_model_name)
    """
    prefix, _, rest = model.partition("/")
    if rest and prefix.lower() in providers:
        p = providers[prefix.lower()]
        return p["base_url"], p["api_key"], rest

    p = providers.get(default.lower(), {})
    return p.get("base_url", ""), p.get("api_key", ""), model
