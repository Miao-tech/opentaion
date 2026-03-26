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


@app.post("/debug/test-post")
async def debug_test_post() -> dict:
    return {"status": "ok", "method": "POST"}


@app.post("/v1/debug/test-post")
async def debug_test_post_v1() -> dict:
    return {"status": "ok", "method": "POST", "path": "/v1/"}


@app.get("/debug/openrouter")
async def debug_openrouter() -> dict:
    """Temporary: test OpenRouter connectivity."""
    import httpx
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        return {"error": "OPENROUTER_API_KEY not set"}
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": "meta-llama/llama-3.3-70b-instruct:free", "messages": [{"role": "user", "content": "hi"}]},
                timeout=30.0,
            )
        return {"status_code": r.status_code, "body": r.text[:300]}
    except Exception as e:
        return {"error": type(e).__name__, "detail": str(e)}


@app.get("/debug/verify-key")
async def debug_verify_key(key: str) -> dict:
    """Temporary: test API key verification against the DB."""
    try:
        from fastapi import HTTPException
        from opentaion_api.database import AsyncSessionLocal
        from opentaion_api.deps import verify_api_key
        async with AsyncSessionLocal() as db:
            result = await verify_api_key(authorization=f"Bearer {key}", db=db)
        return {"status": "ok", "user_id": str(result)}
    except Exception as e:
        return {"error": type(e).__name__, "detail": str(e)}


