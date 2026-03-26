# src/opentaion/core/config.py
import json
from pathlib import Path
from typing import TypedDict

CONFIG_PATH = Path.home() / ".opentaion" / "config.json"


class Config(TypedDict):
    proxy_url: str
    api_key: str
    user_email: str


def write_config(proxy_url: str, api_key: str) -> None:
    """Write credentials to ~/.opentaion/config.json, creating directories if needed."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    config: Config = {
        "proxy_url": proxy_url.rstrip("/"),  # strip trailing slash for consistent URL building
        "api_key": api_key,
        "user_email": "",  # placeholder — populated in a future version
    }
    CONFIG_PATH.write_text(json.dumps(config, indent=2))
    CONFIG_PATH.chmod(0o600)


def read_config() -> Config | None:
    """Read ~/.opentaion/config.json. Returns None if file does not exist."""
    if not CONFIG_PATH.exists():
        return None
    try:
        return json.loads(CONFIG_PATH.read_text())
    except json.JSONDecodeError:
        return None
