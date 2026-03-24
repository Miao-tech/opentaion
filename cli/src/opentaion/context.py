import tiktoken


class ContextManager:
    def __init__(self, max_tokens: int, model: str = "gpt-4o"):
        self.max_tokens = max_tokens
        self._enc = tiktoken.encoding_for_model(model)
        self._system_prompt: dict | None = None
        self._messages: list[dict] = []

    def _count(self, message: dict) -> int:
        return len(self._enc.encode(message["role"] + message["content"]))

    def set_system_prompt(self, content: str) -> None:
        self._system_prompt = {"role": "system", "content": content}

    def add(self, message: dict) -> None:
        self._messages.append(message)
        self._truncate()

    def _system_tokens(self) -> int:
        return self._count(self._system_prompt) if self._system_prompt else 0

    def _truncate(self) -> None:
        budget = self.max_tokens - self._system_tokens()
        # Drop oldest messages until we fit; always keep the last message
        while len(self._messages) > 1:
            total = sum(self._count(m) for m in self._messages)
            if total <= budget:
                break
            self._messages.pop(0)

    def get_messages(self) -> list[dict]:
        messages = []
        if self._system_prompt:
            messages.append(self._system_prompt)
        messages.extend(self._messages)
        return messages

    def total_tokens(self) -> int:
        return self._system_tokens() + sum(self._count(m) for m in self._messages)
