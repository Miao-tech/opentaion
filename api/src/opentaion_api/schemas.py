# src/opentaion_api/schemas.py
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from opentaion_api.models import UsageLog


class ApiKeyCreateResponse(BaseModel):
    """Response for POST /api/keys — contains the plaintext key (shown ONCE only)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str           # full plaintext key — only returned at creation, never again
    key_prefix: str
    created_at: datetime


class ApiKeyListItem(BaseModel):
    """One entry in GET /api/keys — NO key_hash, NO full key."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key_prefix: str
    created_at: datetime


class UsageRecord(BaseModel):
    """One usage_logs row, date-truncated and cost serialized as string."""
    date: str              # "YYYY-MM-DD" extracted from created_at
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: str          # Decimal serialized as 8-dp string — never float

    @classmethod
    def from_log(cls, log: "UsageLog") -> "UsageRecord":
        return cls(
            date=log.created_at.strftime("%Y-%m-%d"),
            model=log.model,
            prompt_tokens=log.prompt_tokens,
            completion_tokens=log.completion_tokens,
            cost_usd=f"{log.cost_usd:.8f}",
        )


class UsageResponse(BaseModel):
    """Response shape for GET /api/usage."""
    records: list[UsageRecord]
    total_cost_usd: str    # sum of all cost_usd, 8 decimal places
    period_days: int = 30
