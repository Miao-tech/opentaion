# cli/tests/test_context.py
import pytest
from hypothesis import given, strategies as st
from opentaion.context import ContextManager

def make_message(role: str, content: str) -> dict:
    return {"role": role, "content": content}

def test_context_manager_stores_and_retrieves_messages():
    ctx = ContextManager(max_tokens=10000)
    ctx.add(make_message("user", "hello"))
    ctx.add(make_message("assistant", "hi there"))
    messages = ctx.get_messages()
    assert len(messages) == 2
    assert messages[0]["content"] == "hello"
    assert messages[1]["content"] == "hi there"

def test_context_manager_truncates_when_over_limit():
    # Use a small limit to force truncation
    ctx = ContextManager(max_tokens=100)
    for i in range(50):
        ctx.add(make_message("user", f"Message {i}: " + "x" * 10))
    # After truncation, total tokens must fit within limit
    assert ctx.total_tokens() <= 100
    # Most recent message must be preserved
    messages = ctx.get_messages()
    assert any("Message 49" in m["content"] for m in messages)

def test_context_manager_preserves_system_prompt():
    ctx = ContextManager(max_tokens=100)
    ctx.set_system_prompt("You are an AI assistant. " + "x" * 50)
    for i in range(20):
        ctx.add(make_message("user", f"Message {i}: " + "x" * 10))
    messages = ctx.get_messages()
    # System prompt must always be present
    assert messages[0]["role"] == "system"
    assert "You are an AI assistant" in messages[0]["content"]

def test_context_manager_handles_single_oversized_message():
    ctx = ContextManager(max_tokens=10)
    oversized = make_message("user", "x" * 1000)
    ctx.add(oversized)
    # Should not raise; should truncate or flag the message
    messages = ctx.get_messages()
    assert ctx.total_tokens() <= 10 or len(messages) == 1

# Property-based test: any message sequence produces valid context
@given(
    messages=st.lists(
        st.fixed_dictionaries({
            "role": st.sampled_from(["user", "assistant"]),
            "content": st.text(min_size=1, max_size=200),
        }),
        min_size=0,
        max_size=100,
    )
)
def test_context_manager_always_fits_within_limit(messages):
    ctx = ContextManager(max_tokens=1000)
    for msg in messages:
        ctx.add(msg)
    assert ctx.total_tokens() <= 1000
