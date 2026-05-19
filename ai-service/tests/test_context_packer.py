from __future__ import annotations

from uuid import UUID

from corp_rag_ai.domain.ingestion_state import ParentChunkRecord
from corp_rag_ai.domain.retrieval import RetrievalCandidate, RetrieverType
from corp_rag_ai.pipeline.retrieval.context_packer import OVERSIZED_PARENT_TRUNCATED, ContextPacker
from corp_rag_ai.pipeline.retrieval.parent_resolver import ParentResolution, ResolvedParentContext


DOCUMENT_ID = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
PARENT_A = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
PARENT_B = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
CHILD_A = UUID("11111111-1111-4111-8111-111111111042")
CHILD_B = UUID("22222222-2222-4222-8222-222222222017")


def test_context_packer_uses_xml_evidence_boundaries_and_child_citation_ids() -> None:
    child_a = _candidate(CHILD_A, PARENT_A, "Child A quote", 0.9)
    child_b = _candidate(CHILD_B, PARENT_B, "Child B quote", 0.8)
    resolution = ParentResolution(
        contexts=(
            ResolvedParentContext(parent=_parent(PARENT_A, "Parent A context"), children=(child_a,), max_child_score=0.9),
            ResolvedParentContext(parent=_parent(PARENT_B, "Parent B context"), children=(child_b,), max_child_score=0.8),
        ),
        citation_candidates=(child_a, child_b),
    )

    packed = ContextPacker(token_cap=4000).pack(resolution, (child_a, child_b))

    assert packed.text.startswith("<evidence>")
    assert '<source index="1" parentChunkId="' in packed.text
    assert "<text>Parent A context</text>" in packed.text
    assert [citation.chunk_id for citation in packed.citations] == [CHILD_A, CHILD_B]
    assert all(citation.chunk_id not in {PARENT_A, PARENT_B} for citation in packed.citations)
    assert [citation.quote for citation in packed.citations] == ["Child A quote", "Child B quote"]


def test_context_packer_prefers_parent_boundaries_and_truncates_single_oversized_parent() -> None:
    child_a = _candidate(CHILD_A, PARENT_A, "Child A quote", 0.9)
    oversized = " ".join(f"token{i}" for i in range(300))
    resolution = ParentResolution(
        contexts=(ResolvedParentContext(parent=_parent(PARENT_A, oversized), children=(child_a,), max_child_score=0.9),),
        citation_candidates=(child_a,),
    )

    packed = ContextPacker(token_cap=80).pack(resolution, (child_a,))

    assert OVERSIZED_PARENT_TRUNCATED in packed.warnings
    assert packed.citations[0].chunk_id == CHILD_A
    assert "token299" not in packed.text


def _parent(parent_id: UUID, content: str) -> ParentChunkRecord:
    return ParentChunkRecord(
        parent_chunk_id=parent_id,
        document_id=DOCUMENT_ID,
        section_path=("HR", "Leave"),
        content=content,
        position=0,
        token_count=10,
    )


def _candidate(chunk_id: UUID, parent_id: UUID, content: str, score: float) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=chunk_id,
        parent_chunk_id=parent_id,
        document_id=DOCUMENT_ID,
        document_title="Vacation Policy",
        section_path=("HR", "Leave"),
        content=content,
        snippet=content,
        score=score,
        access_level="INTERNAL",
        retriever=RetrieverType.HYBRID,
    )
