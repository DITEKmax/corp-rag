from __future__ import annotations

from uuid import UUID

from corp_rag_ai.domain.ingestion_state import ParentChunkRecord
from corp_rag_ai.domain.retrieval import RetrievalCandidate, RetrieverType
from corp_rag_ai.pipeline.retrieval.parent_resolver import MISSING_PARENT_WARNING, ParentResolver


DOCUMENT_ID = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
PARENT_A = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
PARENT_B = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
CHILD_A = UUID("11111111-1111-4111-8111-111111111042")
CHILD_B = UUID("22222222-2222-4222-8222-222222222017")
MISSING_PARENT = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


async def test_parent_resolver_dedupes_orders_by_max_child_score_and_preserves_child_citations() -> None:
    repo = _ParentRepo(
        {
            PARENT_A: _parent(PARENT_A, "Parent A", position=0),
            PARENT_B: _parent(PARENT_B, "Parent B", position=1),
        }
    )
    resolver = ParentResolver(repo)
    low = _candidate(CHILD_A, parent_id=PARENT_A, score=0.4)
    high = _candidate(CHILD_B, parent_id=PARENT_B, score=0.9)
    sibling = _candidate(UUID("33333333-3333-4333-8333-333333333333"), parent_id=PARENT_A, score=0.7)

    result = await resolver.resolve((low, high, sibling))

    assert repo.requested_parent_ids == (PARENT_A, PARENT_B)
    assert [context.parent.parent_chunk_id for context in result.contexts] == [PARENT_B, PARENT_A]
    assert result.contexts[1].children == (low, sibling)
    assert result.citation_candidates == (low, high, sibling)
    assert result.warnings == ()


async def test_missing_parent_warns_and_excludes_only_that_parent_from_context() -> None:
    resolver = ParentResolver(_ParentRepo({PARENT_A: _parent(PARENT_A, "Parent A")}))
    usable = _candidate(CHILD_A, parent_id=PARENT_A, score=0.8)
    missing = _candidate(CHILD_B, parent_id=MISSING_PARENT, score=0.9)

    result = await resolver.resolve((usable, missing))

    assert [context.parent.parent_chunk_id for context in result.contexts] == [PARENT_A]
    assert result.citation_candidates == (usable,)
    assert result.warnings == (f"{MISSING_PARENT_WARNING}:{MISSING_PARENT}",)


class _ParentRepo:
    def __init__(self, parents: dict[UUID, ParentChunkRecord]) -> None:
        self.parents = parents
        self.requested_parent_ids: tuple[UUID, ...] = ()

    async def get_by_parent_ids(self, parent_ids: tuple[UUID, ...]) -> dict[UUID, ParentChunkRecord]:
        self.requested_parent_ids = parent_ids
        return {parent_id: self.parents[parent_id] for parent_id in parent_ids if parent_id in self.parents}


def _parent(parent_id: UUID, content: str, *, position: int = 0) -> ParentChunkRecord:
    return ParentChunkRecord(
        parent_chunk_id=parent_id,
        document_id=DOCUMENT_ID,
        section_path=("HR",),
        content=content,
        position=position,
        token_count=10,
    )


def _candidate(chunk_id: UUID, *, parent_id: UUID, score: float) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=chunk_id,
        parent_chunk_id=parent_id,
        document_id=DOCUMENT_ID,
        document_title="Vacation Policy",
        section_path=("HR",),
        content="Child content",
        score=score,
        access_level="INTERNAL",
        retriever=RetrieverType.HYBRID,
    )
