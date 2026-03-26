# api/tests/conftest.py
import os

# Provide a parseable (but unconnectable) DATABASE_URL so create_async_engine()
# does not raise ArgumentError during test collection when DATABASE_URL is unset.
# All tests that use the database override get_db via dependency_overrides.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
