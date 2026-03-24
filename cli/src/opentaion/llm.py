import asyncio
import httpx
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str


class OpenRouterClient:
    MAX_RETRIES = 3

    def __init__(self, api_key: str, model: str = "deepseek/deepseek-r1"):
        self.api_key = api_key
        self.model = model

    async def complete(self, prompt: str) -> LLMResponse:
        async with httpx.AsyncClient(trust_env=False) as client:
            for attempt in range(self.MAX_RETRIES):
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                if response.status_code == 429:
                    if attempt == self.MAX_RETRIES - 1:
                        raise RuntimeError(
                            f"Rate limit exceeded after {self.MAX_RETRIES} attempts"
                        )
                    retry_after = int(response.headers.get("Retry-After", 1))
                    await asyncio.sleep(retry_after)
                    continue
                data = await response.json()
                return LLMResponse(content=data["choices"][0]["message"]["content"])
