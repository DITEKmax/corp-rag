from __future__ import annotations

from dataclasses import dataclass

import tiktoken

from corp_rag_ai.domain.retrieval import CitationDraft, RetrievalCandidate, RetrieverType
from corp_rag_ai.pipeline.retrieval.parent_resolver import ParentResolution, ResolvedParentContext

OVERSIZED_PARENT_TRUNCATED = "oversized_parent_truncated"


@dataclass(frozen=True, slots=True)
class PackedContext:
    text: str
    citations: tuple[CitationDraft, ...]
    token_count: int
    warnings: tuple[str, ...] = ()


class ContextPacker:
    def __init__(self, *, token_cap: int = 4000) -> None:
        if token_cap < 1:
            raise ValueError("token_cap must be positive")
        self._token_cap = token_cap

    def pack(self, resolution: ParentResolution, ranked_children: tuple[RetrievalCandidate, ...]) -> PackedContext:
        citation_order = {candidate.chunk_id: index for index, candidate in enumerate(ranked_children)}
        citation_index_by_chunk_id = {candidate.chunk_id: index + 1 for index, candidate in enumerate(ranked_children)}
        contexts = sorted(
            resolution.contexts,
            key=lambda context: max((citation_order.get(child.chunk_id, 10_000) for child in context.children), default=10_000),
        )
        included: list[ResolvedParentContext] = []
        warnings: list[str] = list(resolution.warnings)
        token_total = 0

        for context in contexts:
            source_text = _source_block(len(included) + 1, context, citation_index_by_chunk_id)
            source_tokens = _count_tokens(source_text)
            if token_total + source_tokens <= self._token_cap:
                included.append(context)
                token_total += source_tokens
                continue
            if not included:
                truncated_parent = _truncate_to_token_cap(context.parent.content, self._token_cap)
                included.append(
                    ResolvedParentContext(
                        parent=context.parent.__class__(
                            parent_chunk_id=context.parent.parent_chunk_id,
                            document_id=context.parent.document_id,
                            section_path=context.parent.section_path,
                            content=truncated_parent,
                            position=context.parent.position,
                            token_count=_count_tokens(truncated_parent),
                        ),
                        children=context.children,
                        max_child_score=context.max_child_score,
                    )
                )
                warnings.append(OVERSIZED_PARENT_TRUNCATED)
            break

        text = (
            "<evidence>\n"
            + "\n".join(_source_block(index, context, citation_index_by_chunk_id) for index, context in enumerate(included, 1))
            + "\n</evidence>"
        )
        included_child_ids = {child.chunk_id for context in included for child in context.children}
        parent_text_by_child_id = {
            child.chunk_id: context.parent.content
            for context in included
            for child in context.children
        }
        citations = tuple(
            _citation_from_candidate(candidate, parent_text=parent_text_by_child_id.get(candidate.chunk_id))
            for candidate in ranked_children
            if candidate.chunk_id in included_child_ids
        )
        return PackedContext(text=text, citations=citations, token_count=_count_tokens(text), warnings=tuple(warnings))


def _source_block(
    index: int,
    context: ResolvedParentContext,
    citation_index_by_chunk_id: dict[object, int],
) -> str:
    child_ids = ",".join(str(child.chunk_id) for child in context.children)
    section = " > ".join(context.parent.section_path)
    citations = "\n".join(
        _citation_block(child, citation_index_by_chunk_id[child.chunk_id], parent_text=context.parent.content)
        for child in context.children
        if child.chunk_id in citation_index_by_chunk_id
    )
    return (
        f'<source index="{index}" parentChunkId="{context.parent.parent_chunk_id}" childChunkIds="{child_ids}">\n'
        f"<section>{section}</section>\n"
        f"<citations>\n{citations}\n</citations>\n"
        f"<text>{context.parent.content}</text>\n"
        "</source>"
    )


def _citation_block(candidate: RetrievalCandidate, index: int, *, parent_text: str) -> str:
    return (
        f'<citation index="{index}" chunkId="{candidate.chunk_id}">\n'
        f"<quote>{_quote(candidate, parent_text=parent_text, max_length=300)}</quote>\n"
        "</citation>"
    )


def _citation_from_candidate(candidate: RetrievalCandidate, *, parent_text: str | None = None) -> CitationDraft:
    return CitationDraft(
        document_id=candidate.document_id,
        document_title=candidate.document_title,
        chunk_id=candidate.chunk_id,
        section_path=candidate.section_path,
        quote=_quote(candidate, parent_text=parent_text),
        snippet=_quote(candidate, parent_text=parent_text, max_length=200),
        page_number=candidate.page_number,
        score=candidate.score,
        access_level=candidate.access_level,
    )


def _quote(candidate: RetrievalCandidate, *, parent_text: str | None = None, max_length: int = 200) -> str:
    if candidate.retriever is RetrieverType.GRAPH and parent_text and parent_text.strip():
        text = parent_text.strip()
    else:
        text = (candidate.snippet or candidate.content).strip()
    return text[:max_length]


def _encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_encoding().encode(text)) if text else 0


def _truncate_to_token_cap(text: str, token_cap: int) -> str:
    tokens = _encoding().encode(text)
    return _encoding().decode(tokens[:token_cap]).strip()
