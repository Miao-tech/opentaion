---
name: opentaion-component
description: Scaffold a new OpenTalon CLI command with test stub
argument-hint: <component-name>
allowed-tools:
  - Read
  - Glob
  - Write
  - Bash
---

# Skill: opentaion-component

Scaffold a new CLI command for the OpenTalon agent.

## Arguments

`$ARGUMENTS` — the component name in snake_case (e.g., `config`, `usage_report`)

## Procedure

1. **Read existing structure**
   - Glob `cli/src/opentaion/*.py` to see existing command files
   - Read one existing command file to understand the import and decorator pattern

2. **Create the command file**
   Write `cli/src/opentaion/{$ARGUMENTS}.py`:

   \```python
   # cli/src/opentaion/{component_name}.py
   import click
   from rich.console import Console

   console = Console()

   @click.command()
   @click.argument("input", required=False)
   def {component_name}(input: str | None) -> None:
       """[Brief description of what this command does]"""
       console.print(f"[yellow]{component_name}:[/yellow] not yet implemented")
   \```

3. **Create the test stub**
   Write `cli/tests/test_{$ARGUMENTS}.py`:

   \```python
   # cli/tests/test_{component_name}.py
   from opentaion.{component_name} import {component_name}
   from click.testing import CliRunner
   
   def test_{component_name}_exists():
       runner = CliRunner()
       result = runner.invoke({component_name}, [])
       assert result.exit_code == 0
   \```

4. **Run the test**
   \```bash
   cd cli && uv run pytest tests/test_{$ARGUMENTS}.py -v
   \```
   Confirm: the import succeeds and the test passes (the stub is functional).

5. **Report**
   Tell the user:
   
   - What files were created
   - The test result
   - The next step: implement `{component_name}()` to replace the stub

## Notes
- Replace `{component_name}` with the actual `$ARGUMENTS` value throughout
- Do not implement the feature — only scaffold the structure
- If `$ARGUMENTS` contains hyphens, convert to underscores for Python identifiers