#!/bin/bash
# .claude/hooks/block-dangerous-rm.sh
# Receives tool call JSON via stdin, returns decision

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('command',''))")

# Block rm -rf on project root or home directory
if echo "$COMMAND" | grep -qE "rm -rf (/|~|\.\./)"; then
    echo '{"decision":"block","reason":"rm -rf targeting root, home, or parent directory is blocked. Use specific paths within the project."}'
    exit 0
fi

# Allow everything else
echo '{"decision":"approve"}'
