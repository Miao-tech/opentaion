#!/bin/bash
# .claude/hooks/no-api-keys.sh
# PreToolUse hook on Write and Edit
# Blocks file writes that contain patterns matching API keys or secrets

INPUT=$(cat)

# Extract the content being written
# For Write tool: 'content' field
# For Edit tool: 'new_string' field
CONTENT=$(echo "$INPUT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
content = d.get('content') or d.get('new_string') or ''
print(content)
" 2>/dev/null)

# Check for common secret patterns
# These patterns are deliberately conservative to minimize false positives

# OpenRouter / OpenAI style keys: sk- followed by 40+ alphanumeric chars
if echo "$CONTENT" | grep -qE 'sk-[A-Za-z0-9]{40,}'; then
    echo '{"decision":"block","reason":"File contains what appears to be an OpenAI/OpenRouter API key (sk-...). Use environment variables instead: os.environ[\"OPENROUTER_API_KEY\"]"}'
    exit 0
fi

# Bearer tokens: Bearer followed by 30+ alphanumeric/special chars
if echo "$CONTENT" | grep -qE '"Bearer [A-Za-z0-9+/=_-]{30,}"'; then
    echo '{"decision":"block","reason":"File contains a hard-coded Bearer token. Use environment variables instead."}'
    exit 0
fi

# Supabase keys: typically eyJ... (base64-encoded JWT)
if echo "$CONTENT" | grep -qE '"eyJ[A-Za-z0-9+/=]{50,}"'; then
    echo '{"decision":"block","reason":"File contains what appears to be a Supabase JWT key. Use environment variables: os.environ[\"SUPABASE_ANON_KEY\"]"}'
    exit 0
fi

# Generic: long alphanumeric strings assigned to key-like variable names
if echo "$CONTENT" | grep -qiE '(api_key|secret_key|auth_token|access_token)\s*=\s*"[A-Za-z0-9+/=_-]{32,}"'; then
    echo '{"decision":"block","reason":"File contains a hard-coded credential (api_key, secret_key, or token assigned a literal value). Use environment variables instead."}'
    exit 0
fi

echo '{"decision":"approve"}'
