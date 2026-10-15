"""Revocable sessions and shared production authentication throttling."""

import sqlalchemy as sa

from alembic import op

revision = "20261015_0030"
down_revision = "20261015_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("session_version", sa.Integer(), server_default="0", nullable=False)
    )
    op.create_table(
        "auth_rate_limits",
        sa.Column("key_hash", sa.String(64), primary_key=True),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_auth_rate_limits_window_started_at", "auth_rate_limits", ["window_started_at"]
    )
    # Only the platform administrator may change the application-wide ML registry.
    op.execute(
        sa.text("""
        DELETE FROM role_permissions WHERE permission_id IN (
            SELECT id FROM permissions WHERE name IN ('ml:manage', 'ml:train')
        ) AND role_id IN (SELECT id FROM roles WHERE name <> 'ADMIN')
    """)
    )
    # Legacy unassigned staff can be bound only where the owner has exactly one
    # active institute. Ambiguous or invalid assignments remain blocked.
    op.execute(
        sa.text("""
        UPDATE users u SET school_institute_id = s.id
        FROM school_institutes s
        WHERE u.school_manager_id = s.manager_id AND u.school_institute_id IS NULL
          AND s.is_active AND (SELECT COUNT(*) FROM school_institutes x
                               WHERE x.manager_id = s.manager_id AND x.is_active) = 1
    """)
    )


def downgrade() -> None:
    raise RuntimeError("Security migration requires an explicit reviewed rollback")
