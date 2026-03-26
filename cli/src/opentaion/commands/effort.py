# cli/src/opentaion/commands/effort.py
import asyncio
import json
import subprocess
import sys
from decimal import Decimal

import click
import httpx

from opentaion.console import console, err_console
from opentaion.core.config import read_config

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
PROXY_TIMEOUT = httpx.Timeout(connect=5.0, read=120.0, write=5.0, pool=5.0)


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


# ── Error display helpers ─────────────────────────────────────────────────────

def _show_proxy_error(proxy_url: str) -> None:
    """Print the proxy unreachable error to stderr (UX-DR8 ErrorLine format)."""
    err_console.print(f"[bold red]✗ Proxy unreachable: {proxy_url}[/bold red]")
    err_console.print("[dim]  Could not connect to the OpenTalon API server.[/dim]")
    err_console.print("[dim]  Check that your Railway deployment is running.[/dim]")
    err_console.print("")
    err_console.print("  Run [cyan]`opentaion login`[/cyan] to update your proxy URL.")


def _show_auth_error() -> None:
    """Print the 401 auth error to stderr."""
    err_console.print(
        "[bold red]✗ Authentication failed: invalid API key.[/bold red]"
    )
    err_console.print(
        "  Run [cyan]`opentaion login`[/cyan] to reconfigure."
    )


# ── Single proxy request (no retry) ──────────────────────────────────────────

async def _call_proxy_request(
    client: httpx.AsyncClient,
    proxy_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
) -> dict:
    """Make one POST to the proxy. Raises on any failure — caller handles retry."""
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
    try:
        return response.json()
    except (json.JSONDecodeError, ValueError):
        return {"choices": [], "usage": {}}


# ── Agent loop ────────────────────────────────────────────────────────────────

async def _run_agent_loop(proxy_url: str, api_key: str, tier: str, prompt: str) -> None:
    """Multi-turn agent loop with retry on first call and clean error handling."""
    model = EFFORT_MODELS[tier]
    console.print(f"[dim]  ◆ Model: {model} ({tier} tier)[/dim]")

    messages: list[dict] = [{"role": "user", "content": prompt}]
    total_prompt_tokens = 0
    total_completion_tokens = 0

    async with httpx.AsyncClient(timeout=PROXY_TIMEOUT) as client:
        for iteration in range(MAX_ITERATIONS):
            try:
                if iteration == 0:
                    # First call: one silent retry on connection failure (FR9)
                    try:
                        data = await _call_proxy_request(client, proxy_url, api_key, model, messages)
                    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.NetworkError):
                        # Silent first failure — retry once
                        data = await _call_proxy_request(client, proxy_url, api_key, model, messages)
                        # If retry also fails, exception propagates to outer handler
                else:
                    # Mid-loop: no retry (clean failure semantics — metering contract)
                    data = await _call_proxy_request(client, proxy_url, api_key, model, messages)

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    _show_auth_error()
                else:
                    _show_proxy_error(proxy_url)
                sys.exit(1)
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.NetworkError, httpx.TimeoutException):
                _show_proxy_error(proxy_url)
                sys.exit(1)

            # Accumulate token counts
            usage = data.get("usage", {})
            try:
                total_prompt_tokens += int(usage.get("prompt_tokens", 0))
                total_completion_tokens += int(usage.get("completion_tokens", 0))
            except (TypeError, ValueError):
                pass  # malformed usage data — skip this iteration's tokens

            # Extract the assistant's message
            choices = data.get("choices", [])
            if not choices:
                break
            message = choices[0].get("message", {})

            # Check for termination: no tool_calls = final answer
            tool_calls = message.get("tool_calls")
            if not tool_calls:
                # Print the model's final text response if present
                final_content = message.get("content")
                if final_content:
                    console.print(final_content)
                break  # natural termination

            # Append assistant message (with tool_calls) to conversation
            messages.append(message)

            # Execute each tool call and collect results
            for tool_call in tool_calls:
                try:
                    tool_name = tool_call["function"]["name"]
                    tool_args_raw = tool_call["function"]["arguments"]
                except (KeyError, TypeError):
                    continue  # skip malformed tool_call

                try:
                    tool_args = json.loads(tool_args_raw)
                except (json.JSONDecodeError, TypeError):
                    tool_args = {}

                console.print(f"[dim]  ◆ {tool_name}({_args_summary(tool_args)})[/dim]")
                result = _execute_tool(tool_name, tool_args)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", f"call_{iteration}"),
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

    # Load config — fail with actionable error if missing or incomplete
    config = read_config()
    if config is None or "proxy_url" not in config or "api_key" not in config:
        err_console.print("[bold red]✗ Not configured.[/bold red]")
        err_console.print("[dim]  Run [cyan]`opentaion login`[/cyan] to set your proxy URL and API key.[/dim]")
        sys.exit(1)

    asyncio.run(_run_agent_loop(config["proxy_url"], config["api_key"], tier, prompt))
