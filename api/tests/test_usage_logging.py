# tests/test_usage_logging.py
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opentaion_api.routers.proxy import write_usage_log


TEST_USER_ID = uuid.uuid4()


def make_mock_db():
    """Create a mock AsyncSession for testing write_usage_log."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


def mock_session_factory(db):
    """Create a mock AsyncSessionLocal that yields the given db mock."""
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=db)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return MagicMock(return_value=ctx)


# ── Successful write ───────────────────────────────────────────────────────────

async def test_write_usage_log_calls_db_add_and_commit():
    db = make_mock_db()
    with patch("opentaion_api.routers.proxy.AsyncSessionLocal", mock_session_factory(db)):
        await write_usage_log(TEST_USER_ID, "deepseek/deepseek-r1:free", 1000, 500)
    db.add.assert_called_once()
    db.commit.assert_awaited_once()


async def test_write_usage_log_model_field():
    db = make_mock_db()
    with patch("opentaion_api.routers.proxy.AsyncSessionLocal", mock_session_factory(db)):
        await write_usage_log(TEST_USER_ID, "meta-llama/llama-3.3-70b-instruct:free", 100, 50)
    log_record = db.add.call_args[0][0]
    assert log_record.model == "meta-llama/llama-3.3-70b-instruct:free"


async def test_write_usage_log_token_fields():
    db = make_mock_db()
    with patch("opentaion_api.routers.proxy.AsyncSessionLocal", mock_session_factory(db)):
        await write_usage_log(TEST_USER_ID, "deepseek/deepseek-r1:free", 1234, 567)
    log_record = db.add.call_args[0][0]
    assert log_record.prompt_tokens == 1234
    assert log_record.completion_tokens == 567


async def test_write_usage_log_user_id_field():
    db = make_mock_db()
    with patch("opentaion_api.routers.proxy.AsyncSessionLocal", mock_session_factory(db)):
        await write_usage_log(TEST_USER_ID, "deepseek/deepseek-r1:free", 100, 50)
    log_record = db.add.call_args[0][0]
    assert log_record.user_id == TEST_USER_ID


async def test_write_usage_log_cost_usd_is_decimal():
    db = make_mock_db()
    with patch("opentaion_api.routers.proxy.AsyncSessionLocal", mock_session_factory(db)):
        await write_usage_log(TEST_USER_ID, "deepseek/deepseek-r1:free", 1000, 500)
    log_record = db.add.call_args[0][0]
    assert isinstance(log_record.cost_usd, Decimal)


async def test_write_usage_log_free_model_cost_is_zero():
    db = make_mock_db()
    with patch("opentaion_api.routers.proxy.AsyncSessionLocal", mock_session_factory(db)):
        await write_usage_log(TEST_USER_ID, "deepseek/deepseek-r1:free", 1_000_000, 500_000)
    log_record = db.add.call_args[0][0]
    assert log_record.cost_usd == Decimal("0")


async def test_write_usage_log_paid_model_cost_computed():
    """deepseek/deepseek-r1 (not :free): 1M prompt + 1M completion = $2.74"""
    db = make_mock_db()
    with patch("opentaion_api.routers.proxy.AsyncSessionLocal", mock_session_factory(db)):
        await write_usage_log(TEST_USER_ID, "deepseek/deepseek-r1", 1_000_000, 1_000_000)
    log_record = db.add.call_args[0][0]
    assert log_record.cost_usd == Decimal("2.74")


# ── Failure path — must not propagate ─────────────────────────────────────────

async def test_write_usage_log_db_commit_failure_does_not_raise(capsys):
    """DB failure must be silent to the caller — only logged to stdout."""
    db = make_mock_db()
    db.commit = AsyncMock(side_effect=Exception("DB connection lost"))

    with patch("opentaion_api.routers.proxy.AsyncSessionLocal", mock_session_factory(db)):
        result = await write_usage_log(TEST_USER_ID, "deepseek/deepseek-r1:free", 100, 50)
    assert result is None


async def test_write_usage_log_db_failure_logged_to_stdout(capsys):
    db = make_mock_db()
    db.commit = AsyncMock(side_effect=Exception("connection timeout"))

    with patch("opentaion_api.routers.proxy.AsyncSessionLocal", mock_session_factory(db)):
        await write_usage_log(TEST_USER_ID, "deepseek/deepseek-r1:free", 100, 50)
    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "write_usage_log" in captured.out


async def test_write_usage_log_db_add_failure_does_not_raise():
    db = make_mock_db()
    db.add = MagicMock(side_effect=Exception("add failed"))
    with patch("opentaion_api.routers.proxy.AsyncSessionLocal", mock_session_factory(db)):
        await write_usage_log(TEST_USER_ID, "deepseek/deepseek-r1:free", 100, 50)
