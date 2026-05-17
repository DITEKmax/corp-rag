from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

import tiktoken

DEFAULT_CHILD_TARGET_TOKENS = 350
DEFAULT_CHILD_MAX_TOKENS = 500
DEFAULT_CHILD_OVERLAP_TOKENS = 50

HARD_CUT_WARNING = "HARD_TOKEN_CUT"

_PROTECTED_ABBREVIATIONS = {
    "dr.",
    "mr.",
    "mrs.",
    "ms.",
    "prof.",
    "sr.",
    "jr.",
    "st.",
    "vs.",
    "e.g.",
    "i.e.",
    "etc.",
    "u.s.",
    "u.k.",
    "\u0442.\u0435.",
    "\u0442.\u0434.",
    "\u0442.\u043f.",
    "\u0438 \u0442.\u0434.",
    "\u0438 \u0442.\u043f.",
    "\u0433.",
    "\u0443\u043b.",
    "\u0441\u0442\u0440.",
    "\u0440\u0438\u0441.",
}


@dataclass(frozen=True, slots=True)
class TextSegment:
    content: str
    token_count: int
    start_token: int
    end_token: int
    overlap_tokens: int
    warnings: tuple[str, ...] = ()


@lru_cache(maxsize=1)
def _encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_encoding().encode(text))


def split_text_into_child_segments(
    text: str,
    *,
    target_tokens: int = DEFAULT_CHILD_TARGET_TOKENS,
    max_tokens: int = DEFAULT_CHILD_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_CHILD_OVERLAP_TOKENS,
) -> list[TextSegment]:
    if target_tokens <= 0:
        raise ValueError("target_tokens must be positive")
    if max_tokens < target_tokens:
        raise ValueError("max_tokens must be greater than or equal to target_tokens")
    if overlap_tokens < 0:
        raise ValueError("overlap_tokens must be non-negative")

    stripped = text.strip()
    if not stripped:
        return []

    encoding = _encoding()
    tokens = encoding.encode(stripped)
    segments: list[TextSegment] = []
    start = 0

    while start < len(tokens):
        remaining = len(tokens) - start
        if remaining <= max_tokens:
            content = encoding.decode(tokens[start:]).strip()
            if content:
                segments.append(
                    TextSegment(
                        content=content,
                        token_count=len(tokens) - start,
                        start_token=start,
                        end_token=len(tokens),
                        overlap_tokens=0 if not segments else min(overlap_tokens, len(tokens) - start),
                    )
                )
            break

        window_tokens = tokens[start : start + max_tokens]
        window_text = encoding.decode(window_tokens)
        target_text = encoding.decode(tokens[start : start + target_tokens])
        boundary_char, warning = _choose_boundary(window_text, target_char=len(target_text))
        content = window_text[:boundary_char].strip()
        segment_token_count = count_tokens(content)

        if segment_token_count <= 0:
            content = encoding.decode(window_tokens).strip()
            segment_token_count = len(window_tokens)
            warning = HARD_CUT_WARNING
        elif segment_token_count > max_tokens:
            content = encoding.decode(window_tokens).strip()
            segment_token_count = len(window_tokens)
            warning = HARD_CUT_WARNING

        end = start + segment_token_count
        warnings = (warning,) if warning else ()
        applied_overlap = 0 if not segments else min(overlap_tokens, segment_token_count)
        segments.append(
            TextSegment(
                content=content,
                token_count=segment_token_count,
                start_token=start,
                end_token=end,
                overlap_tokens=applied_overlap,
                warnings=warnings,
            )
        )

        if end >= len(tokens):
            break

        if overlap_tokens == 0 or segment_token_count <= overlap_tokens:
            start = end
        else:
            start = max(start + 1, end - overlap_tokens)

    return segments


def find_sentence_boundaries(text: str) -> tuple[int, ...]:
    boundaries: list[int] = []
    for index, char in enumerate(text):
        if char in "!?":
            boundaries.append(_consume_closing_marks(text, index + 1))
        elif char == "." and not _is_protected_period(text, index):
            boundaries.append(_consume_closing_marks(text, index + 1))
    return tuple(sorted(set(boundaries)))


def _choose_boundary(text: str, *, target_char: int) -> tuple[int, str | None]:
    candidates = _boundary_candidates(text)
    if not candidates:
        return _last_non_space_index(text), HARD_CUT_WARNING

    max_char = len(text)
    min_char = max(1, int(target_char * 0.55))
    usable = [(position, priority) for position, priority in candidates if min_char <= position <= max_char]
    after_target = [(position, priority) for position, priority in usable if position >= target_char]
    if after_target:
        position, _ = min(after_target, key=lambda item: (item[1], item[0] - target_char))
        return position, None

    before_target = [(position, priority) for position, priority in usable if position < target_char]
    if before_target:
        position, _ = min(before_target, key=lambda item: (item[1], target_char - item[0]))
        return position, None

    return _last_non_space_index(text), HARD_CUT_WARNING


def _boundary_candidates(text: str) -> list[tuple[int, int]]:
    candidates: list[tuple[int, int]] = []

    for match in re.finditer(r"\n{2,}", text):
        candidates.append((match.end(), 0))

    for index, char in enumerate(text):
        if char in "!?":
            candidates.append((_consume_closing_marks(text, index + 1), 1))
        elif char == "." and not _is_protected_period(text, index):
            candidates.append((_consume_closing_marks(text, index + 1), 2))

    for match in re.finditer(r"\n+", text):
        candidates.append((match.end(), 3))

    return sorted(set(candidates))


def _is_protected_period(text: str, index: int) -> bool:
    previous_char = text[index - 1] if index > 0 else ""
    next_char = text[index + 1] if index + 1 < len(text) else ""
    if previous_char.isdigit() and next_char.isdigit():
        return True

    prefix = re.sub(r"\s+", " ", text[: index + 1]).strip().lower()
    if any(prefix.endswith(abbreviation) for abbreviation in _PROTECTED_ABBREVIATIONS):
        return True

    token_match = re.search(r"([\w.]+)\.$", prefix, flags=re.UNICODE)
    token = token_match.group(1) + "." if token_match else ""
    if re.fullmatch(r"(?:[a-z\u0430-\u044f\u0451]\.){1,}", token):
        return True

    if previous_char.isupper() and (index == 1 or text[index - 2].isspace() or text[index - 2] == "."):
        return True

    return False


def _consume_closing_marks(text: str, index: int) -> int:
    while index < len(text) and text[index] in "\"')]}":
        index += 1
    return index


def _last_non_space_index(text: str) -> int:
    stripped = text.rstrip()
    return len(stripped) if stripped else len(text)
