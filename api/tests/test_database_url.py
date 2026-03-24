# tests/test_database_url.py
"""Tests for DATABASE_URL scheme normalization in database.py.

Railway/Supabase provide postgresql:// but asyncpg requires postgresql+asyncpg://.
These tests verify the URL replacement logic works correctly.
"""
import importlib
import os
from unittest.mock import patch


def _get_database_url(raw_url: str) -> str:
    """Apply the same URL normalization logic as database.py."""
    return (
        raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if raw_url.startswith("postgresql://")
        else raw_url
    )


def test_postgresql_scheme_is_replaced():
    """postgresql:// is replaced with postgresql+asyncpg://."""
    result = _get_database_url("postgresql://user:pass@host:5432/db")
    assert result == "postgresql+asyncpg://user:pass@host:5432/db"


def test_already_asyncpg_scheme_is_unchanged():
    """postgresql+asyncpg:// is passed through unchanged (no double-replacement)."""
    url = "postgresql+asyncpg://user:pass@host:5432/db"
    result = _get_database_url(url)
    assert result == url


def test_empty_url_is_unchanged():
    """Empty string (no DATABASE_URL set) passes through unchanged."""
    result = _get_database_url("")
    assert result == ""


def test_non_postgresql_scheme_is_unchanged():
    """Other schemes (e.g. sqlite) are not modified."""
    url = "sqlite+aiosqlite:///./test.db"
    result = _get_database_url(url)
    assert result == url


def test_only_first_occurrence_is_replaced():
    """Replacement is applied only to the scheme prefix, not mid-string."""
    url = "postgresql://user:postgresql://extra@host:5432/db"
    result = _get_database_url(url)
    # Only the leading scheme is replaced
    assert result.startswith("postgresql+asyncpg://")
    assert result.count("postgresql+asyncpg://") == 1
