# API — Component Rules

## Environment
- Package manager: uv
- Run: `uv run uvicorn opentaion_api.main:app --reload`
- Run tests: `uv run pytest tests/ -v`

## FastAPI conventions
- All routes return typed Pydantic response models — never raw dicts
- Endpoint paths: hyphenated, noun-first (`/usage-records`, `/api-keys`)
- Auth: extract current user via `Depends(get_current_user)` — no manual header reads

## SQLAlchemy conventions
- All database operations use async sessions
- One model file per resource in models/
- Migrations via Alembic — never modify the database schema manually

## Anti-patterns (IMPORTANT)
- Never commit connection strings — use environment variables
- Never write raw SQL — use SQLAlchemy query API
- Never return HTTP 200 with an error body — use correct status codes