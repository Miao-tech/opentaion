# tests/test_keys.py
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from opentaion_api.main import app
from opentaion_api.database import get_db
from opentaion_api.deps import verify_supabase_jwt

TEST_USER_ID = uuid.uuid4()
TEST_KEY_ID = uuid.uuid4()


# ── Dependency overrides ──────────────────────────────────────────────────────

def override_auth():
    """Always authenticates as TEST_USER_ID — no real JWT needed."""
    return TEST_USER_ID


def make_mock_key(user_id: uuid.UUID = TEST_USER_ID, revoked: bool = False) -> MagicMock:
    key = MagicMock()
    key.id = TEST_KEY_ID
    key.user_id = user_id
    key.key_hash = "hashed"
    key.key_prefix = "ot_testkey12"
    key.created_at = datetime.now(timezone.utc)
    key.revoked_at = datetime.now(timezone.utc) if revoked else None
    return key


# ── POST /api/keys ────────────────────────────────────────────────────────────

def test_create_key_returns_201_with_plaintext_key():
    mock_key = make_mock_key()

    async def override_db():
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "created_at", mock_key.created_at) or setattr(obj, "id", TEST_KEY_ID))
        yield db

    app.dependency_overrides[verify_supabase_jwt] = override_auth
    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post("/api/keys")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["key"].startswith("ot_")
    assert len(data["key"]) == 35  # "ot_" + 32 chars
    assert data["key_prefix"] == data["key"][:12]
    assert "id" in data
    assert "created_at" in data
    assert "key_hash" not in data  # never exposed


def test_create_key_requires_auth():
    client = TestClient(app)
    response = client.post("/api/keys")  # no override → real verify_supabase_jwt → 401
    assert response.status_code == 401


# ── GET /api/keys ─────────────────────────────────────────────────────────────

def test_list_keys_returns_active_keys():
    mock_key = make_mock_key()

    async def override_db():
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_key]
        db = AsyncMock()
        db.execute.return_value = mock_result
        yield db

    app.dependency_overrides[verify_supabase_jwt] = override_auth
    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.get("/api/keys")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["key_prefix"] == "ot_testkey12"
    assert "key_hash" not in data[0]
    assert "key" not in data[0]  # full key never in list response


def test_list_keys_returns_empty_list():
    async def override_db():
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db = AsyncMock()
        db.execute.return_value = mock_result
        yield db

    app.dependency_overrides[verify_supabase_jwt] = override_auth
    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.get("/api/keys")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == []


def test_list_keys_requires_auth():
    client = TestClient(app)
    response = client.get("/api/keys")
    assert response.status_code == 401


# ── DELETE /api/keys/{key_id} ─────────────────────────────────────────────────

def test_revoke_key_returns_204():
    mock_key = make_mock_key()

    async def override_db():
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_key
        db = AsyncMock()
        db.execute.return_value = mock_result
        db.commit = AsyncMock()
        yield db

    app.dependency_overrides[verify_supabase_jwt] = override_auth
    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.delete(f"/api/keys/{TEST_KEY_ID}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert mock_key.revoked_at is not None  # verify revoked_at was set


def test_revoke_already_revoked_key_returns_404():
    async def override_db():
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # query filters revoked_at IS NULL → None
        db = AsyncMock()
        db.execute.return_value = mock_result
        yield db

    app.dependency_overrides[verify_supabase_jwt] = override_auth
    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.delete(f"/api/keys/{TEST_KEY_ID}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_revoke_key_not_found_returns_404():
    async def override_db():
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # key not found
        db = AsyncMock()
        db.execute.return_value = mock_result
        yield db

    app.dependency_overrides[verify_supabase_jwt] = override_auth
    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.delete(f"/api/keys/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_revoke_key_requires_auth():
    client = TestClient(app)
    response = client.delete(f"/api/keys/{TEST_KEY_ID}")
    assert response.status_code == 401
