from __future__ import annotations

from uuid import UUID

from corp_rag_ai.domain.guard import GuardReason
from corp_rag_ai.domain.retrieval import CitationDraft, RetrievalCandidate, RetrieverType
from corp_rag_ai.pipeline.generation.synthesizer import SynthesisResult
from corp_rag_ai.pipeline.guards.output_guard import OutputGuard


DOCUMENT_ID = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
CHUNK_ID = UUID("11111111-1111-4111-8111-111111111042")
PARENT_ID = UUID("22222222-2222-4222-8222-222222222017")


def test_invalid_citation_refs_are_blocked() -> None:
    verdict = OutputGuard().validate(
        SynthesisResult(answered=True, answer="The policy says this [4].", citation_indexes=(4,), confidence_hint=0.8),
        citations=(_citation(), _citation(chunk_id=UUID("33333333-3333-4333-8333-333333333333"))),
        evidence=(_candidate(),),
    )

    assert verdict.blocked is True
    assert verdict.reason is GuardReason.INVALID_CITATIONS


def test_factual_answer_without_refs_is_blocked_for_missing_citations() -> None:
    verdict = OutputGuard().validate(
        SynthesisResult(answered=True, answer="Employees receive annual leave after approval.", citation_indexes=(), confidence_hint=0.8),
        citations=(_citation(),),
        evidence=(_candidate(),),
    )

    assert verdict.blocked is True
    assert verdict.reason is GuardReason.MISSING_CITATIONS


def test_aggregation_answer_still_requires_citations() -> None:
    verdict = OutputGuard().validate(
        SynthesisResult(answered=True, answer="There are 12 matching policies.", citation_indexes=(), confidence_hint=0.8),
        citations=(_citation(),),
        evidence=(_candidate(),),
    )

    assert verdict.blocked is True
    assert verdict.reason is GuardReason.MISSING_CITATIONS


def test_secret_like_output_is_blocked() -> None:
    verdict = OutputGuard().validate(
        SynthesisResult(answered=True, answer="Use api_key = sk-test-secret-value [1].", citation_indexes=(1,), confidence_hint=0.8),
        citations=(_citation(),),
        evidence=(_candidate(),),
    )

    assert verdict.blocked is True
    assert verdict.reason is GuardReason.LEAK_PATTERN


def test_unsafe_evidence_only_forces_refusal() -> None:
    verdict = OutputGuard().validate(
        SynthesisResult(answered=True, answer="Policy says this [1].", citation_indexes=(1,), confidence_hint=0.8),
        citations=(_citation(),),
        evidence=(_candidate(sanitizer_flags=("PROMPT_IGNORE_INSTRUCTIONS",)),),
    )

    assert verdict.blocked is True
    assert verdict.reason is GuardReason.UNSAFE_EVIDENCE_ONLY


def test_valid_cited_answer_passes() -> None:
    verdict = OutputGuard().validate(
        SynthesisResult(answered=True, answer="Policy says this [1].", citation_indexes=(1,), confidence_hint=0.8),
        citations=(_citation(),),
        evidence=(_candidate(),),
    )

    assert verdict.safe is True


def _citation(*, chunk_id: UUID = CHUNK_ID) -> CitationDraft:
    return CitationDraft(
        document_id=DOCUMENT_ID,
        document_title="Vacation Policy",
        chunk_id=chunk_id,
        section_path=("HR",),
        quote="Policy says this.",
        score=0.8,
        access_level="INTERNAL",
    )


def _candidate(*, sanitizer_flags: tuple[str, ...] = ()) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=CHUNK_ID,
        parent_chunk_id=PARENT_ID,
        document_id=DOCUMENT_ID,
        document_title="Vacation Policy",
        section_path=("HR",),
        content="Policy says this.",
        score=0.8,
        access_level="INTERNAL",
        retriever=RetrieverType.HYBRID,
        sanitizer_flags=sanitizer_flags,
    )
