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


@app.get("/debug/jwt-config")
async def debug_jwt_config() -> dict:
    """Temporary endpoint to diagnose JWT configuration. Remove after fix."""
    import os
    from jwt.algorithms import RSAAlgorithm
    jwk_json = os.environ.get("SUPABASE_JWT_PUBLIC_KEY", "")
    if not jwk_json:
        return {"error": "SUPABASE_JWT_PUBLIC_KEY not set"}
    try:
        RSAAlgorithm.from_jwk(jwk_json)
        return {"status": "ok", "key_length": len(jwk_json), "starts_with": jwk_json[:20]}
    except Exception as e:
        return {"error": str(e), "key_length": len(jwk_json), "starts_with": jwk_json[:20]}
