# tests/test_login.py
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from click.testing import CliRunner

from opentaion.__main__ import main
import opentaion.core.config as config_module


@pytest.fixture
def tmp_config_path(tmp_path, monkeypatch):
    """Redirect CONFIG_PATH to a temp directory for test isolation."""
    fake_path = tmp_path / ".opentaion" / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_PATH", fake_path)
    # Also patch the import in login.py (it imports CONFIG_PATH at module level)
    import opentaion.commands.login as login_module
    monkeypatch.setattr(login_module, "CONFIG_PATH", fake_path)
    return fake_path


def make_mock_client(raise_exc: Exception | None = None):
    """Build a mock httpx.AsyncClient for use as an async context manager."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    if raise_exc:
        mock_client.get = AsyncMock(side_effect=raise_exc)
    else:
        mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


# ── Success tests ─────────────────────────────────────────────────────────────

def test_login_success_writes_config(tmp_config_path):
    mock_client = make_mock_client()

    with patch("opentaion.commands.login.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["login"],
            input="https://myapp.up.railway.app\nmysecretapikey\n",
        )

    assert result.exception is None, result.output
    assert result.exit_code == 0, result.output
    assert tmp_config_path.exists()
    config = json.loads(tmp_config_path.read_text())
    assert config["proxy_url"] == "https://myapp.up.railway.app"
    assert config["api_key"] == "mysecretapikey"
    assert config["user_email"] == ""


def test_login_success_output_contains_confirmation(tmp_config_path):
    mock_client = make_mock_client()

    with patch("opentaion.commands.login.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["login"],
            input="https://myapp.up.railway.app\nmysecretapikey\n",
        )

    assert result.exception is None, result.output
    assert "✓" in result.output
    assert "https://myapp.up.railway.app" in result.output


def test_login_overwrites_existing_config(tmp_config_path):
    # Pre-create config with old values
    tmp_config_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_config_path.write_text(
        json.dumps({"proxy_url": "https://old.railway.app", "api_key": "oldkey", "user_email": ""})
    )

    mock_client = make_mock_client()

    with patch("opentaion.commands.login.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["login"],
            input="https://newapp.up.railway.app\nnewkey\n",
        )

    assert result.exception is None, result.output
    assert result.exit_code == 0
    config = json.loads(tmp_config_path.read_text())
    assert config["proxy_url"] == "https://newapp.up.railway.app"
    assert config["api_key"] == "newkey"


# ── Failure tests ─────────────────────────────────────────────────────────────

def test_login_unreachable_proxy_exits_1(tmp_config_path):
    mock_client = make_mock_client(raise_exc=httpx.ConnectError("Connection refused"))

    with patch("opentaion.commands.login.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["login"],
            input="https://unreachable.example.com\nmysecretapikey\n",
        )

    assert result.exit_code == 1
    assert "unreachable" in result.output.lower() or "unreachable" in (result.stderr or "").lower()


def test_login_unreachable_proxy_does_not_write_config(tmp_config_path):
    mock_client = make_mock_client(raise_exc=httpx.ConnectError("Connection refused"))

    with patch("opentaion.commands.login.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner()
        runner.invoke(
            main,
            ["login"],
            input="https://unreachable.example.com\nmysecretapikey\n",
        )

    assert not tmp_config_path.exists()
