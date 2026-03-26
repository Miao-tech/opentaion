# Story 3.4: CLI `/effort` Command — Multi-Turn Agent Loop with Tool Execution

Status: done

## Story

As a developer building OpenTalon,
I want the `opentaion effort [low|medium|high] "<prompt>"` command implemented as a true multi-turn agent loop with tool execution,
So that I can run agentic coding tasks that read and modify files across multiple LLM iterations and see the total accumulated cost immediately when the task completes.

## Acceptance Criteria

**AC1 — Command starts, prints model bullet, sends initial request:**
Given `~/.opentaion/config.json` exists with `proxy_url` and `api_key`
When `opentaion effort low "add docstrings to utils.py"` is run
Then the CLI prints `[dim]  ◆ Model: deepseek/deepseek-r1:free (low tier)[/dim]` and sends the initial user message to `<proxy_url>/v1/chat/completions` with `Authorization: Bearer <api_key>`, the mapped model ID, and the three tool definitions in the request body (satisfies FR6, FR7, UX-DR8)

**AC2 — Request body includes three tool definitions:**
Given the tool definitions are included in the request
When the request body is constructed
Then it includes at minimum three OpenRouter-compatible tool schemas:
- `read_file(path: str) → str` — reads and returns file contents
- `write_file(path: str, content: str) → str` — writes content to file, returns confirmation
- `run_command(command: str) → str` — executes a shell command, returns stdout + stderr (capped at 4000 chars)

**AC3 — Tool calls are executed and loop continues:**
Given the LLM response contains `tool_calls`
When the agent loop processes the response
Then for each tool call: the CLI prints `[dim]  ◆ {tool_name}({args_summary})[/dim]`, executes the tool locally, appends the `assistant` message (with tool_calls) and a `tool` result message to the messages list, and sends the updated messages list in the next proxy request — accumulating `prompt_tokens + completion_tokens` from each iteration's `usage` field

**AC4 — Natural termination when no tool_calls:**
Given the LLM response contains no `tool_calls` (the model returns a final text response)
When the loop detects termination
Then the loop exits cleanly — this is the normal completion path

**AC5 — Max iterations safety limit:**
Given the loop has run 20 iterations without terminating
When the 20th iteration completes
Then the loop is forcibly terminated with `[dim]  ◆ Max iterations reached. Stopping.[/dim]`

**AC6 — Cost summary reflects accumulated totals across all iterations:**
Given the loop terminates (either naturally or via max iterations)
When the cost summary is displayed
Then the terminal prints:
```
✓ Task complete.  Tokens: {total:,}  |  Cost: ${cost:.4f}
```
Where `total` and `cost` are the **sum across all loop iterations** — not a single call's values (satisfies FR8, UX-DR8)

**AC7 — Tier defaults to `low` when not specified:**
Given no tier argument is provided (e.g. `opentaion effort "fix the bug"`)
When the command runs
Then the `low` tier is used silently — no error, no warning

**AC8 — Missing config shows actionable error:**
Given `~/.opentaion/config.json` does not exist
When any `opentaion effort` command is run
Then the CLI prints an error directing the user to run `opentaion login` first and exits with code 1

**AC9 — Tests pass:**
Given tests are run
When `uv run pytest` is executed from `cli/`
Then tests pass for: correct model mapped per tier, single-iteration task completes correctly, two-iteration task with tool call executes and accumulates tokens, max iterations safety limit triggers, missing config error, cost summary reflects accumulated totals

## Tasks / Subtasks

- [x] Task 1: Write tests FIRST in `tests/test_effort.py` — confirm they fail (TDD)
  - [x] Tests for AC1–AC9 all fail before implementation

- [x] Task 2: Create `cli/src/opentaion/commands/effort.py` (AC: 1–8)
  - [x] `EFFORT_MODELS` dict (CLI-local copy of API's mapping)
  - [x] `CLI_MODEL_PRICING` dict and `_compute_cost()` for terminal display
  - [x] `TOOLS` list with three tool definitions (OpenRouter tool calling format)
  - [x] Tool execution functions: `_execute_read_file`, `_execute_write_file`, `_execute_run_command`
  - [x] `_run_agent_loop()` async function — multi-turn loop with token accumulation
  - [x] `effort` Click command with smart tier/prompt argument parsing

- [x] Task 3: Register `effort` command in `__main__.py` (AC: 1)
  - [x] `from opentaion.commands.effort import effort`
  - [x] `main.add_command(effort)`

- [x] Task 4: Run tests green (AC: 9)
  - [x] `uv run pytest tests/test_effort.py -v`
  - [x] `uv run pytest` — full suite passes

## Dev Notes

### Prerequisites: Story 2.6 Must Be Complete

- `src/opentaion/core/config.py` must exist with `read_config()` and `CONFIG_PATH`
- `src/opentaion/console.py` must exist with `console` and `err_console`
- `httpx` must be in `cli/pyproject.toml` (added in Story 2.6)

### Note on Existing `agent.py` and `llm.py`

The architecture doc marks `cli/src/opentaion/agent.py` and `llm.py` as existing (✅). These are legacy modules from before the proxy architecture was established. **Do NOT modify, delete, or integrate them in this story.** The `effort.py` command is self-contained. If `agent.py` and `llm.py` create naming conflicts or import errors, note them in the Dev Agent Record — but leave them untouched.

### Command Argument Parsing

The command supports:
- `opentaion effort low "prompt"` — explicit tier
- `opentaion effort medium "prompt"` — explicit tier
- `opentaion effort "prompt"` — implicit low tier
- `opentaion effort low add docstrings to utils.py` — multi-word prompt (no quotes)

Use `nargs=-1` to capture all trailing arguments:

```python
@click.command(name="effort")
@click.argument("args", nargs=-1, required=True)
def effort(args: tuple[str, ...]) -> None:
    """Run an agentic coding task via the OpenTalon proxy."""
    if args[0] in ("low", "medium", "high"):
        tier = args[0]
        prompt = " ".join(args[1:])
    else:
        tier = "low"
        prompt = " ".join(args)

    if not prompt:
        err_console.print("[bold red]✗ No prompt provided.[/bold red]")
        sys.exit(1)

    asyncio.run(_run_effort(tier, prompt))
```

### `commands/effort.py` — Full Implementation

```python
# cli/src/opentaion/commands/effort.py
import asyncio
import json
import subprocess
import sys
from decimal import Decimal

import httpx

from opentaion.console import console, err_console
from opentaion.core.config import read_config

import click

# ── Effort tier → model mapping ───────────────────────────────────────────────
# CLI-local copy of the API's EFFORT_MODELS dict (api/src/opentaion_api/services/cost.py).
# Must stay in sync with the API. Both use the :free variants.

EFFORT_MODELS: dict[str, str] = {
    "low":    "deepseek/deepseek-r1:free",
    "medium": "meta-llama/llama-3.3-70b-instruct:free",
    "high":   "qwen/qwen-2.5-72b-instruct:free",
}

# ── Client-side pricing for terminal display ──────────────────────────────────
# Used only for the cost summary line — the authoritative cost is stored by the API.
# All V1 models are :free (0.0 per million tokens), so displayed cost is always $0.

CLI_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "deepseek/deepseek-r1:free":               (0.0, 0.0),
    "meta-llama/llama-3.3-70b-instruct:free":  (0.0, 0.0),
    "qwen/qwen-2.5-72b-instruct:free":         (0.0, 0.0),
    "deepseek/deepseek-r1":                    (0.55, 2.19),
}


def _compute_cost(model: str, prompt_tokens: int, completion_tokens: int) -> Decimal:
    """Compute display cost from token counts. Returns Decimal("0") for unknown models."""
    if model not in CLI_MODEL_PRICING:
        return Decimal("0")
    prompt_price, completion_price = CLI_MODEL_PRICING[model]
    return (
        Decimal(str(prompt_tokens)) / Decimal("1000000") * Decimal(str(prompt_price))
        + Decimal(str(completion_tokens)) / Decimal("1000000") * Decimal(str(completion_price))
    )


# ── Tool definitions (OpenRouter / OpenAI tool calling format) ────────────────

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read and return the full contents of a file at the given path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative or absolute path to the file to read.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file, creating it or overwriting it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to write.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full content to write to the file.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command and return stdout + stderr (capped at 4000 characters).",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute.",
                    }
                },
                "required": ["command"],
            },
        },
    },
]

MAX_ITERATIONS = 20
PROXY_TIMEOUT = httpx.Timeout(connect=5.0, read=120.0)


# ── Tool execution ────────────────────────────────────────────────────────────

def _execute_read_file(path: str) -> str:
    """Read file at path. Returns contents or error message."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading {path}: {e}"


def _execute_write_file(path: str, content: str) -> str:
    """Write content to path. Returns confirmation or error message."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"✓ Written {len(content)} chars to {path}"
    except Exception as e:
        return f"Error writing {path}: {e}"


def _execute_run_command(command: str) -> str:
    """Run shell command, return stdout + stderr capped at 4000 chars."""
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = proc.stdout + proc.stderr
        if len(output) > 4000:
            output = output[:4000] + "\n[... output truncated at 4000 chars ...]"
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 30 seconds"
    except Exception as e:
        return f"Error running command: {e}"


def _execute_tool(name: str, args: dict) -> str:
    """Dispatch tool call by name. Returns string result."""
    if name == "read_file":
        return _execute_read_file(args.get("path", ""))
    elif name == "write_file":
        return _execute_write_file(args.get("path", ""), args.get("content", ""))
    elif name == "run_command":
        return _execute_run_command(args.get("command", ""))
    else:
        return f"Error: unknown tool '{name}'"


def _args_summary(args: dict) -> str:
    """One-line summary of tool args for progress bullet display."""
    parts = []
    for key, value in args.items():
        val_str = str(value)
        if len(val_str) > 40:
            val_str = val_str[:37] + "..."
        parts.append(f"{key}={val_str!r}")
    return ", ".join(parts)


# ── Agent loop ────────────────────────────────────────────────────────────────

async def _run_agent_loop(proxy_url: str, api_key: str, tier: str, prompt: str) -> None:
    """Multi-turn agent loop. Runs until LLM returns no tool_calls or MAX_ITERATIONS."""
    model = EFFORT_MODELS[tier]
    console.print(f"[dim]  ◆ Model: {model} ({tier} tier)[/dim]")

    messages: list[dict] = [{"role": "user", "content": prompt}]
    total_prompt_tokens = 0
    total_completion_tokens = 0

    async with httpx.AsyncClient(timeout=PROXY_TIMEOUT) as client:
        for iteration in range(MAX_ITERATIONS):
            # Send request to proxy
            response = await client.post(
                f"{proxy_url}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "tools": TOOLS,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()

            # Accumulate token counts
            usage = data.get("usage", {})
            total_prompt_tokens += int(usage.get("prompt_tokens", 0))
            total_completion_tokens += int(usage.get("completion_tokens", 0))

            # Extract the assistant's message
            choices = data.get("choices", [])
            if not choices:
                break
            message = choices[0].get("message", {})

            # Check for termination: no tool_calls = final answer
            tool_calls = message.get("tool_calls")
            if not tool_calls:
                break  # natural termination

            # Append assistant message (with tool_calls) to conversation
            messages.append(message)

            # Execute each tool call and collect results
            for tool_call in tool_calls:
                tool_name = tool_call["function"]["name"]
                try:
                    tool_args = json.loads(tool_call["function"]["arguments"])
                except (json.JSONDecodeError, KeyError):
                    tool_args = {}

                console.print(f"[dim]  ◆ {tool_name}({_args_summary(tool_args)})[/dim]")
                result = _execute_tool(tool_name, tool_args)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result,
                })
        else:
            # Loop exhausted without break — max iterations reached
            console.print("[dim]  ◆ Max iterations reached. Stopping.[/dim]")

    # Cost summary
    total_tokens = total_prompt_tokens + total_completion_tokens
    cost = _compute_cost(model, total_prompt_tokens, total_completion_tokens)
    console.print(
        f"[bold]✓ Task complete.[/bold]  "
        f"[dim]Tokens: {total_tokens:,}[/dim]  "
        f"[dim]|[/dim]  "
        f"[bold cyan]Cost: ${cost:.4f}[/bold cyan]"
    )


# ── Click command ─────────────────────────────────────────────────────────────

@click.command(name="effort")
@click.argument("args", nargs=-1, required=True)
def effort(args: tuple[str, ...]) -> None:
    """Run an agentic coding task via the OpenTalon proxy.

    Usage:
      opentaion effort low "add docstrings to utils.py"
      opentaion effort medium "refactor the auth module"
      opentaion effort "fix the bug"       (defaults to low tier)
    """
    # Parse tier + prompt from variadic args
    if args[0] in ("low", "medium", "high"):
        tier = args[0]
        prompt = " ".join(args[1:])
    else:
        tier = "low"
        prompt = " ".join(args)

    if not prompt:
        err_console.print("[bold red]✗ No prompt provided.[/bold red]")
        err_console.print("[dim]  Usage: opentaion effort [low|medium|high] \"<prompt>\"[/dim]")
        sys.exit(1)

    # Load config — fail with actionable error if missing
    config = read_config()
    if config is None:
        err_console.print("[bold red]✗ Not configured.[/bold red]")
        err_console.print("[dim]  Run [cyan]`opentaion login`[/cyan] to set your proxy URL and API key.[/dim]")
        sys.exit(1)

    asyncio.run(_run_agent_loop(config["proxy_url"], config["api_key"], tier, prompt))
```

### Updated `__main__.py`

```python
# cli/src/opentaion/__main__.py
import asyncio
import click
from opentaion import __version__
from opentaion.commands.login import login
from opentaion.commands.effort import effort


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="opentaion")
@click.pass_context
def main(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


main.add_command(login)
main.add_command(effort)


if __name__ == "__main__":
    asyncio.run(main())
```

### Tool Execution Design Decisions

**`run_command` uses `shell=True`**
This allows shell features (pipes, redirects, globs) that an agentic tool needs. The target audience is a developer using the tool on their own machine — `shell=True` is the correct choice for maximum utility. Security implication: the LLM can execute arbitrary commands. This is intentional — the whole value proposition is an agent that can run tests, check diffs, install packages, etc.

**`run_command` timeout: 30 seconds**
Covers most test runs and build commands. `subprocess.TimeoutExpired` returns a clean error string so the LLM can retry with a faster command or acknowledge the timeout.

**Output cap: 4000 chars**
Keeps tool results within model context limits. Long outputs (e.g., full file listings, verbose test output) are truncated with a clear marker. The LLM can request a more targeted command if it needs specific information from the truncated output.

**Tool functions return `str`, never raise**
Every tool execution is wrapped in `try/except Exception`. This ensures the agent loop never crashes due to a failed tool call — it returns an error string that the LLM can reason about and potentially retry.

### OpenRouter Tool Calling Format

OpenRouter uses the OpenAI tool calling format:

**Request:**
```json
{
  "model": "deepseek/deepseek-r1:free",
  "messages": [{"role": "user", "content": "add docstrings to utils.py"}],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "read_file",
        "description": "...",
        "parameters": {"type": "object", "properties": {...}, "required": [...]}
      }
    }
  ]
}
```

**Response (with tool_calls):**
```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": null,
      "tool_calls": [{
        "id": "call_abc123",
        "type": "function",
        "function": {
          "name": "read_file",
          "arguments": "{\"path\": \"utils.py\"}"
        }
      }]
    }
  }],
  "usage": {"prompt_tokens": 150, "completion_tokens": 30}
}
```

**Tool result appended to messages:**
```json
{
  "role": "tool",
  "tool_call_id": "call_abc123",
  "content": "def add(a, b):\n    return a + b\n"
}
```

Note: `arguments` is a **JSON string**, not a dict. Always use `json.loads(tool_call["function"]["arguments"])` to parse it.

### Token Accumulation

Tokens accumulate across ALL iterations:
```
Iteration 1: prompt_tokens=200, completion_tokens=30  → total so far: 230
Iteration 2: prompt_tokens=350, completion_tokens=45  → total so far: 625
Iteration 3: prompt_tokens=420, completion_tokens=80  → total so far: 1125
Final display: Tokens: 1,125  |  Cost: $0.0000
```

This is the total tokens consumed by the entire task, not just the last call.

### Why `httpx.AsyncClient` Created Once for the Loop

```python
async with httpx.AsyncClient(timeout=PROXY_TIMEOUT) as client:
    for iteration in range(MAX_ITERATIONS):
        response = await client.post(...)
```

Creating the client **outside** the iteration loop allows connection reuse (HTTP keep-alive) across iterations. Each loop iteration reuses the same underlying TCP connection to the proxy, reducing overhead per call. This matters for the 200ms proxy overhead NFR.

### Tests — `tests/test_effort.py`

```python
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
    import opentaion.commands.effort as effort_module
    # effort.py uses read_config() which imports CONFIG_PATH from config_module
    # Since read_config() re-reads the file each call, patching config_module is sufficient
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
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, ["effort", "low", "hello world"])
    assert result.exit_code == 0, result.output


def test_effort_single_iteration_prints_cost_summary(tmp_config):
    mock_client = mock_httpx_responses([
        make_proxy_response(tool_calls=None, prompt_tokens=100, completion_tokens=50),
    ])
    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner(mix_stderr=False)
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
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, ["effort", "low", "hello"])
    assert "150" in result.output  # 100 + 50


# ── Two-iteration task (one tool call) ────────────────────────────────────────

def test_effort_two_iterations_accumulates_tokens(tmp_config, tmp_path):
    """First iteration: read_file tool call. Second iteration: final answer."""
    # Create a temp file for read_file to read
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
        runner = CliRunner(mix_stderr=False)
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
        runner = CliRunner(mix_stderr=False)
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
        runner = CliRunner(mix_stderr=False)
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
        runner = CliRunner(mix_stderr=False)
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
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, ["effort", "fix the bug"])
    assert result.exit_code == 0, result.output
    assert captured_model == ["deepseek/deepseek-r1:free"]


# ── Missing config ─────────────────────────────────────────────────────────────

def test_effort_missing_config_exits_1(monkeypatch, tmp_path):
    missing_path = tmp_path / "nonexistent" / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_PATH", missing_path)

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(main, ["effort", "low", "hello"])
    assert result.exit_code == 1


def test_effort_missing_config_mentions_login(monkeypatch, tmp_path):
    missing_path = tmp_path / "nonexistent" / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_PATH", missing_path)

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(main, ["effort", "low", "hello"])
    # Error goes to stderr; with mix_stderr=False, check output (stdout only)
    # The error message is in stderr
    assert result.exit_code == 1


# ── Cost computation ──────────────────────────────────────────────────────────

def test_compute_cost_free_model():
    from opentaion.commands.effort import _compute_cost
    result = _compute_cost("deepseek/deepseek-r1:free", 1_000_000, 500_000)
    assert result == Decimal("0")


def test_compute_cost_unknown_model():
    from opentaion.commands.effort import _compute_cost
    result = _compute_cost("unknown/model", 1_000_000, 500_000)
    assert result == Decimal("0")
```

### Architecture Cross-References

From `architecture.md`:
- `commands/effort.py` — `opentaion /effort [low|medium|high] "<prompt>"` [Source: architecture.md#Project Structure]
- `EFFORT_MODELS` and `MODEL_PRICING` from `services/cost.py` as single source of truth (CLI mirrors these locally) [Source: architecture.md#Coherence Validation]
- `httpx.Timeout(connect=5.0, read=120.0)` — read 120s for reasoning models [Source: architecture.md#Gaps Resolved]
- CLI entry point: `asyncio.run()` in `__main__.py` only [Source: architecture.md#Implementation Patterns rule 8]
- All CLI output via Rich Console — never `print()` [Source: architecture.md#Implementation Patterns rule 3]
- Config at `~/.opentaion/config.json` [Source: architecture.md#CLI Python Package]
- `httpx.AsyncClient` created once per command invocation [Source: architecture.md#CLI Python Package]

From `epics.md`:
- FR6: "Developer can invoke an agentic coding task from the terminal using a natural language prompt" [Source: epics.md#FR6]
- FR7: "Developer can specify a model cost tier (low, medium, or high) per task" [Source: epics.md#FR7]
- FR8: "Developer can view total token count and computed cost for each completed task" [Source: epics.md#FR8]
- UX-DR8: `CostSummaryLine` and `ProgressBullet` output formats [Source: epics.md#UX-DR8]

### What This Story Does NOT Include

- Retry logic on connection failures — that is Story 3.5
- The `httpx.ConnectError` / HTTP 401 error handling with specific messages — Story 3.5 wraps this
- Story 3.5 will modify `_run_agent_loop()` to add retry on the first call only
- Streaming responses — V1 is non-streaming; no SSE handling
- The `agent.py` / `llm.py` refactor — those are legacy files; leave untouched
- `opentaion login` retry — only `effort` has the retry requirement (Story 3.5)

### Final Modified/Created Files

```
cli/
├── src/opentaion/
│   ├── __main__.py              ← MODIFIED — add effort command
│   └── commands/
│       └── effort.py            ← NEW — full effort command + agent loop + tools
└── tests/
    └── test_effort.py           ← NEW — effort command tests
```

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Story spec uses `CliRunner(mix_stderr=False)` but Click 8.3.1 doesn't support `mix_stderr` param — used `CliRunner()` throughout (consistent with test_login.py)
- `test_effort_missing_config_mentions_login` checks `result.output` (stdout) not stderr — `err_console` writes to stderr which CliRunner merges with stdout in default mode

### Completion Notes List

- TDD red: all 15 tests failed (import error from missing module)
- `commands/effort.py` created with full agent loop, tool dispatch, token accumulation
- `__main__.py` updated to register effort command
- 15/15 effort tests pass; 47/47 full suite passes

### File List

- `cli/src/opentaion/commands/effort.py` — NEW: effort command + agent loop + tools
- `cli/src/opentaion/__main__.py` — MODIFIED: added effort command registration
- `cli/tests/test_effort.py` — NEW: 15 tests for effort command
