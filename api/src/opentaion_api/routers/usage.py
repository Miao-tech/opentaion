# api/src/opentaion_api/routers/usage.py
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opentaion_api.database import get_db
from opentaion_api.deps import verify_supabase_jwt
from opentaion_api.models import UsageLog
from opentaion_api.schemas import UsageRecord, UsageResponse

router = APIRouter()


@router.get("/usage")
async def get_usage(
    user_id: uuid.UUID = Depends(verify_supabase_jwt),
    db: AsyncSession = Depends(get_db),
) -> UsageResponse:
    """Return all usage_logs records for the authenticated user from the last 30 days.

    Ordered by created_at DESC — most recent first.
    Uses idx_usage_logs_user_date index on (user_id, created_at DESC).
    """
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    result = await db.execute(
        select(UsageLog)
        .where(UsageLog.user_id == user_id)
        .where(UsageLog.created_at >= thirty_days_ago)
        .order_by(UsageLog.created_at.desc())
    )
    logs = result.scalars().all()

    records = [UsageRecord.from_log(log) for log in logs]

    # Sum cost_usd (Decimal) across all records
    total_cost: Decimal = sum(
        (log.cost_usd for log in logs), Decimal("0")
    )

    return UsageResponse(
        records=records,
        total_cost_usd=f"{total_cost:.8f}",
        period_days=30,
    )
