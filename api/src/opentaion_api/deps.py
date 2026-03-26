# src/opentaion_api/deps.py
import os
import uuid

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opentaion_api.database import get_db
from opentaion_api.models import ApiKey


async def verify_api_key(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    """
    Validate an OpenTalon API key from the Authorization header.

    Flow: parse key → prefix lookup (indexed) → bcrypt.checkpw → revocation check
    Cost factor 12 is set during key GENERATION (Story 2.2, bcrypt.gensalt(rounds=12)).
    checkpw timing is determined by the cost factor embedded in the stored hash.

    Used by: POST /v1/chat/completions (Story 3.2) — called on every proxy request.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    key = authorization.removeprefix("Bearer ").strip()

    if not key.startswith("ot_") or len(key) != 35:
        raise HTTPException(status_code=401, detail="Unauthorized")

    prefix = key[:12]

    result = await db.execute(select(ApiKey).where(ApiKey.key_prefix == prefix))
    candidates = result.scalars().all()

    for candidate in candidates:
        if bcrypt.checkpw(key.encode(), candidate.key_hash.encode()):
            if candidate.revoked_at is not None:
                continue  # matched but revoked — keep checking remaining candidates
            return candidate.user_id

    raise HTTPException(status_code=401, detail="Unauthorized")


async def verify_supabase_jwt(
    authorization: str | None = Header(default=None),
) -> uuid.UUID:
    """
    Validate a Supabase Auth JWT from the Authorization header.

    Verifies signature against SUPABASE_JWT_PUBLIC_KEY (RS256 JWK).
    Supabase user tokens always have aud="authenticated".
    Extracts the `sub` claim (user UUID) and returns it.

    Used by: POST/GET/DELETE /api/keys (Story 2.2), GET /api/usage (Story 4.1)
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = authorization.removeprefix("Bearer ").strip()

    jwk_json = os.environ.get("SUPABASE_JWT_PUBLIC_KEY", "")
    if not jwk_json:
        raise HTTPException(status_code=500, detail="Server configuration error")

    try:
        from jwt.algorithms import ECAlgorithm
        public_key = ECAlgorithm.from_jwk(jwk_json)
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["ES256"],
            audience="authenticated",
        )
        return uuid.UUID(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
