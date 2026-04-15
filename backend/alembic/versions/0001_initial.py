"""initial schema: scans, findings, module_runs, domain_cache

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    scan_status = postgresql.ENUM(
        "pending", "running", "done", "failed",
        name="scan_status",
    )
    module_status = postgresql.ENUM(
        "pending", "running", "done", "failed", "skipped",
        name="module_status",
    )
    severity = postgresql.ENUM(
        "info", "low", "medium", "high", "critical",
        name="severity",
    )
    scan_status.create(op.get_bind(), checkfirst=True)
    module_status.create(op.get_bind(), checkfirst=True)
    severity.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("domain", sa.String(253), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="scan_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_by", sa.String(64), nullable=True),
    )
    op.create_index("ix_scans_domain", "scans", ["domain"])

    op.create_table(
        "findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "scan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("module", sa.String(64), nullable=False),
        sa.Column(
            "severity",
            postgresql.ENUM(name="severity", create_type=False),
            nullable=False,
            server_default="info",
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column(
            "data",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_findings_scan_id", "findings", ["scan_id"])
    op.create_index("ix_findings_module", "findings", ["module"])

    op.create_table(
        "module_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "scan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("module", sa.String(64), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="module_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_module_runs_scan_id", "module_runs", ["scan_id"])

    op.create_table(
        "domain_cache",
        sa.Column("domain", sa.String(253), primary_key=True),
        sa.Column("module", sa.String(64), primary_key=True),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_domain_cache_expires_at", "domain_cache", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_domain_cache_expires_at", table_name="domain_cache")
    op.drop_table("domain_cache")
    op.drop_index("ix_module_runs_scan_id", table_name="module_runs")
    op.drop_table("module_runs")
    op.drop_index("ix_findings_module", table_name="findings")
    op.drop_index("ix_findings_scan_id", table_name="findings")
    op.drop_table("findings")
    op.drop_index("ix_scans_domain", table_name="scans")
    op.drop_table("scans")

    bind = op.get_bind()
    postgresql.ENUM(name="severity").drop(bind, checkfirst=True)
    postgresql.ENUM(name="module_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="scan_status").drop(bind, checkfirst=True)
