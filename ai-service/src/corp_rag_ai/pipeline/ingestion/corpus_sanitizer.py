from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from corp_rag_ai.domain.chunks import ChildChunk
from corp_rag_ai.domain.exceptions import INVALID_FILE_FORMAT, IndexingStage, StageFailure, stage_failure

PROMPT_IGNORE_INSTRUCTIONS = "PROMPT_IGNORE_INSTRUCTIONS"
PROMPT_FORGET_CONTEXT = "PROMPT_FORGET_CONTEXT"
PROMPT_ROLE_OVERRIDE = "PROMPT_ROLE_OVERRIDE"
PROMPT_SYSTEM_MARKER = "PROMPT_SYSTEM_MARKER"
PROMPT_CHAT_TEMPLATE = "PROMPT_CHAT_TEMPLATE"
PROMPT_DISREGARD_RULES = "PROMPT_DISREGARD_RULES"
SECRET_LITERAL = "SECRET_LITERAL"
SECRET_AWS_KEY = "SECRET_AWS_KEY"
SECRET_JWT = "SECRET_JWT"
SECRET_PEM_PRIVATE_KEY = "SECRET_PEM_PRIVATE_KEY"
SECRET_BEARER_TOKEN = "SECRET_BEARER_TOKEN"

DROP_EMPTY_TEXT = "DROP_EMPTY_TEXT"
DROP_PUNCTUATION_ONLY = "DROP_PUNCTUATION_ONLY"
DROP_REPEATED_CHARACTER = "DROP_REPEATED_CHARACTER"

LOCKED_SANITIZER_FLAGS = (
    PROMPT_IGNORE_INSTRUCTIONS,
    PROMPT_FORGET_CONTEXT,
    PROMPT_ROLE_OVERRIDE,
    PROMPT_SYSTEM_MARKER,
    PROMPT_CHAT_TEMPLATE,
    PROMPT_DISREGARD_RULES,
    SECRET_LITERAL,
    SECRET_AWS_KEY,
    SECRET_JWT,
    SECRET_PEM_PRIVATE_KEY,
    SECRET_BEARER_TOKEN,
)

_ZERO_WIDTH_RE = re.compile("[\u200b-\u200f\ufeff]")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACES_RE = re.compile(r"[^\S\n]+")
_PARAGRAPH_BREAK_RE = re.compile(r"\n{3,}")
_REPEATED_CHARACTER_MIN_LENGTH = 50

_FLAG_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        PROMPT_IGNORE_INSTRUCTIONS,
        re.compile(
            r"\b(ignore|override)\s+(all\s+)?(previous|prior|above)\s+instructions\b"
            r"|\bignore\s+the\s+instructions\b"
            r"|(?:\u0438\u0433\u043d\u043e\u0440\u0438\u0440\u0443\u0439|\u043f\u0440\u043e\u0438\u0433\u043d\u043e\u0440\u0438\u0440\u0443\u0439).{0,40}\u0438\u043d\u0441\u0442\u0440\u0443\u043a\u0446",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        PROMPT_FORGET_CONTEXT,
        re.compile(
            r"\bforget\s+(the\s+)?(previous|prior|above|earlier)\s+(content|context|messages|conversation)\b"
            r"|(?:\u0437\u0430\u0431\u0443\u0434\u044c|\u0437\u0430\u0431\u0443\u0434\u044c\u0442\u0435).{0,40}(\u043f\u0440\u0435\u0434\u044b\u0434\u0443\u0449|\u043a\u043e\u043d\u0442\u0435\u043a\u0441\u0442)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        PROMPT_ROLE_OVERRIDE,
        re.compile(
            r"\byou\s+are\s+now\b|\bact\s+as\s+(a\s+)?(system|developer|admin)\b|\bdeveloper\s+mode\b"
            r"|(?:\u0442\u044b|\u0432\u044b)\s+\u0442\u0435\u043f\u0435\u0440\u044c",
            re.IGNORECASE,
        ),
    ),
    (
        PROMPT_SYSTEM_MARKER,
        re.compile(
            r"<\s*/?\s*system\s*>|\bsystem\s*:|#+\s*system\s+prompt\b"
            r"|\u0441\u0438\u0441\u0442\u0435\u043c\u043d(ый|\u044b\u0439)\s+\u043f\u0440\u043e\u043c\u043f\u0442",
            re.IGNORECASE,
        ),
    ),
    (
        PROMPT_CHAT_TEMPLATE,
        re.compile(r"<\|system\|>|<\|user\|>|\[/?INST\]|<<SYS>>|<s>\s*\[INST\]", re.IGNORECASE),
    ),
    (
        PROMPT_DISREGARD_RULES,
        re.compile(
            r"\bdisregard\s+(the\s+)?rules\b|\bbypass\s+(the\s+)?(policy|rules|guardrails)\b"
            r"|(?:\u043e\u0431\u043e\u0439\u0434\u0438|\u043d\u0435\s+\u0441\u043e\u0431\u043b\u044e\u0434\u0430\u0439).{0,40}\u043f\u0440\u0430\u0432\u0438\u043b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        SECRET_LITERAL,
        re.compile(
            r"\b(api[_-]?key|secret|password|passwd|token|access[_-]?token|refresh[_-]?token)\b\s*[:=]\s*[\"']?[A-Za-z0-9_./+=:-]{8,}",
            re.IGNORECASE,
        ),
    ),
    (SECRET_AWS_KEY, re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    (SECRET_JWT, re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    (
        SECRET_PEM_PRIVATE_KEY,
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
    ),
    (SECRET_BEARER_TOKEN, re.compile(r"\bbearer\s+[A-Za-z0-9._~+/\-]+=*", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class SanitizerResult:
    sanitized_text: str
    is_sanitized: bool
    sanitizer_flags: tuple[str, ...]
    drop: bool
    drop_reason: str | None = None


@dataclass(frozen=True, slots=True)
class SanitizedChildChunk:
    child: ChildChunk
    sanitized_text: str
    is_sanitized: bool
    sanitizer_flags: tuple[str, ...]


class CorpusSanitizer:
    def sanitize_text(self, text: str) -> SanitizerResult:
        sanitized_text = _cleanup_text(text)
        drop_reason = _drop_reason(sanitized_text)
        flags = _detect_flags(sanitized_text) if drop_reason is None else ()

        return SanitizerResult(
            sanitized_text=sanitized_text,
            is_sanitized=not flags and drop_reason is None,
            sanitizer_flags=flags,
            drop=drop_reason is not None,
            drop_reason=drop_reason,
        )

    def sanitize_child_chunks(self, chunks: Iterable[ChildChunk]) -> tuple[SanitizedChildChunk, ...]:
        sanitized: list[SanitizedChildChunk] = []
        for child in chunks:
            result = self.sanitize_text(child.content)
            if result.drop:
                continue
            sanitized.append(
                SanitizedChildChunk(
                    child=child,
                    sanitized_text=result.sanitized_text,
                    is_sanitized=result.is_sanitized,
                    sanitizer_flags=result.sanitizer_flags,
                )
            )
        ensure_has_indexable_chunks(sanitized)
        return tuple(sanitized)


def ensure_has_indexable_chunks(chunks: Iterable[SanitizedChildChunk]) -> None:
    if not tuple(chunks):
        raise all_chunks_dropped_failure()


def all_chunks_dropped_failure() -> StageFailure:
    return stage_failure(
        stage=IndexingStage.SANITIZATION,
        error_code=INVALID_FILE_FORMAT,
        retryable=False,
        detail="all child chunks dropped",
    )


def _cleanup_text(text: str) -> str:
    value = text.replace("\r\n", "\n").replace("\r", "\n")
    value = _ZERO_WIDTH_RE.sub("", value)
    value = _CONTROL_RE.sub("", value)
    value = _SPACES_RE.sub(" ", value)
    lines = [line.strip() for line in value.split("\n")]
    value = "\n".join(lines)
    value = _PARAGRAPH_BREAK_RE.sub("\n\n", value)
    return value.strip()


def _drop_reason(text: str) -> str | None:
    if not text:
        return DROP_EMPTY_TEXT

    compact = re.sub(r"\s+", "", text)
    if compact and all(not char.isalnum() for char in compact):
        return DROP_PUNCTUATION_ONLY

    if len(compact) >= _REPEATED_CHARACTER_MIN_LENGTH and len(set(compact)) == 1:
        return DROP_REPEATED_CHARACTER

    return None


def _detect_flags(text: str) -> tuple[str, ...]:
    flags: list[str] = []
    for flag, pattern in _FLAG_PATTERNS:
        if pattern.search(text):
            flags.append(flag)
    return tuple(flags)
