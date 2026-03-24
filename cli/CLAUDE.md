# CLI — Component Rules

## Environment
- Package manager: uv (never pip, never poetry)
- Run the agent: `uv run python -m opentaion "your prompt"`
- Run tests: `uv run pytest tests/ -v`
- Lint: `uv run ruff check . && uv run black --check .`

## Click conventions
- Commands defined with @click.command() and @click.option() decorators
- Groups under `cli = click.group()`
- Pass config through Click context (ctx.obj) — not global variables

## Rich display
- All console output via `rich.console.Console()`
- Progress: `with console.status("[bold]Working..."):`
- Errors: `console.print("[red]Error:[/red] message", err=True)`

## Anti-patterns (IMPORTANT)
- Never import from web/ or api/ — CLI is a standalone tool
- Never use synchronous httpx — async/await for all HTTP calls
- Never hard-code API base URL — read from config