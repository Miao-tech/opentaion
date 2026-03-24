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
