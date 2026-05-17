from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

metadata = sa.MetaData()

processed_events = sa.Table(
    "processed_events",
    metadata,
    sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("event_type", sa.String(length=64), nullable=False),
    sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
)

document_index_state = sa.Table(
    "document_index_state",
    metadata,
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

document_chunks_parent = sa.Table(
    "document_chunks_parent",
    metadata,
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
    sa.Index("idx_document_chunks_parent_document_id", "document_id"),
)

