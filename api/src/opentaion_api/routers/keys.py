# src/opentaion_api/routers/keys.py
import secrets
import uuid
from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opentaion_api.database import get_db
from opentaion_api.deps import verify_supabase_jwt
from opentaion_api.models import ApiKey
from opentaion_api.schemas import ApiKeyCreateResponse, ApiKeyListItem

router = APIRouter(tags=["keys"])


@router.post("/keys", response_model=ApiKeyCreateResponse, status_code=201)
async def create_api_key(
    user_id: uuid.UUID = Depends(verify_supabase_jwt),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyCreateResponse:
    """
    Generate a new API key for the authenticated user.
    The plaintext key is returned ONCE here and never stored — only its bcrypt hash.
    """
    key = "ot_" + secrets.token_urlsafe(24)
    key_prefix = key[:12]
    key_hash = bcrypt.hashpw(key.encode(), bcrypt.gensalt(rounds=12)).decode()

    new_key = ApiKey(
        user_id=user_id,
        key_hash=key_hash,
        key_prefix=key_prefix,
    )
    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)

    return ApiKeyCreateResponse(
        id=new_key.id,
        key=key,           # plaintext key — included here and NEVER again
        key_prefix=key_prefix,
        created_at=new_key.created_at,
    )


@router.get("/keys", response_model=list[ApiKeyListItem])
async def list_api_keys(
    user_id: uuid.UUID = Depends(verify_supabase_jwt),
    db: AsyncSession = Depends(get_db),
) -> list[ApiKeyListItem]:
    """
    Return all active (non-revoked) API keys for the authenticated user.
    Never returns key_hash or the full plaintext key.
    """
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user_id)
        .where(ApiKey.revoked_at.is_(None))
        .order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [ApiKeyListItem.model_validate(k) for k in keys]


@router.delete("/keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: uuid.UUID,
    user_id: uuid.UUID = Depends(verify_supabase_jwt),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Revoke an API key by setting revoked_at = NOW().
    Returns 404 if the key doesn't exist, belongs to a different user, or is already revoked.
    This prevents leaking the existence of other users' keys and keeps revoked_at immutable.
    """
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.id == key_id)
        .where(ApiKey.user_id == user_id)
        .where(ApiKey.revoked_at.is_(None))
    )
    key = result.scalar_one_or_none()

    if key is None:
        raise HTTPException(status_code=404, detail="Not found")

    key.revoked_at = datetime.now(timezone.utc)
    await db.commit()
