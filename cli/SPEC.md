### SPEC: OpenTalon CLI — Version 1

**Written:** Chapter 9 | **Governs:** Chapters 9–12 | **Status:** Active

---

#### Purpose

OpenTalon CLI is a terminal-based coding agent for macOS. Given a natural language prompt, it reasons about the current directory's codebase, uses file system and shell tools to gather context and make changes, calls an LLM via OpenRouter for reasoning, and reports results to the terminal.

The CLI is a standalone tool. It does not require the OpenTalon web platform or API to function. It can operate with only an OpenRouter API key.

---

#### Non-Goals (V1)

These features will not be in V1. Including them would increase scope beyond what can be built and tested in the book's timeline.

- **No multi-file diff view.** Results are shown as individual file edits, not a unified diff.
- **No conversation persistence.** Each session is independent. No session history is saved.
- **No plugin system.** The tool set is fixed at the six tools described below.
- **No GUI or web interface.** Terminal only.
- **No Windows support.** macOS only. Linux may work but is untested.
- **No streaming partial results.** Output is shown when complete, not streamed token by token.

---

#### Entry Point

```
python -m opentaion "your prompt here"
```

Or via the installed Homebrew command:

```
opentaion "your prompt here"
```

Flags:

- `--model MODEL` — override the default model (default: `deepseek/deepseek-r1`)
- `--max-turns N` — maximum agent loop iterations (default: 10)
- `--effort [low|medium|high]` — thinking budget (default: medium)
- `--dry-run` — show what would be done without executing

---

#### Tool Set (Fixed)

The CLI exposes exactly six tools to the LLM:

| Tool                          | Function                                         |
| ----------------------------- | ------------------------------------------------ |
| `read_file(path)`             | Read a file's contents                           |
| `write_file(path, content)`   | Write content to a file (creates or replaces)    |
| `edit_file(path, old, new)`   | Replace a specific string in a file              |
| `run_bash(command)`           | Execute a shell command and return stdout/stderr |
| `glob_files(pattern)`         | List files matching a glob pattern               |
| `search_files(pattern, path)` | Search file contents for a regex pattern         |

All tools include basic safety checks:

- `run_bash`: blocks commands matching dangerous patterns (same patterns as the PreToolUse hook)
- `write_file` and `edit_file`: scan content for API key patterns before writing

---

#### Context Management

The CLI manages a context window of approximately 100,000 tokens (conservative estimate to allow headroom).

Context budget allocation:

- System prompt + tool definitions: ~8,000 tokens (reserved)
- Conversation history: up to 60,000 tokens before compaction triggers
- Single tool output: capped at 10,000 tokens (truncated with notification if exceeded)

When conversation history exceeds 60,000 tokens, the context manager:

1. Summarizes the conversation history to date (approximately 1,000 tokens)
2. Replaces the full history with the summary
3. Continues the session from the summary

This compaction is invisible to the user — the agent continues as if no compaction occurred.

---

#### OpenRouter Integration

The CLI calls OpenRouter's API, which is OpenAI-compatible. It uses the `POST /v1/chat/completions` endpoint.

Required configuration (via `.env` in project root or environment variables):

```
OPENROUTER_API_KEY=sk-or-...
OPENTAION_MODEL=deepseek/deepseek-r1       (optional, overrides default)
```

The client implements:

- Automatic retry on 429 (rate limit): exponential backoff, maximum 3 retries
- Timeout: 60 seconds per request
- No streaming (V1)

---

#### Error Handling Strategy

| Error condition                 | Behavior                                              |
| ------------------------------- | ----------------------------------------------------- |
| OpenRouter API key missing      | Print error, exit 1 immediately                       |
| Tool call fails (non-zero exit) | Include error in context, continue loop               |
| Context compaction fails        | Print warning, attempt to continue                    |
| Max turns reached               | Print summary of completed and remaining work, exit 0 |
| Network timeout                 | Retry once, then print error and exit 1               |

---

#### Acceptance Criteria

Done means:

1. `uv run python -m opentaion "list the Python files in this directory"` runs without error and produces a response
2. The agent loop runs at most `--max-turns` iterations then terminates
3. Tool outputs exceeding 10,000 tokens are truncated with a notification
4. Context compaction triggers automatically when history exceeds 60,000 tokens
5. OpenRouter retry logic retries on 429 and succeeds if the second request succeeds
6. `--dry-run` shows the planned tool calls without executing them