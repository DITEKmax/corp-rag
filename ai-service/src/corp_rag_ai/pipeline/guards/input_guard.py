from __future__ import annotations

import re
from dataclasses import dataclass

from corp_rag_ai.domain.guard import GuardReason, GuardTier, GuardVerdict
from corp_rag_ai.domain.query import QueryInput, QueryResult, QueryRoute, RefusalReason
from corp_rag_ai.domain.retrieval import RetrievalMetadata
from corp_rag_ai.pipeline.ingestion.corpus_sanitizer import (
    PROMPT_CHAT_TEMPLATE,
    PROMPT_DISREGARD_RULES,
    PROMPT_FORGET_CONTEXT,
    PROMPT_IGNORE_INSTRUCTIONS,
    PROMPT_ROLE_OVERRIDE,
    PROMPT_SYSTEM_MARKER,
    CorpusSanitizer,
)

PROMPT_INJECTION_FLAGS = (
    PROMPT_IGNORE_INSTRUCTIONS,
    PROMPT_FORGET_CONTEXT,
    PROMPT_ROLE_OVERRIDE,
    PROMPT_SYSTEM_MARKER,
    PROMPT_CHAT_TEMPLATE,
    PROMPT_DISREGARD_RULES,
)

SYSTEM_PROMPT_EXTRACTION = "SYSTEM_PROMPT_EXTRACTION"
POLICY_ABUSE_REQUEST = "POLICY_ABUSE_REQUEST"
OUT_OF_SCOPE_REQUEST = "OUT_OF_SCOPE_REQUEST"

_SYSTEM_PROMPT_PATTERNS = (
    re.compile(r"\b(show|reveal|print|dump|expose)\s+(me\s+)?(your\s+)?(system|developer)\s+(prompt|instructions)\b", re.I),
    re.compile(r"\bwhat\s+(are|were)\s+your\s+(system|developer)\s+(prompt|instructions)\b", re.I),
)

_POLICY_PATTERNS = (
    re.compile(r"\b(harass|bully|threaten|intimidate)\b", re.I),
    re.compile(r"\b(write|draft|send).{0,40}\b(insulting|abusive|hostile)\b", re.I | re.S),
)

_OUT_OF_SCOPE_PATTERNS = (
    re.compile(r"\b(tell\s+me\s+a\s+joke|sing\s+a\s+song|write\s+a\s+poem)\b", re.I),
    re.compile(r"\b(weather|sports\s+score|movie\s+recommendation)\b", re.I),
    re.compile(r"\bwhat\s+is\s+\d+\s*[+\-*/]\s*\d+\b", re.I),
    re.compile(r"\b(write|generate|debug)\s+(python|java|javascript|sql|code)\b", re.I),
)

_REFUSAL_MESSAGES = {
    RefusalReason.PROMPT_INJECTION: "I cannot process requests that try to override system instructions.",
    RefusalReason.OUT_OF_SCOPE: "I can answer questions about available corporate documents, policies, and procedures.",
    RefusalReason.POLICY: "I cannot help with requests that target or harass people.",
}


@dataclass(frozen=True, slots=True)
class GuardOutcome:
    verdict: GuardVerdict
    refusal_result: QueryResult | None = None

    @property
    def accepted(self) -> bool:
        return self.refusal_result is None and self.verdict.safe


class InputGuard:
    def __init__(self, *, sanitizer: CorpusSanitizer | None = None, model_id: str = "") -> None:
        self._sanitizer = sanitizer or CorpusSanitizer()
        self._model_id = model_id

    def evaluate(self, query: QueryInput) -> GuardVerdict:
        text = query.message
        sanitizer_result = self._sanitizer.sanitize_text(text)
        injection_flags = tuple(flag for flag in sanitizer_result.sanitizer_flags if flag in PROMPT_INJECTION_FLAGS)
        if injection_flags:
            return GuardVerdict.rejected(
                reason=GuardReason.PROMPT_INJECTION,
                tier=GuardTier.TIER_0_REGEX,
                flags=injection_flags,
            )
        if _matches_any(_SYSTEM_PROMPT_PATTERNS, text):
            return GuardVerdict.rejected(
                reason=GuardReason.PROMPT_INJECTION,
                tier=GuardTier.TIER_0_REGEX,
                flags=(SYSTEM_PROMPT_EXTRACTION,),
            )
        if _matches_any(_POLICY_PATTERNS, text):
            return GuardVerdict.rejected(
                reason=GuardReason.POLICY,
                tier=GuardTier.TIER_0_REGEX,
                flags=(POLICY_ABUSE_REQUEST,),
            )
        if _matches_any(_OUT_OF_SCOPE_PATTERNS, text):
            return GuardVerdict.rejected(
                reason=GuardReason.OUT_OF_SCOPE,
                tier=GuardTier.TIER_0_REGEX,
                flags=(OUT_OF_SCOPE_REQUEST,),
            )
        return GuardVerdict.accepted()

    def guard(self, query: QueryInput) -> GuardOutcome:
        verdict = self.evaluate(query)
        if verdict.safe:
            return GuardOutcome(verdict=verdict)
        reason = _refusal_reason(verdict)
        return GuardOutcome(verdict=verdict, refusal_result=self._refusal_result(query, reason, verdict))

    def _refusal_result(self, query: QueryInput, reason: RefusalReason, verdict: GuardVerdict) -> QueryResult:
        return QueryResult.refused(
            query=query,
            reason=reason,
            answer=_REFUSAL_MESSAGES[reason],
            guard_verdict=verdict,
            retrieval_meta=RetrievalMetadata(
                route=QueryRoute.UNSUPPORTED,
                retrievers_attempted=(),
                retrievers_used=(),
                degradation_warnings=(),
                latency_ms=0,
                chunks_considered=0,
                chunks_returned=0,
                reranker_used=False,
                model_id=self._model_id,
            ),
        )


def _matches_any(patterns: tuple[re.Pattern[str], ...], text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _refusal_reason(verdict: GuardVerdict) -> RefusalReason:
    if verdict.reason == GuardReason.PROMPT_INJECTION:
        return RefusalReason.PROMPT_INJECTION
    if verdict.reason == GuardReason.POLICY:
        return RefusalReason.POLICY
    return RefusalReason.OUT_OF_SCOPE
