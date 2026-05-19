from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from corp_rag_ai.domain.ingestion_state import ParentChunkRecord
from corp_rag_ai.domain.retrieval import RetrievalCandidate

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

        for candidate in candidates:
            if candidate.parent_chunk_id is None:
                warnings.append(f"{MISSING_PARENT_WARNING}:{candidate.chunk_id}")
                continue
            if candidate.parent_chunk_id not in parents:
                warnings.append(f"{MISSING_PARENT_WARNING}:{candidate.parent_chunk_id}")
                continue
            children_by_parent[candidate.parent_chunk_id].append(candidate)

        contexts = [
            ResolvedParentContext(
                parent=parents[parent_id],
                children=tuple(children),
                max_child_score=max(child.score for child in children),
            )
            for parent_id, children in children_by_parent.items()
        ]
        contexts.sort(key=lambda item: item.max_child_score, reverse=True)
        usable_parent_ids = {context.parent.parent_chunk_id for context in contexts}
        citation_candidates = tuple(
            candidate for candidate in candidates if candidate.parent_chunk_id in usable_parent_ids
        )
        return ParentResolution(
            contexts=tuple(contexts),
            citation_candidates=citation_candidates,
            warnings=tuple(warnings),
        )
