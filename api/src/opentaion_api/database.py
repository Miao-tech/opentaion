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

engine = create_async_engine(
    DATABASE_URL,
    connect_args={"ssl": "require", "timeout": 10, "statement_cache_size": 0},
    echo=False,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
