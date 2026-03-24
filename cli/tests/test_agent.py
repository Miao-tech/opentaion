# cli/tests/test_agent.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from opentaion.agent import AgentLoop, TOOLS, ToolResult


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

def test_tools_contains_all_six_required_tools():
    """SPEC: the tool set is fixed at six tools."""
    tool_names = {t["function"]["name"] for t in TOOLS}
    assert tool_names == {
        "read_file",
        "write_file",
        "edit_file",
        "run_bash",
        "glob_files",
        "search_files",
    }


def test_each_tool_has_required_fields():
    """Every tool must have a name, description, and parameters schema."""
    for tool in TOOLS:
        assert tool["type"] == "function"
        fn = tool["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn


# ---------------------------------------------------------------------------
# AgentLoop construction
# ---------------------------------------------------------------------------

def test_agent_loop_defaults():
    """AgentLoop uses spec defaults when not overridden."""
    loop = AgentLoop(api_key="sk-test", prompt="hello")
    assert loop.max_turns == 10
    assert loop.dry_run is False
    assert loop.model == "deepseek/deepseek-r1"


def test_agent_loop_accepts_custom_values():
    loop = AgentLoop(
        api_key="sk-test",
        prompt="hello",
        model="mistral/mistral-7b",
        max_turns=3,
        dry_run=True,
    )
    assert loop.max_turns == 3
    assert loop.dry_run is True
    assert loop.model == "mistral/mistral-7b"


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_tool_read_file(tmp_path):
    """read_file returns file contents."""
    f = tmp_path / "hello.txt"
    f.write_text("world")
    loop = AgentLoop(api_key="sk-test", prompt="read")
    result: ToolResult = await loop.execute_tool("read_file", {"path": str(f)})
    assert result.success
    assert "world" in result.output


@pytest.mark.asyncio
async def test_execute_tool_write_file(tmp_path):
    """write_file creates a file with the given content."""
    out = tmp_path / "out.txt"
    loop = AgentLoop(api_key="sk-test", prompt="write")
    result: ToolResult = await loop.execute_tool(
        "write_file", {"path": str(out), "content": "hello"}
    )
    assert result.success
    assert out.read_text() == "hello"


@pytest.mark.asyncio
async def test_execute_tool_edit_file(tmp_path):
    """edit_file replaces old string with new string."""
    f = tmp_path / "code.py"
    f.write_text("foo = 1")
    loop = AgentLoop(api_key="sk-test", prompt="edit")
    result: ToolResult = await loop.execute_tool(
        "edit_file", {"path": str(f), "old": "foo = 1", "new": "foo = 2"}
    )
    assert result.success
    assert f.read_text() == "foo = 2"


@pytest.mark.asyncio
async def test_execute_tool_glob_files(tmp_path):
    """glob_files returns matching file paths."""
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.py").write_text("")
    (tmp_path / "c.txt").write_text("")
    loop = AgentLoop(api_key="sk-test", prompt="glob")
    result: ToolResult = await loop.execute_tool(
        "glob_files", {"pattern": str(tmp_path / "*.py")}
    )
    assert result.success
    assert "a.py" in result.output
    assert "b.py" in result.output
    assert "c.txt" not in result.output


@pytest.mark.asyncio
async def test_execute_tool_search_files(tmp_path):
    """search_files returns lines matching the pattern."""
    f = tmp_path / "code.py"
    f.write_text("def foo():\n    pass\ndef bar():\n    pass\n")
    loop = AgentLoop(api_key="sk-test", prompt="search")
    result: ToolResult = await loop.execute_tool(
        "search_files", {"pattern": "def foo", "path": str(tmp_path)}
    )
    assert result.success
    assert "def foo" in result.output


@pytest.mark.asyncio
async def test_execute_tool_run_bash():
    """run_bash executes a shell command and returns stdout."""
    loop = AgentLoop(api_key="sk-test", prompt="bash")
    result: ToolResult = await loop.execute_tool(
        "run_bash", {"command": "echo hello_world"}
    )
    assert result.success
    assert "hello_world" in result.output


@pytest.mark.asyncio
async def test_execute_tool_run_bash_blocks_dangerous_commands():
    """run_bash blocks commands matching dangerous patterns."""
    loop = AgentLoop(api_key="sk-test", prompt="bash")
    result: ToolResult = await loop.execute_tool(
        "run_bash", {"command": "rm -rf /"}
    )
    assert not result.success
    assert "blocked" in result.output.lower()


@pytest.mark.asyncio
async def test_execute_tool_write_file_blocks_api_key_patterns(tmp_path):
    """write_file refuses to write content containing API key patterns."""
    out = tmp_path / "secrets.txt"
    loop = AgentLoop(api_key="sk-test", prompt="write")
    result: ToolResult = await loop.execute_tool(
        "write_file",
        {"path": str(out), "content": "OPENROUTER_API_KEY=sk-or-v1-abc123"},
    )
    assert not result.success
    assert not out.exists()


@pytest.mark.asyncio
async def test_tool_output_truncated_at_10000_tokens(tmp_path):
    """Tool outputs exceeding 10,000 tokens are truncated with a notification."""
    big_file = tmp_path / "big.txt"
    big_file.write_text("word " * 20000)  # well over 10k tokens
    loop = AgentLoop(api_key="sk-test", prompt="read")
    result: ToolResult = await loop.execute_tool("read_file", {"path": str(big_file)})
    assert result.truncated
    assert "[truncated]" in result.output.lower() or "truncated" in result.output.lower()


# ---------------------------------------------------------------------------
# Agent loop control flow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_loop_stops_at_max_turns():
    """The agent loop runs at most max_turns iterations."""
    turn_count = 0

    async def fake_chat(messages, tools):
        nonlocal turn_count
        turn_count += 1
        # Always return a tool call so the loop keeps going
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": f"call_{turn_count}",
                    "type": "function",
                    "function": {"name": "run_bash", "arguments": '{"command": "echo hi"}'},
                }
            ],
        }

    loop = AgentLoop(api_key="sk-test", prompt="run forever", max_turns=3)
    with patch.object(loop, "_chat", side_effect=fake_chat):
        await loop.run()

    assert turn_count <= 3


@pytest.mark.asyncio
async def test_agent_loop_stops_when_no_tool_calls():
    """The loop exits when the assistant returns a plain text response."""
    async def fake_chat(messages, tools):
        return {
            "role": "assistant",
            "content": "Done. No more work to do.",
            "tool_calls": [],
        }

    loop = AgentLoop(api_key="sk-test", prompt="do something", max_turns=10)
    with patch.object(loop, "_chat", side_effect=fake_chat):
        result = await loop.run()

    assert "Done" in result or result is not None


@pytest.mark.asyncio
async def test_dry_run_does_not_execute_tools():
    """In dry-run mode, tool calls are shown but not executed."""
    executed = []

    async def fake_chat(messages, tools):
        if not executed:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "run_bash",
                            "arguments": '{"command": "rm important_file"}',
                        },
                    }
                ],
            }
        return {
            "role": "assistant",
            "content": "Done",
            "tool_calls": [],
        }

    async def fake_execute(name, args):
        executed.append(name)
        return ToolResult(success=True, output="ran", truncated=False)

    loop = AgentLoop(api_key="sk-test", prompt="delete stuff", dry_run=True)
    with patch.object(loop, "_chat", side_effect=fake_chat):
        with patch.object(loop, "execute_tool", side_effect=fake_execute):
            await loop.run()

    assert len(executed) == 0


@pytest.mark.asyncio
async def test_tool_error_included_in_context_and_loop_continues():
    """When a tool fails, its error is added to context and the loop continues."""
    call_count = 0

    async def fake_chat(messages, tools):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_err",
                        "type": "function",
                        "function": {
                            "name": "run_bash",
                            "arguments": '{"command": "false"}',
                        },
                    }
                ],
            }
        # Second turn: check that previous tool result is in messages
        tool_messages = [m for m in messages if m.get("role") == "tool"]
        assert len(tool_messages) >= 1
        return {"role": "assistant", "content": "Handled.", "tool_calls": []}

    loop = AgentLoop(api_key="sk-test", prompt="trigger error")
    with patch.object(loop, "_chat", side_effect=fake_chat):
        await loop.run()

    assert call_count == 2
