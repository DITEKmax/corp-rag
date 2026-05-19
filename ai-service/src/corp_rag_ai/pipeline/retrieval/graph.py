from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from corp_rag_ai.domain.query import QueryInput, QueryRoute
from corp_rag_ai.domain.retrieval import (
    RetrievalCandidate,
    RetrievalFailureReason,
    RetrievalMetadata,
    RetrievalResult,
    RetrieverType,
)
from corp_rag_ai.pipeline.retrieval.graph_query_helpers import (
    aggregation_query,
    comparison_query,
    graph_access_params,
    multi_hop_query,
)

DEFAULT_GRAPH_LIMIT = 20
DEFAULT_MAX_GRAPH_HOPS = 3


class GraphRetriever:
    def __init__(
        self,
        driver: Any,
        *,
        database: str = "neo4j",
        max_hops: int = DEFAULT_MAX_GRAPH_HOPS,
        limit: int = DEFAULT_GRAPH_LIMIT,
    ) -> None:
        if max_hops < 1 or max_hops > DEFAULT_MAX_GRAPH_HOPS:
            raise ValueError("max_hops must be between 1 and 3")
        if limit < 1:
            raise ValueError("limit must be positive")
        self._driver = driver
        self._database = database
        self._max_hops = max_hops
        self._limit = limit

    async def retrieve(self, query: QueryInput, *, route: QueryRoute, model_id: str = "") -> RetrievalResult:
        if route in {QueryRoute.FACTUAL, QueryRoute.UNSUPPORTED}:
            return _empty_result(route=route, model_id=model_id)
        if route is QueryRoute.MULTI_HOP and _requested_hops(query.message) > self._max_hops:
            return _failure_result(
                route=route,
                reason=RetrievalFailureReason.UNSUPPORTED_GRAPH_DEPTH,
                warning=RetrievalFailureReason.UNSUPPORTED_GRAPH_DEPTH.value,
                model_id=model_id,
                attempted=(),
            )

        cypher, params = self._query_and_params(query, route)
        try:
            records = await self._run(cypher, params)
        except Exception:
            return _failure_result(
                route=route,
                reason=RetrievalFailureReason.GRAPH_RETRIEVAL_UNAVAILABLE,
                warning=RetrievalFailureReason.GRAPH_RETRIEVAL_UNAVAILABLE.value,
                model_id=model_id,
            )

        candidates = tuple(_candidate_from_record(record) for record in records)
        return RetrievalResult(
            candidates=candidates,
            metadata=RetrievalMetadata(
                route=route,
                retrievers_attempted=(RetrieverType.GRAPH,),
                retrievers_used=(RetrieverType.GRAPH,) if candidates else (),
                degradation_warnings=(),
                latency_ms=0,
                chunks_considered=len(records),
                chunks_returned=len(candidates),
                reranker_used=False,
                model_id=model_id,
            ),
        )

    def _query_and_params(self, query: QueryInput, route: QueryRoute) -> tuple[str, dict[str, object]]:
        params = graph_access_params(query.access_filter)
        params["limit"] = self._limit
        if route is QueryRoute.AGGREGATION:
            return aggregation_query(), params
        if route is QueryRoute.MULTI_HOP:
            return multi_hop_query(self._max_hops), params
        if route is QueryRoute.COMPARISON:
            params["entityNames"] = _comparison_entity_names(query.message)
            return comparison_query(), params
        raise ValueError(f"unsupported graph route: {route.value}")

    async def _run(self, cypher: str, params: Mapping[str, object]) -> list[Mapping[str, object]]:
        async with self._driver.session(database=self._database) as session:
            execute_read = getattr(session, "execute_read", None)
            if execute_read is not None:
                return list(await execute_read(_run_query, cypher, dict(params)))
            result = await session.run(cypher, **dict(params))
            return await _records(result)


async def _run_query(tx: Any, cypher: str, params: dict[str, object]) -> list[Mapping[str, object]]:
    result = await tx.run(cypher, **params)
    return await _records(result)


async def _records(result: Any) -> list[Mapping[str, object]]:
    data = getattr(result, "data", None)
    if data is not None:
        records = data()
        if hasattr(records, "__await__"):
            records = await records
        return list(records)
    if hasattr(result, "__aiter__"):
        return [record async for record in result]
    return list(result or [])


def _candidate_from_record(record: Mapping[str, object]) -> RetrievalCandidate:
    graph_path = str(record.get("graphPath") or "").strip()
    entity_name = record.get("entityName")
    relation_type = record.get("relationType")
    metadata = {
        "graphPath": graph_path,
        "entityName": entity_name,
        "relationType": relation_type,
        "candidateGroup": entity_name or relation_type,
    }
    return RetrievalCandidate(
        chunk_id=UUID(str(record["chunkId"])),
        parent_chunk_id=_optional_uuid(record.get("parentChunkId")),
        document_id=UUID(str(record["documentId"])),
        document_title=str(record.get("documentTitle", "")),
        section_path=_section_path(record.get("sectionPath")),
        content=graph_path or str(record.get("relationDescription") or entity_name or ""),
        snippet=graph_path or None,
        score=float(record.get("score", 0.0) or 0.0),
        access_level=str(record.get("accessLevel", "")),
        retriever=RetrieverType.GRAPH,
        sanitizer_flags=(),
        metadata={key: value for key, value in metadata.items() if value},
    )


def _empty_result(*, route: QueryRoute, model_id: str) -> RetrievalResult:
    return RetrievalResult(
        candidates=(),
        metadata=RetrievalMetadata(
            route=route,
            retrievers_attempted=(),
            retrievers_used=(),
            degradation_warnings=(),
            latency_ms=0,
            chunks_considered=0,
            chunks_returned=0,
            reranker_used=False,
            model_id=model_id,
        ),
    )


def _failure_result(
    *,
    route: QueryRoute,
    reason: RetrievalFailureReason,
    warning: str,
    model_id: str,
    attempted: tuple[RetrieverType, ...] = (RetrieverType.GRAPH,),
) -> RetrievalResult:
    return RetrievalResult(
        candidates=(),
        metadata=RetrievalMetadata(
            route=route,
            retrievers_attempted=attempted,
            retrievers_used=(),
            degradation_warnings=(warning,),
            latency_ms=0,
            chunks_considered=0,
            chunks_returned=0,
            reranker_used=False,
            model_id=model_id,
        ),
        failure_reason=reason,
    )


def _requested_hops(message: str) -> int:
    match = re.search(r"\b([2-9])\s*hops?\b", message, re.I)
    if match:
        return int(match.group(1))
    words = {"two": 2, "three": 3, "four": 4, "five": 5}
    for word, value in words.items():
        if re.search(rf"\b{word}\s+hops?\b", message, re.I):
            return value
    return DEFAULT_MAX_GRAPH_HOPS


def _comparison_entity_names(message: str) -> list[str]:
    text = re.sub(r"[^A-Za-z0-9\s]", " ", message.lower())
    text = re.sub(r"\b(compare|comparison|difference|between|versus|vs|and|with|policy|procedure)\b", " ", text)
    names: list[str] = []
    for part in re.sub(r"\s+", " ", text).strip().split(" "):
        if len(part) <= 2 or part in names:
            continue
        names.append(part)
    return names[:6]


def _section_path(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(part) for part in value if str(part).strip())
    if value is None:
        return ()
    return tuple(part.strip() for part in str(value).split(">") if part.strip())


def _optional_uuid(value: object) -> UUID | None:
    return UUID(str(value)) if value else None
