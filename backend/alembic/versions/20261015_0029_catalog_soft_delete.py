"""Recoverable removal of school catalog items without changing student records."""

import sqlalchemy as sa

from alembic import op

revision = "20261015_0029"
down_revision = "20261015_0028"
branch_labels = None
depends_on = None
TABLES = ("school_courses", "school_special_supports", "school_exam_plans")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(
            table, sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False)
        )


def downgrade() -> None:
    for table in TABLES:
        if op.get_bind().scalar(sa.text(f"SELECT COUNT(*) FROM {table} WHERE is_deleted")):
            raise RuntimeError("Restore deleted catalog items before downgrading")
    for table in TABLES:
        op.drop_column(table, "is_deleted")
