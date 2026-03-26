# tests/test_effort.py
import json
import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from click.testing import CliRunner

from opentaion.__main__ import main
import opentaion.core.config as config_module


# ── Test fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    """Write a fake config to a temp path and redirect CONFIG_PATH."""
    config_file = tmp_path / ".opentaion" / "config.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps({
        "proxy_url": "https://fake-proxy.railway.app",
        "api_key": "ot_testkey123456",
        "user_email": "",
    }))
    monkeypatch.setattr(config_module, "CONFIG_PATH", config_file)
    return config_file


def make_proxy_response(
    tool_calls: list | None = None,
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    model: str = "deepseek/deepseek-r1:free",
) -> dict:
    """Build a fake OpenRouter-style response."""
    message: dict = {"role": "assistant", "content": None}
    if tool_calls:
        message["tool_calls"] = tool_calls
    else:
        message["content"] = "Task complete."
    return {
        "choices": [{"message": message}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
        "model": model,
    }


def make_tool_call(name: str, args: dict, call_id: str = "call_001") -> dict:
    """Build a fake tool_call object."""
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(args),
        },
    }


def mock_httpx_responses(responses: list[dict]):
    """Create an httpx AsyncClient mock that returns responses in sequence."""
    mock_responses = []
    for data in responses:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value=data)
        mock_resp.raise_for_status = MagicMock()
        mock_responses.append(mock_resp)

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=mock_responses)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


# ── Tier → model mapping ───────────────────────────────────────────────────────

def test_effort_models_low():
    from opentaion.commands.effort import EFFORT_MODELS
    assert EFFORT_MODELS["low"] == "deepseek/deepseek-r1:free"


def test_effort_models_medium():
    from opentaion.commands.effort import EFFORT_MODELS
    assert EFFORT_MODELS["medium"] == "meta-llama/llama-3.3-70b-instruct:free"


def test_effort_models_high():
    from opentaion.commands.effort import EFFORT_MODELS
    assert EFFORT_MODELS["high"] == "qwen/qwen-2.5-72b-instruct:free"


# ── Single-iteration task (no tool calls) ─────────────────────────────────────

def test_effort_single_iteration_exits_0(tmp_config):
    mock_client = mock_httpx_responses([
        make_proxy_response(tool_calls=None, prompt_tokens=100, completion_tokens=50),
    ])
    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner()
        result = runner.invoke(main, ["effort", "low", "hello world"])
    assert result.exit_code == 0, result.output


def test_effort_single_iteration_prints_cost_summary(tmp_config):
    mock_client = mock_httpx_responses([
        make_proxy_response(tool_calls=None, prompt_tokens=100, completion_tokens=50),
    ])
    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner()
        result = runner.invoke(main, ["effort", "low", "hello world"])
    assert "✓ Task complete." in result.output
    assert "Tokens:" in result.output
    assert "Cost:" in result.output


def test_effort_single_iteration_token_count(tmp_config):
    """100 prompt + 50 completion = 150 total tokens."""
    mock_client = mock_httpx_responses([
        make_proxy_response(tool_calls=None, prompt_tokens=100, completion_tokens=50),
    ])
    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner()
        result = runner.invoke(main, ["effort", "low", "hello"])
    assert "150" in result.output  # 100 + 50


# ── Two-iteration task (one tool call) ────────────────────────────────────────

def test_effort_two_iterations_accumulates_tokens(tmp_config, tmp_path):
    """First iteration: read_file tool call. Second iteration: final answer."""
    test_file = tmp_path / "utils.py"
    test_file.write_text("def add(a, b): return a + b\n")

    responses = [
        make_proxy_response(
            tool_calls=[make_tool_call("read_file", {"path": str(test_file)})],
            prompt_tokens=200,
            completion_tokens=30,
        ),
        make_proxy_response(
            tool_calls=None,
            prompt_tokens=400,
            completion_tokens=80,
        ),
    ]
    mock_client = mock_httpx_responses(responses)
    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner()
        result = runner.invoke(main, ["effort", "low", "read utils.py"])
    assert result.exit_code == 0, result.output
    # Total: 200+400 prompt + 30+80 completion = 710 tokens
    assert "710" in result.output


def test_effort_two_iterations_prints_tool_bullet(tmp_config, tmp_path):
    test_file = tmp_path / "utils.py"
    test_file.write_text("def add(a, b): return a + b\n")

    responses = [
        make_proxy_response(
            tool_calls=[make_tool_call("read_file", {"path": str(test_file)})],
            prompt_tokens=100,
            completion_tokens=20,
        ),
        make_proxy_response(tool_calls=None, prompt_tokens=200, completion_tokens=30),
    ]
    mock_client = mock_httpx_responses(responses)
    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner()
        result = runner.invoke(main, ["effort", "low", "read utils.py"])
    assert "read_file" in result.output


# ── Max iterations safety limit ───────────────────────────────────────────────

def test_effort_max_iterations_shows_warning(tmp_config):
    """20 iterations all with tool_calls → safety limit message."""
    responses = [
        make_proxy_response(
            tool_calls=[make_tool_call("run_command", {"command": "echo hi"})],
            prompt_tokens=10,
            completion_tokens=5,
        )
    ] * 20  # 20 identical responses, all with tool_calls

    mock_client = mock_httpx_responses(responses)
    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner()
        result = runner.invoke(main, ["effort", "low", "loop forever"])
    assert "Max iterations reached" in result.output


def test_effort_max_iterations_still_shows_cost_summary(tmp_config):
    responses = [
        make_proxy_response(
            tool_calls=[make_tool_call("run_command", {"command": "echo hi"})],
            prompt_tokens=10,
            completion_tokens=5,
        )
    ] * 20

    mock_client = mock_httpx_responses(responses)
    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner()
        result = runner.invoke(main, ["effort", "low", "loop"])
    assert "✓ Task complete." in result.output
    # 20 × (10 + 5) = 300 total tokens
    assert "300" in result.output


# ── Default tier ───────────────────────────────────────────────────────────────

def test_effort_default_tier_is_low(tmp_config):
    """No tier specified → low tier → deepseek/deepseek-r1:free model."""
    captured_model = []

    async def fake_post(url, **kwargs):
        body = kwargs.get("json", {})
        captured_model.append(body.get("model"))
        mock_resp = MagicMock()
        mock_resp.json = MagicMock(return_value=make_proxy_response(tool_calls=None))
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=fake_post)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner()
        result = runner.invoke(main, ["effort", "fix the bug"])
    assert result.exit_code == 0, result.output
    assert captured_model == ["deepseek/deepseek-r1:free"]


# ── Missing config ─────────────────────────────────────────────────────────────

def test_effort_missing_config_exits_1(monkeypatch, tmp_path):
    missing_path = tmp_path / "nonexistent" / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_PATH", missing_path)

    runner = CliRunner()
    result = runner.invoke(main, ["effort", "low", "hello"])
    assert result.exit_code == 1


def test_effort_missing_config_mentions_login(monkeypatch, tmp_path):
    missing_path = tmp_path / "nonexistent" / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_PATH", missing_path)

    runner = CliRunner()
    result = runner.invoke(main, ["effort", "low", "hello"])
    assert result.exit_code == 1
    assert "login" in result.output.lower()


# ── Cost computation ──────────────────────────────────────────────────────────

def test_compute_cost_free_model():
    from opentaion.commands.effort import _compute_cost
    result = _compute_cost("deepseek/deepseek-r1:free", 1_000_000, 500_000)
    assert result == Decimal("0")


def test_compute_cost_unknown_model():
    from opentaion.commands.effort import _compute_cost
    result = _compute_cost("unknown/model", 1_000_000, 500_000)
    assert result == Decimal("0")


# ── Retry logic tests ─────────────────────────────────────────────────────────

def test_retry_first_call_success_on_retry(tmp_config):
    """First call raises ConnectError, retry succeeds → task completes normally."""
    call_count = [0]

    async def fake_post(url, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise httpx.ConnectError("Connection refused")
        # Second call succeeds
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=make_proxy_response(tool_calls=None))
        return mock_resp

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=fake_post)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner()
        result = runner.invoke(main, ["effort", "low", "hello"])

    assert result.exit_code == 0, result.output
    assert "✓ Task complete." in result.output
    assert call_count[0] == 2  # first attempt + one retry


def test_retry_first_call_no_output_on_first_failure(tmp_config):
    """First call fails silently — no error output on first attempt."""
    call_count = [0]

    async def fake_post(url, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise httpx.ConnectError("Connection refused")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=make_proxy_response(tool_calls=None))
        return mock_resp

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=fake_post)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner()
        result = runner.invoke(main, ["effort", "low", "hello"])

    # No "unreachable" error in output (success path)
    assert "unreachable" not in result.output.lower()


def test_both_first_call_attempts_fail_exits_1(tmp_config):
    """Both first-call attempts fail → exit code 1."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner()
        result = runner.invoke(main, ["effort", "low", "hello"])

    assert result.exit_code == 1


def test_both_first_call_attempts_fail_no_cost_summary(tmp_config):
    """On double failure, no cost summary is shown."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner()
        result = runner.invoke(main, ["effort", "low", "hello"])

    assert "✓ Task complete." not in result.output


def test_both_first_call_attempts_fail_exactly_two_calls(tmp_config):
    """Verify exactly 2 calls made (original + one retry), not more."""
    call_count = [0]

    async def counting_post(url, **kwargs):
        call_count[0] += 1
        raise httpx.ConnectError("Connection refused")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=counting_post)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner()
        runner.invoke(main, ["effort", "low", "hello"])

    assert call_count[0] == 2  # exactly original + one retry, not more


def test_mid_loop_connection_error_exits_1(tmp_config, tmp_path):
    """Connection error on iteration 1 (mid-loop) → exit 1, no retry."""
    test_file = tmp_path / "utils.py"
    test_file.write_text("def add(a, b): return a + b\n")

    call_count = [0]

    async def fake_post(url, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call succeeds (with tool call)
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json = MagicMock(return_value=make_proxy_response(
                tool_calls=[make_tool_call("read_file", {"path": str(test_file)})],
            ))
            return mock_resp
        # Second call (iteration 1) fails — mid-loop
        raise httpx.ConnectError("Connection dropped")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=fake_post)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner()
        result = runner.invoke(main, ["effort", "low", "read utils.py"])

    assert result.exit_code == 1


def test_mid_loop_connection_error_no_retry(tmp_config, tmp_path):
    """Mid-loop failure: exactly 2 calls total (iteration 0 success + iteration 1 fail, no retry)."""
    test_file = tmp_path / "utils.py"
    test_file.write_text("def add(a, b): return a + b\n")

    call_count = [0]

    async def fake_post(url, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json = MagicMock(return_value=make_proxy_response(
                tool_calls=[make_tool_call("read_file", {"path": str(test_file)})],
            ))
            return mock_resp
        raise httpx.ConnectError("Connection dropped")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=fake_post)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner()
        runner.invoke(main, ["effort", "low", "read utils.py"])

    # 2 calls: iteration 0 (success) + iteration 1 (fail, no retry = only 1 attempt)
    assert call_count[0] == 2


def test_http_401_exits_1(tmp_config):
    """HTTP 401 response → exit 1, no retry."""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=mock_response,
        )
    )

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner()
        result = runner.invoke(main, ["effort", "low", "hello"])

    assert result.exit_code == 1


def test_http_401_no_retry(tmp_config):
    """HTTP 401: exactly 1 call (no retry on auth failures)."""
    call_count = [0]
    mock_response = MagicMock()
    mock_response.status_code = 401

    async def counting_post(url, **kwargs):
        call_count[0] += 1
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "401 Unauthorized",
                request=MagicMock(),
                response=mock_response,
            )
        )
        return mock_response

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=counting_post)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner()
        runner.invoke(main, ["effort", "low", "hello"])

    assert call_count[0] == 1  # no retry — only one attempt
