# src/opentaion_api/deps.py
"""
Authentication dependency placeholders.
Implemented fully in Story 2.1.
"""
import uuid
from fastapi import HTTPException, Header


async def verify_api_key(
    authorization: str = Header(...),
) -> uuid.UUID:
    """Validates OpenTalon API key (bcrypt). Implemented in Story 2.1."""
    raise HTTPException(status_code=501, detail="Not implemented")


async def verify_supabase_jwt(
    authorization: str = Header(...),
) -> uuid.UUID:
    """Validates Supabase JWT for web routes. Implemented in Story 2.1."""
    raise HTTPException(status_code=501, detail="Not implemented")
