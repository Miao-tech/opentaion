"""create api keys and usage logs

Revision ID: 88a7cdb79508
Revises: 
Create Date: 2026-03-24 18:17:48.529359

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '88a7cdb79508'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── api_keys ───────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE public.api_keys (
            id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            key_hash    TEXT        NOT NULL,
            key_prefix  TEXT        NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            revoked_at  TIMESTAMPTZ NULL
        )
    """)
    op.execute("CREATE INDEX idx_api_keys_prefix ON public.api_keys (key_prefix)")
    op.execute("CREATE INDEX idx_api_keys_user   ON public.api_keys (user_id)")

    # ── usage_logs ─────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE public.usage_logs (
            id                UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id           UUID          NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            model             TEXT          NOT NULL,
            prompt_tokens     INTEGER       NOT NULL,
            completion_tokens INTEGER       NOT NULL,
            cost_usd          NUMERIC(10,8) NOT NULL,
            created_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_usage_logs_user_date ON public.usage_logs (user_id, created_at DESC)")

    # ── RLS ───────────────────────────────────────────────────────────────────
    op.execute("ALTER TABLE public.api_keys   ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.usage_logs ENABLE ROW LEVEL SECURITY")

    # api_keys policies — authenticated web users manage their own keys
    op.execute("""
        CREATE POLICY "Users can view own keys"
        ON public.api_keys FOR SELECT
        USING (auth.uid() = user_id)
    """)
    op.execute("""
        CREATE POLICY "Users can create own keys"
        ON public.api_keys FOR INSERT
        WITH CHECK (auth.uid() = user_id)
    """)
    op.execute("""
        CREATE POLICY "Users can revoke own keys"
        ON public.api_keys FOR UPDATE
        USING (auth.uid() = user_id)
        WITH CHECK (auth.uid() = user_id)
    """)
    # Column-level restriction: revoke broad UPDATE, grant only revoked_at
    op.execute("REVOKE UPDATE ON public.api_keys FROM authenticated")
    op.execute("GRANT UPDATE (revoked_at) ON public.api_keys TO authenticated")

    # usage_logs policies — web users can read; INSERT is service-role-only (no INSERT policy)
    op.execute("""
        CREATE POLICY "Users can view own usage"
        ON public.usage_logs FOR SELECT
        USING (auth.uid() = user_id)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.usage_logs")
    op.execute("DROP TABLE IF EXISTS public.api_keys")
