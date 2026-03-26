# tests/test_deps.py
import os
import time
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import bcrypt as _bcrypt
import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from jwt.algorithms import RSAAlgorithm

from opentaion_api.deps import verify_api_key, verify_supabase_jwt

# Generate a test RSA key pair once for the entire test module
_TEST_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_TEST_PUBLIC_KEY_JWK = RSAAlgorithm.to_jwk(_TEST_PRIVATE_KEY.public_key())

# A second key pair for "wrong key" tests
_OTHER_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


# ── Test helpers ─────────────────────────────────────────────────────────────

def make_test_jwt(user_id: str, private_key=None, expired: bool = False) -> str:
    """Create a signed Supabase-shaped JWT for testing (RS256)."""
    if private_key is None:
        private_key = _TEST_PRIVATE_KEY
    now = int(time.time())
    return pyjwt.encode(
        {
            "sub": user_id,
            "aud": "authenticated",
            "exp": now - 10 if expired else now + 3600,
            "iat": now,
        },
        private_key,
        algorithm="RS256",
    )


def make_key_candidate(key: str, revoked: bool = False) -> MagicMock:
    """Create a mock ApiKey DB row with a real bcrypt hash (rounds=4 for test speed)."""
    candidate = MagicMock()
    candidate.key_hash = _bcrypt.hashpw(key.encode(), _bcrypt.gensalt(rounds=4)).decode()
    candidate.revoked_at = datetime.now(timezone.utc) if revoked else None
    candidate.user_id = uuid.uuid4()
    return candidate


def mock_db_returning(candidates: list) -> AsyncMock:
    """Return an AsyncMock session that yields the given candidates from execute()."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = candidates
    db = AsyncMock()
    db.execute.return_value = mock_result
    return db


TEST_KEY = "ot_testkey1234567890123456789012345"  # 35 chars: "ot_" + 32


# ── verify_api_key ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_api_key_valid_returns_user_id():
    candidate = make_key_candidate(TEST_KEY)
    db = mock_db_returning([candidate])
    result = await verify_api_key(authorization=f"Bearer {TEST_KEY}", db=db)
    assert result == candidate.user_id


@pytest.mark.asyncio
async def test_verify_api_key_revoked_raises_401():
    candidate = make_key_candidate(TEST_KEY, revoked=True)
    db = mock_db_returning([candidate])
    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(authorization=f"Bearer {TEST_KEY}", db=db)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_api_key_no_match_raises_401():
    db = mock_db_returning([])  # prefix lookup returns nothing
    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(authorization=f"Bearer {TEST_KEY}", db=db)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_api_key_missing_bearer_raises_401():
    db = mock_db_returning([])
    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(authorization=TEST_KEY, db=db)  # no "Bearer " prefix
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_api_key_none_header_raises_401():
    db = mock_db_returning([])
    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(authorization=None, db=db)
    assert exc_info.value.status_code == 401


# ── verify_supabase_jwt ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_supabase_jwt_valid_returns_user_id(monkeypatch):
    user_id = str(uuid.uuid4())
    monkeypatch.setenv("SUPABASE_JWT_PUBLIC_KEY", _TEST_PUBLIC_KEY_JWK)
    token = make_test_jwt(user_id)
    result = await verify_supabase_jwt(authorization=f"Bearer {token}")
    assert result == uuid.UUID(user_id)


@pytest.mark.asyncio
async def test_verify_supabase_jwt_expired_raises_401(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_PUBLIC_KEY", _TEST_PUBLIC_KEY_JWK)
    token = make_test_jwt(str(uuid.uuid4()), expired=True)
    with pytest.raises(HTTPException) as exc_info:
        await verify_supabase_jwt(authorization=f"Bearer {token}")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_supabase_jwt_wrong_secret_raises_401(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_PUBLIC_KEY", _TEST_PUBLIC_KEY_JWK)
    token = make_test_jwt(str(uuid.uuid4()), private_key=_OTHER_PRIVATE_KEY)
    with pytest.raises(HTTPException) as exc_info:
        await verify_supabase_jwt(authorization=f"Bearer {token}")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_supabase_jwt_missing_bearer_raises_401(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_PUBLIC_KEY", _TEST_PUBLIC_KEY_JWK)
    token = make_test_jwt(str(uuid.uuid4()))
    with pytest.raises(HTTPException) as exc_info:
        await verify_supabase_jwt(authorization=token)  # no "Bearer " prefix
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_supabase_jwt_none_header_raises_401(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_PUBLIC_KEY", _TEST_PUBLIC_KEY_JWK)
    with pytest.raises(HTTPException) as exc_info:
        await verify_supabase_jwt(authorization=None)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_supabase_jwt_missing_secret_raises_500(monkeypatch):
    monkeypatch.delenv("SUPABASE_JWT_PUBLIC_KEY", raising=False)
    token = make_test_jwt(str(uuid.uuid4()))
    with pytest.raises(HTTPException) as exc_info:
        await verify_supabase_jwt(authorization=f"Bearer {token}")
    assert exc_info.value.status_code == 500
