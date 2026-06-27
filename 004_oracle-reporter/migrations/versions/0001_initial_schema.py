"""initial Oracle schema for oracle-reporter

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00

Oracle-specific notes:
  - VARCHAR2 instead of VARCHAR (Oracle convention, same behaviour)
  - NUMBER instead of FLOAT (Oracle native numeric type)
  - Sequences for auto-increment (Oracle 12c+ supports GENERATED AS IDENTITY,
    but explicit sequences are shown here for compatibility with older Oracle 11g)
  - No AUTOCOMMIT — Alembic wraps DDL in transactions where Oracle allows it
    (Oracle auto-commits DDL, so CREATE TABLE is always immediately effective)
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Spark risk results — written by spark-calculator, read by oracle-reporter
    op.create_table(
        "spark_risk_results",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), primary_key=True),
        sa.Column("portfolio_id", sa.String(100), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("scenario", sa.String(50), nullable=False),
        sa.Column("risk_score", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("var_95", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("var_99", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("calculated_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
        # Unique constraint: one result per portfolio/model/scenario/date
        sa.UniqueConstraint(
            "portfolio_id", "model_version", "scenario", "calculated_date",
            name="uq_spark_risk_results"
        ),
    )
    # Index on portfolio_id + calculated_date for the CronJob's range queries
    op.create_index(
        "ix_spark_risk_results_portfolio_date",
        "spark_risk_results",
        ["portfolio_id", "calculated_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_spark_risk_results_portfolio_date", "spark_risk_results")
    op.drop_table("spark_risk_results")
