"""Add ingestion idempotency, state, and parent chunk tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_ingestion_state"
down_revision: str | None = "0001_empty_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "processed_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "document_index_state",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_indexed_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_failure_stage", sa.String(length=64), nullable=True),
        sa.Column("last_failure_code", sa.String(length=128), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('PENDING', 'INDEXING', 'INDEXED', 'FAILED', 'DELETED')",
            name="ck_document_index_state_status",
        ),
    )

    op.create_table(
        "document_chunks_parent",
        sa.Column("parent_chunk_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "section_path",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("position >= 0", name="ck_document_chunks_parent_position_non_negative"),
        sa.CheckConstraint("token_count >= 0", name="ck_document_chunks_parent_token_count_non_negative"),
    )
    op.create_index(
        "idx_document_chunks_parent_document_id",
        "document_chunks_parent",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_document_chunks_parent_document_id", table_name="document_chunks_parent")
    op.drop_table("document_chunks_parent")
    op.drop_table("document_index_state")
    op.drop_table("processed_events")
