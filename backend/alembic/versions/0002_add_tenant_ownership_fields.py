"""Add tenant ownership fields and workflows table.

Revision ID: 0002_tenant_ownership
Revises: 0001_initial
Create Date: 2026-11-15 13:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_tenant_ownership"
down_revision: str | None = "0001_initial"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create workflows table for tenancy-scoped workflow definitions
    op.create_table(
        "workflows",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "name", name="uq_workflows_user_name"),
    )
    op.create_index("ix_workflows_user_id", "workflows", ["user_id"], unique=False)
    op.create_index("ix_workflows_name", "workflows", ["name"], unique=False)

    # 2. Add tenant ownership to integrations table
    with op.batch_alter_table("integrations") as batch_op:
        batch_op.add_column(
            sa.Column("user_id", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.create_foreign_key(
            "fk_integrations_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index("ix_integrations_user_id", ["user_id"], unique=False)
        # Drop legacy global uniqueness on name and replace with per-tenant uniqueness
        batch_op.drop_index("ix_integrations_name")
        batch_op.create_index("ix_integrations_name", ["name"], unique=False)
        batch_op.create_unique_constraint(
            "uq_integrations_user_name", ["user_id", "name"]
        )

    # 3. Add tenant user_id reference to agents table
    with op.batch_alter_table("agents") as batch_op:
        batch_op.add_column(
            sa.Column("user_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_agents_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index("ix_agents_user_id", ["user_id"], unique=False)

    # 4. Add tenant user_id reference to tasks table
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(
            sa.Column("user_id", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.create_foreign_key(
            "fk_tasks_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index("ix_tasks_user_id", ["user_id"], unique=False)


def downgrade() -> None:
    # 4. Remove user_id from tasks
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_index("ix_tasks_user_id")
        batch_op.drop_constraint("fk_tasks_user_id_users", type_="foreignkey")
        batch_op.drop_column("user_id")

    # 3. Remove user_id from agents
    with op.batch_alter_table("agents") as batch_op:
        batch_op.drop_index("ix_agents_user_id")
        batch_op.drop_constraint("fk_agents_user_id_users", type_="foreignkey")
        batch_op.drop_column("user_id")

    # 2. Remove user_id and restore global unique index on integrations
    with op.batch_alter_table("integrations") as batch_op:
        batch_op.drop_constraint("uq_integrations_user_name", type_="unique")
        batch_op.drop_index("ix_integrations_user_id")
        batch_op.drop_index("ix_integrations_name")
        batch_op.create_index("ix_integrations_name", ["name"], unique=True)
        batch_op.drop_constraint("fk_integrations_user_id_users", type_="foreignkey")
        batch_op.drop_column("user_id")

    # 1. Drop workflows table
    op.drop_index("ix_workflows_name", table_name="workflows")
    op.drop_index("ix_workflows_user_id", table_name="workflows")
    op.drop_table("workflows")
