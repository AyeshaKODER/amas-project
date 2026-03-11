"""add created_at to agents (safe conditional)

This migration uses ALTER TABLE ... ADD COLUMN IF NOT EXISTS so it will not
fail when the column already exists.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b37f24ebf420'
down_revision = 'd91b9b509159'
branch_labels = None
depends_on = None

def upgrade():
    # Single-line SQL string avoids quoting/escape problems.
    op.execute("ALTER TABLE agents ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL;")

def downgrade():
    # Drop only if exists - use single-line SQL string.
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = 'agents' AND column_name = 'created_at') THEN ALTER TABLE agents DROP COLUMN IF EXISTS created_at; END IF; END $$;")


