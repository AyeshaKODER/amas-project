"""${message}"""

revision = "${up_revision}"
down_revision = ${down_revision}
branch_labels = ${repr(branch_labels) if branch_labels else None}
depends_on = ${repr(depends_on) if depends_on else None}

from alembic import op
import sqlalchemy as sa

${imports if imports else ""}
def upgrade():
    ${upgrades if upgrades else "pass"}


def downgrade():
    ${downgrades if downgrades else "pass"}
