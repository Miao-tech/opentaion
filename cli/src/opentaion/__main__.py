# src/opentaion/__main__.py
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
    main()
