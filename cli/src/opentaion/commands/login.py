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
    if not proxy_url.startswith(("http://", "https://")):
        err_console.print("[bold red]✗ Proxy URL must start with http:// or https://[/bold red]")
        sys.exit(1)

    api_key: str = click.prompt(
        "OpenTalon API Key",
        hide_input=True,
    )
    if not api_key.strip():
        err_console.print("[bold red]✗ API key cannot be empty[/bold red]")
        sys.exit(1)

    # Validate connectivity against the health endpoint
    try:
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.get(
                f"{proxy_url.rstrip('/')}/health",
                timeout=5.0,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        err_console.print(
            f"[bold red]✗ Proxy returned {exc.response.status_code}: {proxy_url}[/bold red]"
        )
        err_console.print("[dim]  The server is reachable but returned an error.[/dim]")
        sys.exit(1)
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
