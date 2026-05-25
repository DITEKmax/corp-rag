from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Protocol
from uuid import UUID

from corp_rag_ai.domain.ingestion_state import ParentChunkRecord
from corp_rag_ai.domain.retrieval import RetrievalCandidate, RetrieverType

MISSING_PARENT_WARNING = "missing_parent_context"


class ParentChunkReader(Protocol):
    async def get_by_parent_ids(self, parent_ids: tuple[UUID, ...]) -> dict[UUID, ParentChunkRecord]:
        ...


@dataclass(frozen=True, slots=True)
class ResolvedParentContext:
    parent: ParentChunkRecord
    children: tuple[RetrievalCandidate, ...]
    max_child_score: float


@dataclass(frozen=True, slots=True)
class ParentResolution:
    contexts: tuple[ResolvedParentContext, ...]
    citation_candidates: tuple[RetrievalCandidate, ...]
    warnings: tuple[str, ...] = ()


class ParentResolver:
    def __init__(self, parent_chunks: ParentChunkReader) -> None:
        self._parent_chunks = parent_chunks

    async def resolve(self, candidates: tuple[RetrievalCandidate, ...]) -> ParentResolution:
        parent_ids = tuple(
            dict.fromkeys(candidate.parent_chunk_id for candidate in candidates if candidate.parent_chunk_id is not None)
        )
        parents = await self._parent_chunks.get_by_parent_ids(parent_ids)
        children_by_parent: dict[UUID, list[RetrievalCandidate]] = defaultdict(list)
        warnings: list[str] = []

        citation_candidates: list[RetrievalCandidate] = []
        for candidate in candidates:
            if candidate.parent_chunk_id is None:
                warnings.append(f"{MISSING_PARENT_WARNING}:{candidate.chunk_id}")
                continue
            parent = parents.get(candidate.parent_chunk_id)
            if parent is None:
                warnings.append(f"{MISSING_PARENT_WARNING}:{candidate.parent_chunk_id}")
                continue
            enriched = _document_backed_candidate(candidate, parent)
            children_by_parent[candidate.parent_chunk_id].append(enriched)
            citation_candidates.append(enriched)

        contexts = [
            ResolvedParentContext(
                parent=parents[parent_id],
                children=tuple(children),
                max_child_score=max(child.score for child in children),
            )
            for parent_id, children in children_by_parent.items()
        ]
        contexts.sort(key=lambda item: item.max_child_score, reverse=True)
        return ParentResolution(
            contexts=tuple(contexts),
            citation_candidates=tuple(citation_candidates),
            warnings=tuple(warnings),
        )


def _document_backed_candidate(candidate: RetrievalCandidate, parent: ParentChunkRecord) -> RetrievalCandidate:
    if candidate.retriever is not RetrieverType.GRAPH:
        return candidate
    parent_text = parent.content.strip()
    if not parent_text:
        return candidate
    graph_path = str(candidate.metadata.get("graphPath") or "").strip()
    if _is_internal_graph_text(candidate.content, graph_path) or _is_internal_graph_text(candidate.snippet, graph_path):
        return replace(candidate, content=parent_text, snippet=parent_text)
    return candidate


def _is_internal_graph_text(value: str | None, graph_path: str) -> bool:
    text = (value or "").strip()
    if not text:
        return True
    return text.startswith(("entity:", "comparison:")) or bool(graph_path and text == graph_path)
