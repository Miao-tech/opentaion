# Story 2.6: CLI `opentaion login` Command

Status: ready-for-dev

## Story

As a developer building OpenTalon,
I want the `opentaion login` command implemented,
So that I can authenticate my CLI against my deployed API by entering the proxy URL and pasting my API key.

## Acceptance Criteria

**AC1 — Login command prompts for proxy URL then API key:**
Given the user runs `opentaion login`
When the command starts
Then the terminal displays sequential prompts: (1) `Proxy URL (e.g. https://your-api.railway.app):` then (2) `OpenTalon API Key:` (input hidden)

**AC2 — Successful login writes config and prints confirmation:**
Given the user enters a proxy URL and API key
When the CLI reaches `GET <proxy_url>/health` successfully
Then credentials are written to `~/.opentaion/config.json` as `{"proxy_url": "...", "api_key": "...", "user_email": ""}` and the terminal prints `✓ Connected to <proxy_url>` and `✓ Configuration saved to ~/.opentaion/config.json`

**AC3 — Unreachable proxy prints error and does NOT write config:**
Given the proxy URL is unreachable
When the health check fails
Then the terminal prints `✗ Proxy unreachable: <url>` in bold red to stderr, a hint to check the Railway deployment, and the config file is NOT written

**AC4 — Re-running login overwrites existing config:**
Given `~/.opentaion/config.json` already exists
When `opentaion login` is run again with new values
Then the existing config is overwritten with the new values

**AC5 — Tests pass:**
Given tests are run
When `uv run pytest` is executed from `cli/`
Then tests pass for: successful login (mocked health check), unreachable proxy (mocked failure), config file write, and config file overwrite

## Tasks / Subtasks

- [ ] Task 1: Create `src/opentaion/core/config.py` for config read/write utilities (used by future commands)
  - [ ] `CONFIG_PATH` constant: `Path.home() / ".opentaion" / "config.json"`
  - [ ] `write_config(proxy_url, api_key)` — creates dir, writes JSON
  - [ ] `read_config()` — reads JSON, returns dict or None if missing

- [ ] Task 2: Write tests FIRST in `tests/test_login.py` — confirm they fail (TDD)
  - [ ] Tests for successful login, unreachable proxy, overwrite — all fail before implementation
  - [ ] Use `CliRunner` + `monkeypatch` + `httpx.AsyncClient` mock

- [ ] Task 3: Create `src/opentaion/commands/login.py` (AC: 1, 2, 3, 4)
  - [ ] `@click.command()` function `login` that calls `asyncio.run(_login())`
  - [ ] `_login()` async function: prompts, health check, config write, output

- [ ] Task 4: Register `login` command in `__main__.py` (AC: 1)
  - [ ] Import `login` from `opentaion.commands.login`
  - [ ] `main.add_command(login)`

- [ ] Task 5: Run tests green (AC: 5)
  - [ ] `uv run pytest tests/test_login.py -v`
  - [ ] `uv run pytest` — full suite passes (test_cli.py + test_login.py)

## Dev Notes

### Prerequisites: Story 1.1 Must Be Complete

- `src/opentaion/__main__.py` must have the `main` Click group
- `src/opentaion/console.py` must have `console` and `err_console`
- `src/opentaion/commands/__init__.py` must exist
- `src/opentaion/core/__init__.py` must exist

### Config Utilities — `src/opentaion/core/config.py`

Create this module now even though only `login` uses it — Story 3.4 (`opentaion effort`) reads the config on every invocation. Centralizing config access here prevents duplicate path logic:

```python
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
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    config: Config = {
        "proxy_url": proxy_url.rstrip("/"),  # strip trailing slash for consistent URL building
        "api_key": api_key,
        "user_email": "",  # placeholder — populated in a future version
    }
    CONFIG_PATH.write_text(json.dumps(config, indent=2))


def read_config() -> Config | None:
    """Read ~/.opentaion/config.json. Returns None if file does not exist."""
    if not CONFIG_PATH.exists():
        return None
    return json.loads(CONFIG_PATH.read_text())
```

**Why `proxy_url.rstrip("/")`?**
Story 3.4 constructs `{proxy_url}/v1/chat/completions`. If the stored URL has a trailing slash, requests go to `https://api.railway.app//v1/chat/completions` — double slash causes 404 on some servers. Strip it at write time to prevent this bug in all downstream consumers.

**Why `TypedDict` and not a dataclass?**
`json.loads()` returns a plain `dict`. A `TypedDict` gives type checking without needing serialization/deserialization logic. `Config | None` return type makes missing config explicit — callers can't forget the "not configured" case.

### Login Command — `src/opentaion/commands/login.py`

```python
# src/opentaion/commands/login.py
import asyncio
import sys

import click
import httpx

from opentaion.console import console, err_console
from opentaion.core.config import CONFIG_PATH, write_config


@click.command()
def login() -> None:
    """Configure the proxy URL and API key for OpenTalon."""
    asyncio.run(_login())


async def _login() -> None:
    proxy_url: str = click.prompt(
        "Proxy URL (e.g. https://your-api.railway.app)"
    )
    api_key: str = click.prompt(
        "OpenTalon API Key",
        hide_input=True,
    )

    # Validate connectivity against the health endpoint
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{proxy_url.rstrip('/')}/health",
                timeout=5.0,
            )
            response.raise_for_status()
    except Exception:
        err_console.print(f"[bold red]✗ Proxy unreachable: {proxy_url}[/bold red]")
        err_console.print("[dim]  Check that your Railway deployment is running.[/dim]")
        err_console.print(f"[cyan]  Try: curl {proxy_url.rstrip('/')}/health[/cyan]")
        sys.exit(1)

    write_config(proxy_url, api_key)

    console.print(f"[bold]✓[/bold] Connected to {proxy_url}")
    console.print(
        f"[bold]✓[/bold] Configuration saved to [bold]{CONFIG_PATH}[/bold]"
    )
```

**Why `except Exception` (not `httpx.ConnectError`)?**
Health check failures can come from many sources: `ConnectError` (unreachable), `TimeoutException` (Railway cold start too slow), `HTTPStatusError` (server returned 5xx), `ssl.SSLError` (cert issues). Catching all of them and showing a unified "unreachable" message is the right UX — the user's fix is always the same ("check Railway").

**Why `asyncio.run(_login())` in a sync `login()` wrapper?**
Click commands are called synchronously. `asyncio.run()` creates a new event loop, runs the coroutine, and tears it down. This is the correct pattern for a CLI entry point. Do NOT make `login` itself an `async def` — Click doesn't await it.

**Why `sys.exit(1)` not `raise SystemExit(1)`?**
Both work identically. `sys.exit(1)` is the conventional form; `raise SystemExit(1)` is what it expands to internally. The important thing is that the exit code is `1` (non-zero) on failure, and `0` (default) on success.

### Register in `__main__.py`

```python
# src/opentaion/__main__.py
import asyncio
import click
from opentaion import __version__
from opentaion.commands.login import login


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="opentaion")
@click.pass_context
def main(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


main.add_command(login)


if __name__ == "__main__":
    asyncio.run(main())
```

### Tests — `tests/test_login.py`

Write BEFORE implementing `login.py`. Confirm they fail (commands return non-zero or raise errors before the command exists).

```python
# tests/test_login.py
import json
from pathlib import Path
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
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            ["login"],
            input="https://myapp.up.railway.app\nmysecretapikey\n",
        )

    assert result.exit_code == 0, result.output
    assert tmp_config_path.exists()
    config = json.loads(tmp_config_path.read_text())
    assert config["proxy_url"] == "https://myapp.up.railway.app"
    assert config["api_key"] == "mysecretapikey"
    assert config["user_email"] == ""


def test_login_success_output_contains_confirmation(tmp_config_path):
    mock_client = make_mock_client()

    with patch("opentaion.commands.login.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            ["login"],
            input="https://myapp.up.railway.app\nmysecretapikey\n",
        )

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
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            ["login"],
            input="https://newapp.up.railway.app\nnewkey\n",
        )

    assert result.exit_code == 0
    config = json.loads(tmp_config_path.read_text())
    assert config["proxy_url"] == "https://newapp.up.railway.app"
    assert config["api_key"] == "newkey"


# ── Failure tests ─────────────────────────────────────────────────────────────

def test_login_unreachable_proxy_exits_1(tmp_config_path):
    mock_client = make_mock_client(raise_exc=httpx.ConnectError("Connection refused"))

    with patch("opentaion.commands.login.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            ["login"],
            input="https://unreachable.example.com\nmysecretapikey\n",
        )

    assert result.exit_code == 1


def test_login_unreachable_proxy_does_not_write_config(tmp_config_path):
    mock_client = make_mock_client(raise_exc=httpx.ConnectError("Connection refused"))

    with patch("opentaion.commands.login.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner(mix_stderr=False)
        runner.invoke(
            main,
            ["login"],
            input="https://unreachable.example.com\nmysecretapikey\n",
        )

    assert not tmp_config_path.exists()
```

**`CliRunner(mix_stderr=False)`** — separates stdout and stderr so `result.output` only contains stdout. Errors written to `err_console` (stderr) don't pollute the output assertions.

**`mock_client.__aenter__/__aexit__`** — `httpx.AsyncClient` is used as `async with ... as client:`. The mock must implement both dunder methods to act as a valid async context manager. Without them, the `async with` statement raises `TypeError`.

**`monkeypatch.setattr(login_module, "CONFIG_PATH", fake_path)`** — the `CONFIG_PATH` constant is imported at module load time in `login.py`. Simply patching `config_module.CONFIG_PATH` is not enough — the `login.py` module has already bound its own reference to the original value. Both references must be patched.

### Output Format — UX-DR8 Compliance

| Output | Format | Rich markup |
|---|---|---|
| Setup prompt (URL) | `Proxy URL (e.g. https://your-api.railway.app):` | Plain `click.prompt()` |
| Setup prompt (key) | `OpenTalon API Key:` + hidden input | `click.prompt(hide_input=True)` |
| Success line 1 | `✓ Connected to <url>` | `[bold]✓[/bold] Connected to ...` |
| Success line 2 | `✓ Configuration saved to ~/.opentaion/config.json` | `[bold]✓[/bold] Configuration saved to [bold]{path}[/bold]` |
| Error title | `✗ Proxy unreachable: <url>` | `[bold red]✗ Proxy unreachable: ...[/bold red]` → stderr |
| Error detail | `  Check that your Railway deployment is running.` | `[dim]  ...[/dim]` → stderr |
| Error recovery | `  Try: curl <url>/health` | `[cyan]  Try: ...[/cyan]` → stderr |

**All success output → `console` (stdout).** All error output → `err_console` (stderr). This matters for shell scripting: `opentaion login 2>/dev/null` suppresses errors, and tools that pipe `opentaion login` output won't see error messages.

### Architecture Cross-References

From `architecture.md`:
- CLI entry point: `asyncio.run()` in `__main__.py`, all async work flows from there [Source: architecture.md#CLI Python Package]
- Config stored at `~/.opentaion/config.json` [Source: architecture.md#CLI Python Package]
- All CLI output via Rich Console — never bare `print()` [Source: architecture.md#Implementation Patterns]
- `httpx.AsyncClient` created once per command invocation [Source: architecture.md#CLI Python Package]
- CLI timeout: `connect=5.0` [Source: architecture.md#Gap Resolutions]

From `epics.md`:
- FR11: "The CLI stores its proxy URL and API key in a persistent global config file, available across all project directories on the machine" [Source: epics.md#FR11]
- FR26: "The CLI displays a confirmation message in the terminal upon successful first-time authentication" [Source: epics.md#FR26]
- NFR10: "The CLI must surface a deterministic error message and exit within 5 seconds of a proxy connection failure" [Source: epics.md#NFR10]
- UX-DR8: SetupPrompt and SuccessLine output formats [Source: epics.md#UX-DR8]

### What This Story Does NOT Include

- `opentaion effort` command that READS the config (Story 3.4 — that command uses `read_config()`)
- Validating the API key against the proxy (just checks connectivity via `/health`)
- Storing `user_email` — the field exists but is always `""` in V1
- Magic link flow from the CLI — authentication is done via the web dashboard (Stories 2.3–2.5); the CLI just stores the key

### This Completes Epic 2

After Story 2.6 is done, Epic 2 is complete:
- API: auth dependencies (`verify_api_key`, `verify_supabase_jwt`) implemented and tested
- API: key CRUD endpoints (`POST/GET/DELETE /api/keys`) deployed
- Web: login page with magic link flow
- Web: authenticated sidebar navigation
- Web: API keys view with generate/list/revoke
- CLI: `opentaion login` command writing config to `~/.opentaion/config.json`

Epic 3 (Metered Task Execution) is next — starts with pricing dict and the proxy endpoint.

### Final Modified/Created Files

```
cli/
└── src/opentaion/
    ├── __main__.py           # MODIFIED — add login command
    ├── core/
    │   └── config.py         # NEW — CONFIG_PATH, write_config(), read_config()
    └── commands/
        └── login.py          # NEW — opentaion login command
tests/
└── test_login.py             # NEW — login command tests
```

## Dev Agent Record

### Agent Model Used

_to be filled by dev agent_

### Debug Log References

_none_

### Completion Notes List

_to be filled by dev agent_

### File List

_to be filled by dev agent_
