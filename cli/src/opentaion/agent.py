# cli/src/opentaion/agent.py
"""Agent loop for OpenTalon CLI."""
from __future__ import annotations

import asyncio
import glob
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import tiktoken


# ---------------------------------------------------------------------------
# Token counting helper
# ---------------------------------------------------------------------------

_enc = tiktoken.get_encoding("cl100k_base")
TOOL_OUTPUT_TOKEN_LIMIT = 10_000


def _count_tokens(text: str) -> int:
    return len(_enc.encode(text))


def _maybe_truncate(text: str) -> tuple[str, bool]:
    """Return (text, truncated). Truncates to TOOL_OUTPUT_TOKEN_LIMIT tokens."""
    tokens = _enc.encode(text)
    if len(tokens) <= TOOL_OUTPUT_TOKEN_LIMIT:
        return text, False
    truncated = _enc.decode(tokens[:TOOL_OUTPUT_TOKEN_LIMIT])
    truncated += "\n\n[truncated: output exceeded 10,000 tokens]"
    return truncated, True


# ---------------------------------------------------------------------------
# Safety patterns
# ---------------------------------------------------------------------------

_DANGEROUS_BASH_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"rm\s+--no-preserve-root",
    r":\s*\(\s*\)\s*\{.*\}",  # fork bomb
    r"mkfs\.",
    r"dd\s+.*of=/dev/",
    r">\s*/dev/s[dr]",
    r"chmod\s+-R\s+777\s+/",
    r"wget\s+.*\|\s*sh",
    r"curl\s+.*\|\s*sh",
    r"curl\s+.*\|\s*bash",
]

_API_KEY_PATTERNS = [
    r"sk-or-[a-zA-Z0-9\-]+",
    r"OPENROUTER_API_KEY\s*=\s*\S+",
    r"OPENAI_API_KEY\s*=\s*\S+",
    r"sk-[a-zA-Z0-9]{20,}",
]


def _is_dangerous_command(command: str) -> bool:
    for pattern in _DANGEROUS_BASH_PATTERNS:
        if re.search(pattern, command):
            return True
    return False


def _contains_api_key(content: str) -> bool:
    for pattern in _API_KEY_PATTERNS:
        if re.search(pattern, content):
            return True
    return False


# ---------------------------------------------------------------------------
# ToolResult
# ---------------------------------------------------------------------------

@dataclass
class ToolResult:
    success: bool
    output: str
    truncated: bool = False


# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function-calling schema)
# ---------------------------------------------------------------------------

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file's contents from disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative file path"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file (creates or replaces).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace a specific string in a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to edit"},
                    "old": {"type": "string", "description": "String to find and replace"},
                    "new": {"type": "string", "description": "Replacement string"},
                },
                "required": ["path", "old", "new"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_bash",
            "description": "Execute a shell command and return stdout/stderr.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "glob_files",
            "description": "List files matching a glob pattern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern, e.g. src/**/*.py"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search file contents for a regex pattern (like grep -r).",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "path": {"type": "string", "description": "Directory or file path to search"},
                },
                "required": ["pattern", "path"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# AgentLoop
# ---------------------------------------------------------------------------

class AgentLoop:
    """Agentic loop: sends prompts to the LLM, executes tool calls, repeats."""

    DEFAULT_MODEL = "deepseek/deepseek-r1"
    OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
    MAX_RETRIES = 3

    def __init__(
        self,
        api_key: str,
        prompt: str,
        model: str = DEFAULT_MODEL,
        max_turns: int = 10,
        dry_run: bool = False,
    ) -> None:
        self.api_key = api_key
        self.prompt = prompt
        self.model = model
        self.max_turns = max_turns
        self.dry_run = dry_run
        self._messages: list[dict] = []

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self) -> str:
        """Run the agent loop and return the final assistant message."""
        self._messages = [{"role": "user", "content": self.prompt}]

        for _turn in range(self.max_turns):
            response = await self._chat(self._messages, TOOLS)
            self._messages.append(response)

            tool_calls = response.get("tool_calls") or []
            if not tool_calls:
                # Plain text response — we are done
                return response.get("content") or ""

            if self.dry_run:
                # Show tool calls but do not execute
                for tc in tool_calls:
                    fn = tc["function"]
                    print(f"[dry-run] would call {fn['name']}({fn['arguments']})")
                # Stop after showing — no tool results means the loop would
                # stall; return immediately.
                return ""

            # Execute each tool call and append results
            for tc in tool_calls:
                fn = tc["function"]
                name = fn["name"]
                try:
                    args = json.loads(fn["arguments"])
                except json.JSONDecodeError:
                    args = {}

                tool_result = await self.execute_tool(name, args)
                self._messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": name,
                        "content": tool_result.output,
                    }
                )

        # Max turns reached
        return "Max turns reached."

    # ------------------------------------------------------------------
    # LLM call
    # ------------------------------------------------------------------

    async def _chat(self, messages: list[dict], tools: list[dict]) -> dict:
        """Call the OpenRouter API and return the assistant message dict."""
        async with httpx.AsyncClient(trust_env=False, timeout=60.0) as client:
            for attempt in range(self.MAX_RETRIES):
                response = await client.post(
                    self.OPENROUTER_URL,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": self.model, "messages": messages, "tools": tools},
                )
                if response.status_code == 429:
                    if attempt == self.MAX_RETRIES - 1:
                        raise RuntimeError(
                            f"Rate limit exceeded after {self.MAX_RETRIES} attempts"
                        )
                    retry_after = int(response.headers.get("Retry-After", 1))
                    await asyncio.sleep(retry_after)
                    continue
                data = response.json()
                return data["choices"][0]["message"]
        raise RuntimeError("Exhausted retries without a successful response")

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    async def execute_tool(self, name: str, args: dict[str, Any]) -> ToolResult:
        """Dispatch a tool call and return the result."""
        try:
            if name == "read_file":
                return await self._read_file(args)
            elif name == "write_file":
                return await self._write_file(args)
            elif name == "edit_file":
                return await self._edit_file(args)
            elif name == "run_bash":
                return await self._run_bash(args)
            elif name == "glob_files":
                return await self._glob_files(args)
            elif name == "search_files":
                return await self._search_files(args)
            else:
                return ToolResult(success=False, output=f"Unknown tool: {name}")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, output=f"Tool error: {exc}")

    # ------------------------------------------------------------------
    # Individual tool implementations
    # ------------------------------------------------------------------

    async def _read_file(self, args: dict) -> ToolResult:
        path = Path(args["path"])
        if not path.exists():
            return ToolResult(success=False, output=f"File not found: {path}")
        content = path.read_text(errors="replace")
        output, truncated = _maybe_truncate(content)
        return ToolResult(success=True, output=output, truncated=truncated)

    async def _write_file(self, args: dict) -> ToolResult:
        content = args["content"]
        if _contains_api_key(content):
            return ToolResult(
                success=False,
                output="Blocked: content appears to contain an API key or credential.",
            )
        path = Path(args["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return ToolResult(success=True, output=f"Wrote {len(content)} bytes to {path}")

    async def _edit_file(self, args: dict) -> ToolResult:
        path = Path(args["path"])
        if not path.exists():
            return ToolResult(success=False, output=f"File not found: {path}")
        old = args["old"]
        new = args["new"]
        if _contains_api_key(new):
            return ToolResult(
                success=False,
                output="Blocked: replacement content appears to contain an API key.",
            )
        original = path.read_text(errors="replace")
        if old not in original:
            return ToolResult(
                success=False, output=f"String not found in {path}: {old!r}"
            )
        updated = original.replace(old, new, 1)
        path.write_text(updated)
        return ToolResult(success=True, output=f"Edited {path}")

    async def _run_bash(self, args: dict) -> ToolResult:
        command = args["command"]
        if _is_dangerous_command(command):
            return ToolResult(
                success=False,
                output=f"Blocked: command matches a dangerous pattern: {command!r}",
            )
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode(errors="replace")
        output, truncated = _maybe_truncate(output)
        success = proc.returncode == 0
        if not success:
            output = f"Exit code {proc.returncode}:\n{output}"
        return ToolResult(success=success, output=output, truncated=truncated)

    async def _glob_files(self, args: dict) -> ToolResult:
        pattern = args["pattern"]
        matches = glob.glob(pattern, recursive=True)
        output = "\n".join(sorted(matches)) if matches else "(no files matched)"
        output, truncated = _maybe_truncate(output)
        return ToolResult(success=True, output=output, truncated=truncated)

    async def _search_files(self, args: dict) -> ToolResult:
        pattern = args["pattern"]
        search_path = args["path"]
        # Use grep for portability and speed
        proc = await asyncio.create_subprocess_exec(
            "grep", "-rn", "--include=*", pattern, search_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode(errors="replace")
        if not output and stderr:
            output = stderr.decode(errors="replace")
        output, truncated = _maybe_truncate(output)
        # grep exits 1 when no matches — treat as success with empty output
        return ToolResult(success=True, output=output or "(no matches)", truncated=truncated)
