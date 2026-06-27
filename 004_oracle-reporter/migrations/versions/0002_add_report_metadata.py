"""add report_runs audit table

Revision ID: 0002
Revises: 0001
Create Date: 2025-02-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Audit log for each CronJob execution
    op.create_table(
        "report_runs",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), primary_key=True),
        sa.Column("run_at", sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.Column("status", sa.String(20), nullable=False),  # success, error
        sa.Column("rows_processed", sa.Integer(), nullable=True),
        sa.Column("hdfs_path", sa.String(500), nullable=True),
        sa.Column("error_message", sa.String(2000), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("report_runs")
