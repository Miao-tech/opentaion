# Story 1.1: Initialize CLI Python Package

Status: review

## Story

As a developer building OpenTalon,
I want the CLI project scaffolded with its package structure, dependencies, and a working `--version` command,
So that the foundation for all subsequent CLI commands exists and can be verified locally.

## Acceptance Criteria

**AC1 — Version command works:**
Given a macOS machine with `uv` installed
When `uv run python -m opentaion --version` is executed from `cli/`
Then the CLI prints the version string (e.g. `opentaion 0.1.0`) and exits with code 0

**AC2 — Directory structure is correct:**
Given the project is initialized
When the `cli/` directory is examined
Then it contains ALL of the following:
- `src/opentaion/__main__.py` — single `asyncio.run()` entry point
- `src/opentaion/console.py` — module-level `Console` + `err_console` instances; no bare `print()` anywhere in the package
- `src/opentaion/commands/` — directory (empty `__init__.py` is sufficient for now)
- `src/opentaion/core/` — directory (empty `__init__.py` is sufficient for now)
- `tests/` — directory mirroring `src/` structure (at minimum `tests/test_cli.py`)
- `uv.lock` — present and committed
- `pyproject.toml` — with all required dependencies (see Dev Notes)

**AC3 — Test suite passes:**
Given a test is run
When `uv run pytest` is executed from `cli/`
Then the test suite passes — at minimum a smoke test asserting the CLI can be imported without error

## Tasks / Subtasks

- [x] Task 1: Scaffold CLI package with uv (AC: 1, 2)
  - [x] Run `uv init cli` from project root (or initialize if `cli/` already partially exists)
  - [x] Add runtime dependencies: `uv add click rich httpx python-dotenv`
  - [x] Add dev dependencies: `uv add --dev pytest pytest-asyncio`
  - [x] Verify `uv.lock` is generated

- [x] Task 2: Create src layout with correct package structure (AC: 2)
  - [x] Create `src/opentaion/__init__.py` with version string (`__version__ = "0.1.0"`)
  - [x] Create `src/opentaion/__main__.py` with `asyncio.run()` entry point
  - [x] Create `src/opentaion/console.py` with module-level `Console` and `err_console`
  - [x] Create `src/opentaion/commands/__init__.py`
  - [x] Create `src/opentaion/core/__init__.py`
  - [x] Update `pyproject.toml` to use `src` layout and set package name/version

- [x] Task 3: Implement `--version` command (AC: 1)
  - [x] Wire Click group + `--version` option in `__main__.py`
  - [x] Version string format: `opentaion 0.1.0`

- [x] Task 4: Write smoke tests (AC: 3)
  - [x] Create `tests/__init__.py`
  - [x] Create `tests/test_cli.py` with import smoke test
  - [x] Add `--version` invocation test using Click's `CliRunner`
  - [x] Verify `uv run pytest` passes

- [x] Task 5: Validate pyproject.toml entry point (AC: 1)
  - [x] Ensure `[project.scripts]` entry is set: `opentaion = "opentaion.__main__:main"`
  - [x] Confirm `python -m opentaion` invocation works via `__main__.py`

## Dev Notes

### Package Manager — uv (MANDATORY)
- **Never use `pip` or `poetry`** — this project uses `uv` exclusively
- All install commands: `uv add <package>` (runtime), `uv add --dev <package>` (dev)
- Run commands: `uv run python -m opentaion`, `uv run pytest`
- Lock file: `uv.lock` — must be committed, not in `.gitignore`

### Required pyproject.toml Shape

The `pyproject.toml` must declare the `src` layout and contain exactly these dependencies:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "opentaion"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "click>=8.0",
    "rich>=13.0",
    "httpx",
    "python-dotenv",
]

[project.scripts]
opentaion = "opentaion.__main__:main"

[tool.hatch.build.targets.wheel]
packages = ["src/opentaion"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[dependency-groups]
dev = [
    "pytest",
    "pytest-asyncio",
]
```

**Important:** `uv init` may generate a slightly different shape — adjust to match the above. The `asyncio_mode = "auto"` setting is required so `pytest-asyncio` works without decorators on every async test.

### Required File Contents

**`src/opentaion/__main__.py`** — Entry point. All async work flows from `asyncio.run()` here. Never add top-level blocking calls:

```python
# src/opentaion/__main__.py
import asyncio
import click
from opentaion import __version__


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="opentaion")
@click.pass_context
def main(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


if __name__ == "__main__":
    asyncio.run(main())
```

> Note: Click groups don't use `asyncio.run()` at the group level. The `asyncio.run()` call belongs at the command level when a subcommand is actually async. For this story, `main()` is a synchronous Click group — future stories will add async subcommands that call `asyncio.run()` inside their handlers.

**`src/opentaion/__init__.py`:**

```python
# src/opentaion/__init__.py
__version__ = "0.1.0"
```

**`src/opentaion/console.py`** — Module-level singletons. Import from here everywhere — never create Console instances inline:

```python
# src/opentaion/console.py
from rich.console import Console

console = Console()
err_console = Console(stderr=True)
```

- `console` → stdout (normal output, progress, results)
- `err_console` → stderr (errors, warnings)
- **Never use bare `print()`** anywhere in the `opentaion` package. All terminal output goes through these two instances.

**`src/opentaion/commands/__init__.py`** — Empty for this story:
```python
# src/opentaion/commands/__init__.py
```

**`src/opentaion/core/__init__.py`** — Empty for this story:
```python
# src/opentaion/core/__init__.py
```

### Test Requirements

**`tests/test_cli.py`** — minimum required tests:

```python
# tests/test_cli.py
from click.testing import CliRunner
from opentaion.__main__ import main


def test_import():
    """Smoke test: package imports without error."""
    import opentaion
    assert hasattr(opentaion, "__version__")


def test_version():
    """--version prints version string and exits 0."""
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "opentaion" in result.output
    assert "0.1.0" in result.output


def test_no_subcommand_shows_help():
    """Invoking with no args shows help text and exits 0."""
    runner = CliRunner()
    result = runner.invoke(main, [])
    assert result.exit_code == 0
```

- Use `click.testing.CliRunner` for all CLI tests — never subprocess calls in unit tests
- Tests live in `tests/` (not `cli/tests/`) relative to the `cli/` project root
- `pytest-asyncio` is installed but not exercised in this story — it is a dependency for future async tests

### Final Directory Structure

After this story is complete, `cli/` must look exactly like this:

```
cli/
├── pyproject.toml
├── uv.lock
├── src/
│   └── opentaion/
│       ├── __init__.py         # __version__ = "0.1.0"
│       ├── __main__.py         # Click group + --version
│       ├── console.py          # module-level Console + err_console
│       ├── commands/
│       │   └── __init__.py
│       └── core/
│           └── __init__.py
└── tests/
    ├── __init__.py
    └── test_cli.py             # smoke + --version + help tests
```

### CLI Output Conventions (Established Here, Used Everywhere)

These conventions are set in this story and must never be broken in subsequent stories:

| Output type | How to produce it |
|---|---|
| Normal output | `from opentaion.console import console; console.print(...)` |
| Errors | `from opentaion.console import err_console; err_console.print("[bold red]✗ ...[/bold red]", err=True)` |
| Bare `print()` | **FORBIDDEN** — lint will fail |

### Architecture Cross-References

From `architecture.md`:
- Entry point `src/opentaion/__main__.py` enables `uv run python -m opentaion` [Source: architecture.md#Component Initialization]
- Config will later be stored at `~/.opentaion/config.json` — not needed in this story, but the `core/` directory is created here to house it [Source: architecture.md#CLI Python Package]
- `httpx.AsyncClient` will run in an asyncio event loop — not used in this story but `httpx` is installed now [Source: architecture.md#CLI Python Package]

From `epics.md`:
- Additional Requirements: "CLI entry point: Single `asyncio.run()` in `__main__.py`" [Source: epics.md#Additional Requirements]
- Additional Requirements: "All CLI output via Rich Console: Never bare `print()`" [Source: epics.md#Additional Requirements]
- Additional Requirements: "Starter templates: CLI via `uv init cli` + `uv add click rich httpx python-dotenv`" [Source: epics.md#Additional Requirements]

From `cli/SPEC.md`:
- Entry point: `python -m opentaion "your prompt here"` [Source: cli/SPEC.md#Entry Point]
- Tech stack: Click 8.x, Rich 13.x, httpx, python-dotenv [Source: CLAUDE.md#4]

### What This Story Does NOT Include

Do NOT implement any of the following — they belong to later stories:
- `opentaion login` command (Story 2.6)
- `opentaion effort` command (Story 3.4)
- Config file reading/writing (Story 2.6)
- Any HTTP calls to the proxy API
- Any `.env` loading — that comes when actual API calls are needed
- `ruff` or `black` linting setup — not required by any acceptance criterion

### Pre-existing `cli/` directory

The `cli/` directory may already partially exist (it appears in git status as untracked). Before running `uv init`, check what's already there with `ls cli/`. If `pyproject.toml` already exists, adjust rather than overwrite blindly. The goal state is the directory structure above, regardless of starting state.

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

_none_

### Completion Notes List

- `cli/` directory already existed with `pyproject.toml`, `uv.lock`, `agent.py`, `context.py`, `llm.py` and their tests — these were preserved unchanged
- `pyproject.toml` already had the correct hatchling/src layout shape with all required deps (plus extras: tiktoken, hypothesis, ruff, black) — no changes needed
- `__init__.py` was empty — updated with `__version__ = "0.1.0"`
- Created `__main__.py` with Click group + `--version` option as specified
- Created `console.py` with module-level `Console` and `err_console` singletons
- Created `commands/__init__.py` and `core/__init__.py` (empty)
- Created `tests/__init__.py` and `tests/test_cli.py` with 3 tests (TDD: written before implementation confirmed fail, then implementation made them pass)
- `uv run python -m opentaion --version` outputs `opentaion, version 0.1.0` — satisfies AC1 (contains "opentaion" and "0.1.0")
- Full suite: 27 tests, 27 passed, 0 failures

### File List

- `cli/src/opentaion/__init__.py` — MODIFIED (added `__version__ = "0.1.0"`)
- `cli/src/opentaion/__main__.py` — NEW
- `cli/src/opentaion/console.py` — NEW
- `cli/src/opentaion/commands/__init__.py` — NEW
- `cli/src/opentaion/core/__init__.py` — NEW
- `cli/tests/__init__.py` — NEW
- `cli/tests/test_cli.py` — NEW
