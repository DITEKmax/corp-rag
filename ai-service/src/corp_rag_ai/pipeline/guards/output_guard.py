from __future__ import annotations

import re

from corp_rag_ai.domain.guard import GuardReason, GuardTier, GuardVerdict
from corp_rag_ai.domain.retrieval import CitationDraft, RetrievalCandidate
from corp_rag_ai.pipeline.generation.synthesizer import SynthesisResult
from corp_rag_ai.pipeline.ingestion.corpus_sanitizer import (
    SECRET_AWS_KEY,
    SECRET_BEARER_TOKEN,
    SECRET_JWT,
    SECRET_LITERAL,
    SECRET_PEM_PRIVATE_KEY,
    CorpusSanitizer,
)

SECRET_FLAGS = {SECRET_LITERAL, SECRET_AWS_KEY, SECRET_JWT, SECRET_PEM_PRIVATE_KEY, SECRET_BEARER_TOKEN}


class OutputGuard:
    def __init__(self, *, sanitizer: CorpusSanitizer | None = None) -> None:
        self._sanitizer = sanitizer or CorpusSanitizer()

    def validate(
        self,
        result: SynthesisResult,
        *,
        citations: tuple[CitationDraft, ...],
        evidence: tuple[RetrievalCandidate, ...],
    ) -> GuardVerdict:
        if not result.answered:
            return GuardVerdict.accepted()
        if evidence and all(candidate.sanitizer_flags for candidate in evidence):
            return GuardVerdict.rejected(reason=GuardReason.UNSAFE_EVIDENCE_ONLY, tier=GuardTier.OUTPUT_CHECK)

        refs = tuple(int(match) for match in re.findall(r"\[(\d+)\]", result.answer))
        valid_indexes = set(range(1, len(citations) + 1))
        if any(ref not in valid_indexes for ref in refs) or any(index not in valid_indexes for index in result.citation_indexes):
            return GuardVerdict.rejected(reason=GuardReason.INVALID_CITATIONS, tier=GuardTier.OUTPUT_CHECK)
        if not refs and _looks_factual(result.answer):
            return GuardVerdict.rejected(reason=GuardReason.MISSING_CITATIONS, tier=GuardTier.OUTPUT_CHECK)

        flags = set(self._sanitizer.sanitize_text(result.answer).sanitizer_flags)
        if flags & SECRET_FLAGS:
            return GuardVerdict.rejected(
                reason=GuardReason.LEAK_PATTERN,
                tier=GuardTier.OUTPUT_CHECK,
                flags=tuple(sorted(flags & SECRET_FLAGS)),
            )
        return GuardVerdict.accepted()


def _looks_factual(answer: str) -> bool:
    text = answer.strip()
    return bool(re.search(r"[A-Za-z0-9]", text)) and len(text.split()) >= 4
