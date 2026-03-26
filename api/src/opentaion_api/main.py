# src/opentaion_api/main.py
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from opentaion_api.routers import keys, proxy, usage

app = FastAPI(title="opentaion-api", version="0.1.0")

origins = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(keys.router, prefix="/api")
app.include_router(proxy.router)  # no prefix — endpoint is /v1/chat/completions
app.include_router(usage.router, prefix="/api")  # → GET /api/usage


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/debug/db")
async def debug_db() -> dict:
    """Temporary endpoint to diagnose DB connection."""
    try:
        from sqlalchemy import text
        from opentaion_api.database import engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/debug/db-insert")
async def debug_db_insert() -> dict:
    """Temporary endpoint to test DB INSERT into api_keys."""
    import secrets, uuid
    import bcrypt
    from opentaion_api.database import AsyncSessionLocal
    from opentaion_api.models import ApiKey
    try:
        key = "ot_" + secrets.token_urlsafe(24)
        key_hash = bcrypt.hashpw(key.encode(), bcrypt.gensalt(rounds=4)).decode()
        async with AsyncSessionLocal() as db:
            new_key = ApiKey(
                user_id=uuid.uuid4(),
                key_hash=key_hash,
                key_prefix=key[:12],
            )
            db.add(new_key)
            await db.commit()
        return {"status": "ok"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/debug/jwt-config")
async def debug_jwt_config() -> dict:
    """Temporary endpoint to diagnose JWT configuration. Remove after fix."""
    import os
    from jwt.algorithms import ECAlgorithm
    jwk_json = os.environ.get("SUPABASE_JWT_PUBLIC_KEY", "")
    if not jwk_json:
        return {"error": "SUPABASE_JWT_PUBLIC_KEY not set"}
    try:
        ECAlgorithm.from_jwk(jwk_json)
        return {"status": "ok", "key_length": len(jwk_json), "starts_with": jwk_json[:20]}
    except Exception as e:
        return {"error": str(e), "key_length": len(jwk_json), "starts_with": jwk_json[:20]}
