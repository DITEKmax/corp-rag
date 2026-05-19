from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GuardTier(str, Enum):
    TIER_0_REGEX = "TIER_0_REGEX"
    TIER_1_LLM = "TIER_1_LLM"
    OUTPUT_CHECK = "OUTPUT_CHECK"


class GuardReason(str, Enum):
    PROMPT_INJECTION = "prompt_injection"
    OUT_OF_SCOPE = "out_of_scope"
    POLICY = "policy"
    MISSING_CITATIONS = "missing_citations"
    INVALID_CITATIONS = "invalid_citations"
    LEAK_PATTERN = "leak_pattern"
    UNSAFE_EVIDENCE_ONLY = "unsafe_evidence_only"


@dataclass(frozen=True, slots=True)
class GuardVerdict:
    safe: bool
    reason: GuardReason | str | None = None
    tier: GuardTier | None = None
    confidence: float | None = None
    flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("guard confidence must be between 0.0 and 1.0")
        object.__setattr__(self, "flags", tuple(self.flags))

    @classmethod
    def accepted(cls) -> GuardVerdict:
        return cls(safe=True, confidence=1.0)

    @classmethod
    def rejected(
        cls,
        *,
        reason: GuardReason | str,
        tier: GuardTier,
        confidence: float = 1.0,
        flags: tuple[str, ...] = (),
    ) -> GuardVerdict:
        return cls(safe=False, reason=reason, tier=tier, confidence=confidence, flags=flags)

    @property
    def blocked(self) -> bool:
        return not self.safe
