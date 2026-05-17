from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID, uuid5

from corp_rag_ai.domain.chunks import ChildChunk, ChunkingResult, ParentChunk
from corp_rag_ai.domain.document import ParsedBlock, ParsedDocument
from corp_rag_ai.pipeline.ingestion.sentence_boundary import (
    DEFAULT_CHILD_MAX_TOKENS,
    DEFAULT_CHILD_OVERLAP_TOKENS,
    DEFAULT_CHILD_TARGET_TOKENS,
    TextSegment,
    count_tokens,
    split_text_into_child_segments,
)

DEFAULT_PARENT_TARGET_TOKENS = 1500
DEFAULT_PARENT_MAX_TOKENS = 2000

OVERSIZED_TABLE_WARNING = "OVERSIZED_TABLE_BLOCK"
OVERSIZED_PARENT_WARNING = "OVERSIZED_PARENT_BLOCK"
_BREADCRUMB_SEPARATOR = " \u203a "


@dataclass(frozen=True, slots=True)
class _SerializedBlock:
    block: ParsedBlock
    content: str


@dataclass(frozen=True, slots=True)
class _ParentDraft:
    section_path: tuple[str, ...]
    blocks: tuple[_SerializedBlock, ...]
    warnings: tuple[str, ...] = ()

    @property
    def content(self) -> str:
        return _join_blocks(self.blocks)

    @property
    def token_count(self) -> int:
        return count_tokens(self.content)

    @property
    def is_single_table(self) -> bool:
        return len(self.blocks) == 1 and self.blocks[0].block.type == "table"


class DocumentChunker:
    def __init__(
        self,
        *,
        parent_target_tokens: int = DEFAULT_PARENT_TARGET_TOKENS,
        parent_max_tokens: int = DEFAULT_PARENT_MAX_TOKENS,
        child_target_tokens: int = DEFAULT_CHILD_TARGET_TOKENS,
        child_max_tokens: int = DEFAULT_CHILD_MAX_TOKENS,
        child_overlap_tokens: int = DEFAULT_CHILD_OVERLAP_TOKENS,
    ) -> None:
        if parent_target_tokens <= 0:
            raise ValueError("parent_target_tokens must be positive")
        if parent_max_tokens < parent_target_tokens:
            raise ValueError("parent_max_tokens must be greater than or equal to parent_target_tokens")
        self._parent_target_tokens = parent_target_tokens
        self._parent_max_tokens = parent_max_tokens
        self._child_target_tokens = child_target_tokens
        self._child_max_tokens = child_max_tokens
        self._child_overlap_tokens = child_overlap_tokens

    def chunk(self, document: ParsedDocument, *, document_title: str) -> ChunkingResult:
        title = document_title.strip()
        if not title:
            raise ValueError("document_title must not be blank")

        drafts = self._build_parent_drafts(document)
        parents: list[ParentChunk] = []
        children: list[ChildChunk] = []
        warnings: list[str] = []

        for parent_position, draft in enumerate(drafts):
            parent_id = uuid5(document.document_id, f"parent:{parent_position}")
            parent = ParentChunk(
                parent_chunk_id=parent_id,
                document_id=document.document_id,
                section_path=draft.section_path,
                content=draft.content,
                position=parent_position,
                token_count=draft.token_count,
                source_block_positions=tuple(block.block.position for block in draft.blocks),
                warnings=draft.warnings,
            )
            parents.append(parent)
            warnings.extend(f"parent:{parent_position}:{warning}" for warning in draft.warnings)

            segments = self._split_parent(draft)
            for position_in_parent, segment in enumerate(segments):
                child_id = uuid5(parent_id, f"child:{position_in_parent}")
                child_warnings = draft.warnings + segment.warnings
                child = ChildChunk(
                    chunk_id=child_id,
                    parent_chunk_id=parent_id,
                    document_id=document.document_id,
                    section_path=draft.section_path,
                    content=segment.content,
                    content_for_embedding=_with_breadcrumb(
                        title=title,
                        section_path=draft.section_path,
                        body=segment.content,
                    ),
                    position=len(children),
                    position_in_parent=position_in_parent,
                    token_count=segment.token_count,
                    page=_first_page(draft.blocks),
                    warnings=child_warnings,
                )
                children.append(child)
                warnings.extend(f"child:{child.position}:{warning}" for warning in segment.warnings)

        return ChunkingResult(parents=tuple(parents), children=tuple(children), warnings=tuple(warnings))

    def _build_parent_drafts(self, document: ParsedDocument) -> list[_ParentDraft]:
        drafts: list[_ParentDraft] = []
        current: list[_SerializedBlock] = []
        current_section_path: tuple[str, ...] | None = None
        current_warnings: list[str] = []

        def flush() -> None:
            nonlocal current, current_section_path, current_warnings
            if not current or current_section_path is None:
                return
            content = _join_blocks(current)
            if count_tokens(content) > self._parent_max_tokens and OVERSIZED_PARENT_WARNING not in current_warnings:
                current_warnings.append(OVERSIZED_PARENT_WARNING)
            drafts.append(
                _ParentDraft(
                    section_path=current_section_path,
                    blocks=tuple(current),
                    warnings=tuple(current_warnings),
                )
            )
            current = []
            current_section_path = None
            current_warnings = []

        for block in document.blocks:
            serialized = _SerializedBlock(block=block, content=_serialize_block(block))
            section_path = tuple(block.section_path)

            if block.type == "table":
                flush()
                warnings = (OVERSIZED_TABLE_WARNING,) if count_tokens(serialized.content) > self._child_max_tokens else ()
                drafts.append(_ParentDraft(section_path=section_path, blocks=(serialized,), warnings=warnings))
                continue

            if current_section_path is not None and section_path != current_section_path:
                flush()

            if current and _count_joined((*current, serialized)) > self._parent_max_tokens:
                flush()

            if current and _count_joined(current) >= self._parent_target_tokens:
                flush()

            if not current:
                current_section_path = section_path
            current.append(serialized)

        flush()
        return drafts

    def _split_parent(self, draft: _ParentDraft) -> tuple[TextSegment, ...]:
        if draft.is_single_table:
            return (
                TextSegment(
                    content=draft.content,
                    token_count=draft.token_count,
                    start_token=0,
                    end_token=draft.token_count,
                    overlap_tokens=0,
                ),
            )
        return tuple(
            split_text_into_child_segments(
                draft.content,
                target_tokens=self._child_target_tokens,
                max_tokens=self._child_max_tokens,
                overlap_tokens=self._child_overlap_tokens,
            )
        )


def _serialize_block(block: ParsedBlock) -> str:
    text = block.text.strip()
    if block.type == "list_item":
        return "\u2022 " + text
    return text


def _join_blocks(blocks: Iterable[_SerializedBlock]) -> str:
    result = ""
    previous_type: str | None = None
    for item in blocks:
        if not result:
            result = item.content
        elif previous_type == "list_item" and item.block.type == "list_item":
            result += "\n" + item.content
        else:
            result += "\n\n" + item.content
        previous_type = item.block.type
    return result.strip()


def _count_joined(blocks: Iterable[_SerializedBlock]) -> int:
    return count_tokens(_join_blocks(blocks))


def _with_breadcrumb(*, title: str, section_path: tuple[str, ...], body: str) -> str:
    breadcrumb_parts = (title, *section_path)
    breadcrumb = _BREADCRUMB_SEPARATOR.join(part for part in breadcrumb_parts if part)
    return f"{breadcrumb}\n\n{body}" if breadcrumb else body


def _first_page(blocks: Iterable[_SerializedBlock]) -> int | None:
    for item in blocks:
        if item.block.page is not None:
            return item.block.page
    return None
