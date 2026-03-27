# src/opentaion_api/database.py
import os
from collections.abc import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()  # reads api/.env for local dev; no-op in Railway where env vars are set directly

_raw_url = os.environ.get("DATABASE_URL", "")
# Railway/Supabase provide postgresql:// — asyncpg requires postgresql+asyncpg://
DATABASE_URL = (
    _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if _raw_url.startswith("postgresql://")
    else _raw_url
)

# LOCAL=true disables SSL — Supabase local (Docker) does not use SSL
_local = os.environ.get("LOCAL", "").lower() in ("1", "true", "yes")
_connect_args: dict = {"timeout": 10, "statement_cache_size": 0}
if not _local:
    _connect_args["ssl"] = "require"

engine = create_async_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    echo=False,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
