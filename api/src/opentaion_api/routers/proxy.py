# api/src/opentaion_api/routers/proxy.py
import json
import os
import uuid

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response

from opentaion_api.database import AsyncSessionLocal
from opentaion_api.deps import verify_api_key
from opentaion_api.models import UsageLog
from opentaion_api.services.cost import compute_cost
from opentaion_api.services.providers import load_providers, resolve_provider

router = APIRouter()

# httpx timeout: 5s connect (catches Railway cold start), 120s read (reasoning models)
PROXY_TIMEOUT = httpx.Timeout(connect=5.0, read=120.0, write=5.0, pool=5.0)

DEFAULT_PROVIDER = os.environ.get("DEFAULT_PROVIDER", "openrouter")


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
    """Multi-provider proxy with async usage logging.

    1. Authenticates request via verify_api_key dependency
    2. Resolves provider from model name prefix (e.g. 'siliconflow/...' → SiliconFlow)
    3. Strips provider prefix from model name before forwarding
    4. Forwards request to resolved provider with key swap
    5. On success: enqueues write_usage_log as BackgroundTask (non-blocking)
    6. Returns provider response unmodified
    """
    body = await request.body()

    # Parse request body to extract model name for provider routing and usage logging
    try:
        body_json = json.loads(body)
        request_model = body_json.get("model", "")
    except Exception:
        body_json = None
        request_model = ""

    # Resolve provider from model prefix
    providers = load_providers()
    base_url, provider_api_key, forwarded_model = resolve_provider(
        request_model, providers, DEFAULT_PROVIDER
    )

    if not provider_api_key:
        raise HTTPException(status_code=500, detail="No LLM provider configured")

    # If the model prefix was stripped, update the request body
    if forwarded_model != request_model and body_json is not None:
        body_json["model"] = forwarded_model
        forward_body = json.dumps(body_json).encode()
    else:
        forward_body = body  # send raw bytes unchanged

    url = f"{base_url}/chat/completions"

    try:
        async with httpx.AsyncClient(trust_env=False) as client:
            provider_response = await client.post(
                url,
                content=forward_body,
                headers={
                    "Authorization": f"Bearer {provider_api_key}",
                    "Content-Type": request.headers.get("Content-Type", "application/json"),
                },
                timeout=PROXY_TIMEOUT,
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Upstream timeout")
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Upstream unreachable")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Unexpected error: {type(e).__name__}: {e}")

    if provider_response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Proxy error: {provider_response.status_code}",
        )

    # Extract token counts from the provider response (best-effort — falls back to 0).
    # model name is always request_model — preserves the provider prefix (e.g.
    # "siliconflow/Qwen/Qwen2.5-72B-Instruct") so usage logs show which provider
    # was used, regardless of what the response echoes back.
    prompt_tokens, completion_tokens = 0, 0
    content_type = provider_response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        for line in provider_response.text.splitlines():
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            try:
                chunk = json.loads(line[6:])
                usage = chunk.get("usage") or {}
                if usage.get("prompt_tokens"):
                    prompt_tokens = int(usage["prompt_tokens"])
                    completion_tokens = int(usage.get("completion_tokens", 0))
            except Exception:
                pass
    else:
        try:
            response_data = provider_response.json()
            usage = response_data.get("usage", {})
            prompt_tokens = int(usage.get("prompt_tokens", 0))
            completion_tokens = int(usage.get("completion_tokens", 0))
        except Exception:
            pass

    # Enqueue usage log write — response is returned to client before this executes (NFR9)
    background_tasks.add_task(
        write_usage_log,
        user_id,
        request_model,
        prompt_tokens,
        completion_tokens,
    )

    return Response(
        content=provider_response.content,
        status_code=provider_response.status_code,
        media_type=provider_response.headers.get("content-type", "application/json"),
    )
