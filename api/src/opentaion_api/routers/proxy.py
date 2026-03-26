# api/src/opentaion_api/routers/proxy.py
import os
import uuid

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response

from opentaion_api.database import AsyncSessionLocal
from opentaion_api.deps import verify_api_key
from opentaion_api.models import UsageLog
from opentaion_api.services.cost import compute_cost

router = APIRouter()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# httpx timeout: 5s connect (catches Railway cold start), 120s read (reasoning models)
PROXY_TIMEOUT = httpx.Timeout(connect=5.0, read=120.0, write=5.0, pool=5.0)


async def write_usage_log(
    user_id: uuid.UUID,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    """Write a usage record to usage_logs. Always called as a BackgroundTask.

    Opens its own DB session — the request-scoped session from get_db() is closed
    before background tasks run.
    Must NEVER propagate exceptions — any failure is logged to stdout only (NFR9).
    The CLI has already received its response before this function runs.
    """
    try:
        cost = compute_cost(model, prompt_tokens, completion_tokens)
        async with AsyncSessionLocal() as db:
            log = UsageLog(
                user_id=user_id,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost,
            )
            db.add(log)
            await db.commit()
    except Exception as exc:
        print(f"[WARNING] write_usage_log failed: {exc!r}")


@router.post("/v1/chat/completions")
async def proxy_chat_completions(
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: uuid.UUID = Depends(verify_api_key),
) -> Response:
    """Transparent proxy to OpenRouter with async usage logging.

    1. Authenticates request via verify_api_key dependency
    2. Forwards raw body bytes to OpenRouter with key swap
    3. On success: enqueues write_usage_log as BackgroundTask (non-blocking)
    4. Returns OpenRouter response unmodified
    """
    openrouter_api_key = os.environ["OPENROUTER_API_KEY"]
    body = await request.body()  # raw bytes — never JSON-parsed (NFR12)

    try:
        async with httpx.AsyncClient() as client:
            openrouter_response = await client.post(
                OPENROUTER_URL,
                content=body,
                headers={
                    "Authorization": f"Bearer {openrouter_api_key}",
                    "Content-Type": request.headers.get("Content-Type", "application/json"),
                },
                timeout=PROXY_TIMEOUT,
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Upstream timeout")
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Upstream unreachable")

    if openrouter_response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Proxy error: {openrouter_response.status_code}",
        )

    # Parse OpenRouter response for usage logging (best-effort — malformed response → log zeros)
    try:
        response_data = openrouter_response.json()
        model = response_data.get("model", "unknown")
        usage = response_data.get("usage", {})
        prompt_tokens = int(usage.get("prompt_tokens", 0))
        completion_tokens = int(usage.get("completion_tokens", 0))
    except Exception:
        model, prompt_tokens, completion_tokens = "unknown", 0, 0

    # Enqueue usage log write — response is returned to CLI before this executes (NFR9)
    background_tasks.add_task(
        write_usage_log,
        user_id,
        model,
        prompt_tokens,
        completion_tokens,
    )

    return Response(
        content=openrouter_response.content,
        status_code=openrouter_response.status_code,
        media_type=openrouter_response.headers.get("content-type", "application/json"),
    )
