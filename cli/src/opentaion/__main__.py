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
