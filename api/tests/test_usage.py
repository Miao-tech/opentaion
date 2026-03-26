# tests/test_usage.py
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport

from opentaion_api.main import app
from opentaion_api.deps import verify_supabase_jwt
from opentaion_api.database import get_db


TEST_USER_ID = uuid.uuid4()


@pytest.fixture(autouse=True)
def override_auth():
    """Use JWT auth override for all tests in this file."""
    app.dependency_overrides[verify_supabase_jwt] = lambda: TEST_USER_ID
    yield
    app.dependency_overrides.clear()


def make_log(
    model: str = "deepseek/deepseek-r1:free",
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    cost_usd: Decimal = Decimal("0.00000000"),
    days_ago: int = 1,
) -> MagicMock:
    """Build a mock UsageLog ORM object."""
    log = MagicMock()
    log.user_id = TEST_USER_ID
    log.model = model
    log.prompt_tokens = prompt_tokens
    log.completion_tokens = completion_tokens
    log.cost_usd = cost_usd
    log.created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return log


def make_db_with_logs(logs: list) -> AsyncMock:
    """Create a mock AsyncSession that returns logs on execute()."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = logs

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_db


# ── Populated result ──────────────────────────────────────────────────────────

async def test_get_usage_returns_200():
    logs = [make_log(prompt_tokens=100, completion_tokens=50)]
    app.dependency_overrides[get_db] = lambda: make_db_with_logs(logs)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/usage",
            headers={"Authorization": "Bearer fake-jwt"},
        )
    assert response.status_code == 200


async def test_get_usage_response_shape():
    logs = [make_log(model="deepseek/deepseek-r1:free", prompt_tokens=1200, completion_tokens=800)]
    app.dependency_overrides[get_db] = lambda: make_db_with_logs(logs)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/usage", headers={"Authorization": "Bearer fake-jwt"})

    data = response.json()
    assert "records" in data
    assert "total_cost_usd" in data
    assert "period_days" in data
    assert data["period_days"] == 30


async def test_get_usage_record_fields():
    logs = [make_log(
        model="deepseek/deepseek-r1:free",
        prompt_tokens=1200,
        completion_tokens=800,
        days_ago=2,
    )]
    app.dependency_overrides[get_db] = lambda: make_db_with_logs(logs)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/usage", headers={"Authorization": "Bearer fake-jwt"})

    record = response.json()["records"][0]
    assert "date" in record
    assert "model" in record
    assert "prompt_tokens" in record
    assert "completion_tokens" in record
    assert "cost_usd" in record
    assert record["model"] == "deepseek/deepseek-r1:free"
    assert record["prompt_tokens"] == 1200
    assert record["completion_tokens"] == 800


async def test_get_usage_date_field_format():
    """date must be 'YYYY-MM-DD' string, not a datetime."""
    logs = [make_log(days_ago=5)]
    app.dependency_overrides[get_db] = lambda: make_db_with_logs(logs)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/usage", headers={"Authorization": "Bearer fake-jwt"})

    date_str = response.json()["records"][0]["date"]
    # Must be YYYY-MM-DD format (10 chars, no time component)
    assert len(date_str) == 10
    assert date_str[4] == "-" and date_str[7] == "-"


# ── Decimal string serialization ──────────────────────────────────────────────

async def test_cost_usd_is_string_not_number():
    logs = [make_log(cost_usd=Decimal("0.00120000"))]
    app.dependency_overrides[get_db] = lambda: make_db_with_logs(logs)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/usage", headers={"Authorization": "Bearer fake-jwt"})

    record = response.json()["records"][0]
    # cost_usd must be a JSON string, not a JSON number
    assert isinstance(record["cost_usd"], str)


async def test_cost_usd_has_eight_decimal_places():
    logs = [make_log(cost_usd=Decimal("0.00120000"))]
    app.dependency_overrides[get_db] = lambda: make_db_with_logs(logs)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/usage", headers={"Authorization": "Bearer fake-jwt"})

    cost_str = response.json()["records"][0]["cost_usd"]
    # Must have exactly 8 decimal places
    decimal_part = cost_str.split(".")[1]
    assert len(decimal_part) == 8


async def test_total_cost_usd_is_string_not_number():
    logs = [make_log(cost_usd=Decimal("0.00050000")), make_log(cost_usd=Decimal("0.00070000"))]
    app.dependency_overrides[get_db] = lambda: make_db_with_logs(logs)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/usage", headers={"Authorization": "Bearer fake-jwt"})

    assert isinstance(response.json()["total_cost_usd"], str)


async def test_total_cost_usd_sums_correctly():
    logs = [
        make_log(cost_usd=Decimal("0.00050000")),
        make_log(cost_usd=Decimal("0.00070000")),
    ]
    app.dependency_overrides[get_db] = lambda: make_db_with_logs(logs)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/usage", headers={"Authorization": "Bearer fake-jwt"})

    assert response.json()["total_cost_usd"] == "0.00120000"


# ── Empty result ───────────────────────────────────────────────────────────────

async def test_get_usage_empty_result():
    app.dependency_overrides[get_db] = lambda: make_db_with_logs([])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/usage", headers={"Authorization": "Bearer fake-jwt"})

    assert response.status_code == 200
    data = response.json()
    assert data["records"] == []
    assert data["total_cost_usd"] == "0.00000000"
    assert data["period_days"] == 30


# ── Auth required ─────────────────────────────────────────────────────────────

async def test_get_usage_requires_auth():
    """Without auth override, real verify_supabase_jwt should reject."""
    app.dependency_overrides.pop(verify_supabase_jwt, None)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/usage")  # no Authorization header

        assert response.status_code == 401
    finally:
        app.dependency_overrides[verify_supabase_jwt] = lambda: TEST_USER_ID
