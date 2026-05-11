"""Phase 1 baseline — intentionally empty.

This migration establishes the Alembic infrastructure for the
Python AI service's Postgres database. Domain tables are
introduced starting in Phase 4 (Python Ingestion & Indexing).

See .planning/ROADMAP.md and ADR-003.
"""

from collections.abc import Sequence

revision: str = "0001_empty_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
