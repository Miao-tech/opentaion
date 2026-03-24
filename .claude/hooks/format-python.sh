#!/bin/bash
# .claude/hooks/format-python.sh
# Runs after any Write or Edit tool call on a .py file

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
# Write tool output has 'filePath', Edit tool has 'path'
print(d.get('filePath') or d.get('path') or '')
")

# Only run on Python files
if [[ "$FILE_PATH" != *.py ]]; then
    exit 0
fi

# Run from the project root (file paths are relative to project)
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# Run ruff and black; suppress output unless they fail
uv run ruff check --fix "$FILE_PATH" 2>&1 | grep -v "^Found\|^All checks"
uv run black "$FILE_PATH" --quiet 2>&1

exit 0
