from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
import os
from collections.abc import Sequence
from typing import Any, Protocol
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import httpx
import sqlalchemy as sa
from qdrant_client import AsyncQdrantClient, models
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from corp_rag_ai.contracts.generated import ai_service_v1 as contract
from corp_rag_ai.pipeline.indexing.vector_indexer import COLLECTION_NAME
from corp_rag_ai.repositories.tables import document_chunks_parent
from eval.schema import CorpusManifest, GoldenRecord


DEFAULT_EVAL_TOP_K = 5
DEFAULT_QDRANT_URL = "http://localhost:6333"
DEFAULT_AI_DB_URL = "postgresql+asyncpg://corp_rag_ai:corp_rag_ai@localhost:5432/corp_rag_ai"


class ActualOutcome(str, Enum):
    ANSWERED = "answered"
    REFUSED_NO_EVIDENCE = "refused_no_evidence"
    REFUSED_GUARD = "refused_guard"


@dataclass(frozen=True, slots=True)
class EvalAccessFilter:
    access_levels: tuple[str, ...]
    departments: tuple[str, ...]
    doc_types: tuple[str, ...]

    def to_payload(self) -> dict[str, list[str]]:
        return {
            "accessLevels": list(self.access_levels),
            "departments": list(self.departments),
            "docTypes": list(self.doc_types),
        }


@dataclass(frozen=True, slots=True)
class QueryClientConfig:
    base_url: str = "http://localhost:8000"
    timeout_seconds: float = 120.0
    top_k: int = DEFAULT_EVAL_TOP_K
    reranker_enabled: bool = True
    user_id: UUID = field(default_factory=lambda: uuid5(NAMESPACE_URL, "corp-rag-eval-user"))
    access_filter: EvalAccessFilter | None = None
    parent_context_enabled: bool = False
    qdrant_url: str = field(default_factory=lambda: os.getenv("QDRANT_URL", DEFAULT_QDRANT_URL))
    ai_db_url: str = field(default_factory=lambda: os.getenv("AI_DB_URL", DEFAULT_AI_DB_URL))


@dataclass(frozen=True, slots=True)
class EvalCitation:
    document_id: str
    document_title: str
    chunk_id: str
    quote: str
    snippet: str | None
    section_path: str
    score: float
    access_level: str

    @property
    def context_text(self) -> str:
        text = self.quote.strip() or (self.snippet or "").strip()
        prefix = f"{self.document_title} / {self.section_path}".strip(" /")
        return f"{prefix}\n{text}".strip()


@dataclass(frozen=True, slots=True)
class QuerySampleResult:
    record_id: str
    question: str
    reference_answer: str
    expected_doc_ids: tuple[str, ...]
    expected_outcome: str
    actual_outcome: ActualOutcome
    answered: bool
    answer: str
    citations: tuple[EvalCitation, ...]
    retrieved_contexts: tuple[str, ...]
    citation_document_ids: tuple[str, ...]
    route: str
    route_source: str | None
    route_reason: str | None
    retrievers_attempted: tuple[str, ...]
    retrievers_used: tuple[str, ...]
    degradation_warnings: tuple[str, ...]
    reranker_used: bool
    model_id: str
    confidence: float
    service_latency_ms: int
    client_latency_ms: int
    trace_id: str | None
    guard_verdict: dict[str, Any] | None

    def to_detail(self) -> dict[str, Any]:
        return {
            "id": self.record_id,
            "question": self.question,
            "expected_outcome": self.expected_outcome,
            "actual_outcome": self.actual_outcome.value,
            "outcome": self.actual_outcome.value,
            "answered": self.answered,
            "answer": self.answer,
            "expected_doc_ids": list(self.expected_doc_ids),
            "citation_document_ids": list(self.citation_document_ids),
            "retrieved_contexts": list(self.retrieved_contexts),
            "route": self.route,
            "route_source": self.route_source,
            "route_reason": self.route_reason,
            "retrievers_attempted": list(self.retrievers_attempted),
            "retrievers_used": list(self.retrievers_used),
            "degradation_warnings": list(self.degradation_warnings),
            "reranker_used": self.reranker_used,
            "model_id": self.model_id,
            "confidence": self.confidence,
            "service_latency_ms": self.service_latency_ms,
            "client_latency_ms": self.client_latency_ms,
            "trace_id": self.trace_id,
            "guard_verdict": self.guard_verdict,
        }


class QueryClientError(RuntimeError):
    pass


class ParentContextResolver(Protocol):
    async def resolve_contexts(self, citations: Sequence[contract.Citation]) -> tuple[str, ...]:
        ...

    async def aclose(self) -> None:
        ...


class QdrantPostgresParentContextResolver:
    def __init__(
        self,
        *,
        qdrant_url: str = DEFAULT_QDRANT_URL,
        db_url: str = DEFAULT_AI_DB_URL,
        collection_name: str = COLLECTION_NAME,
    ) -> None:
        self._qdrant = AsyncQdrantClient(url=qdrant_url)
        self._engine: AsyncEngine = create_async_engine(db_url)
        self._collection_name = collection_name

    async def resolve_contexts(self, citations: Sequence[contract.Citation]) -> tuple[str, ...]:
        chunk_ids = tuple(str(citation.chunkId) for citation in citations)
        if not chunk_ids:
            return ()

        chunk_payloads = await self._chunk_payloads(chunk_ids)
        parent_ids = tuple(
            dict.fromkeys(
                str(payload["parentChunkId"])
                for payload in chunk_payloads.values()
                if payload.get("parentChunkId")
            )
        )
        parents = await self._parent_contexts(parent_ids)

        contexts: list[str] = []
        seen_parent_ids: set[str] = set()
        for chunk_id in chunk_ids:
            payload = chunk_payloads.get(chunk_id)
            if not payload:
                continue
            parent_id = str(payload.get("parentChunkId") or "")
            if parent_id and parent_id in seen_parent_ids:
                continue
            if parent_id and parent_id in parents:
                contexts.append(_format_parent_context(payload, parents[parent_id]))
                seen_parent_ids.add(parent_id)
                continue
            fallback = _format_payload_context(payload)
            if fallback:
                contexts.append(fallback)
        return tuple(contexts)

    async def aclose(self) -> None:
        await self._qdrant.close()
        await self._engine.dispose()

    async def _chunk_payloads(self, chunk_ids: tuple[str, ...]) -> dict[str, dict[str, Any]]:
        response, _offset = await self._qdrant.scroll(
            collection_name=self._collection_name,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="chunkId",
                        match=models.MatchAny(any=list(chunk_ids)),
                    )
                ]
            ),
            limit=len(chunk_ids),
            with_payload=["chunkId", "parentChunkId", "documentTitle", "sectionPath", "content"],
            with_vectors=False,
        )
        payloads: dict[str, dict[str, Any]] = {}
        for point in response:
            payload = dict(point.payload or {})
            chunk_id = str(payload.get("chunkId") or "")
            if chunk_id:
                payloads[chunk_id] = payload
        return payloads

    async def _parent_contexts(self, parent_ids: tuple[str, ...]) -> dict[str, dict[str, Any]]:
        if not parent_ids:
            return {}
        statement = sa.select(
            document_chunks_parent.c.parent_chunk_id,
            document_chunks_parent.c.section_path,
            document_chunks_parent.c.content,
        ).where(document_chunks_parent.c.parent_chunk_id.in_([UUID(parent_id) for parent_id in parent_ids]))
        async with self._engine.connect() as connection:
            result = await connection.execute(statement)
            return {
                str(row.parent_chunk_id): {
                    "section_path": tuple(row.section_path or ()),
                    "content": row.content,
                }
                for row in result
            }


class ProductionQueryClient:
    def __init__(
        self,
        config: QueryClientConfig,
        *,
        http_client: httpx.AsyncClient | None = None,
        parent_context_resolver: ParentContextResolver | None = None,
    ) -> None:
        self._config = config
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=config.base_url.rstrip("/"),
            timeout=httpx.Timeout(config.timeout_seconds),
        )
        self._owns_parent_context_resolver = parent_context_resolver is None and config.parent_context_enabled
        self._parent_context_resolver = parent_context_resolver
        if self._parent_context_resolver is None and config.parent_context_enabled:
            self._parent_context_resolver = QdrantPostgresParentContextResolver(
                qdrant_url=config.qdrant_url,
                db_url=config.ai_db_url,
            )

    async def __aenter__(self) -> ProductionQueryClient:
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
        if self._owns_parent_context_resolver and self._parent_context_resolver is not None:
            await self._parent_context_resolver.aclose()

    async def query_golden(self, record: GoldenRecord) -> QuerySampleResult:
        payload = build_query_payload(record, self._config)
        started = time.perf_counter()
        response = await self._client.post("/v1/query", json=payload)
        client_latency_ms = int((time.perf_counter() - started) * 1000)
        if response.status_code >= 400:
            raise QueryClientError(_format_problem(response))

        parsed = contract.QueryResponse.model_validate(response.json())
        full_contexts: tuple[str, ...] = ()
        if self._parent_context_resolver is not None:
            full_contexts = await self._parent_context_resolver.resolve_contexts(parsed.citations)
        return query_response_to_sample(
            record,
            parsed,
            retrieved_contexts=full_contexts or None,
            client_latency_ms=client_latency_ms,
            trace_id=_trace_id(response.headers),
        )


def access_filter_from_manifest(manifest: CorpusManifest) -> EvalAccessFilter:
    return EvalAccessFilter(
        access_levels=tuple(sorted({entry.access_level for entry in manifest.documents})),
        departments=tuple(sorted({entry.department for entry in manifest.documents})),
        doc_types=tuple(sorted({entry.doc_type for entry in manifest.documents})),
    )


def build_query_payload(record: GoldenRecord, config: QueryClientConfig) -> dict[str, Any]:
    if config.access_filter is None:
        raise ValueError("QueryClientConfig.access_filter is required")

    return {
        "userId": str(config.user_id),
        "correlationId": str(uuid4()),
        "conversationId": str(uuid5(NAMESPACE_URL, f"corp-rag-eval:{record.id}")),
        "message": record.question,
        "conversationHistory": [],
        "accessFilter": config.access_filter.to_payload(),
        "retrievalOptions": {
            "topK": config.top_k,
            "rerankerEnabled": config.reranker_enabled,
        },
    }


def query_response_to_sample(
    record: GoldenRecord,
    response: contract.QueryResponse,
    *,
    retrieved_contexts: tuple[str, ...] | None = None,
    client_latency_ms: int,
    trace_id: str | None = None,
) -> QuerySampleResult:
    citations = tuple(
        EvalCitation(
            document_id=str(citation.documentId),
            document_title=citation.documentTitle,
            chunk_id=str(citation.chunkId),
            quote=citation.quote,
            snippet=citation.snippet,
            section_path=citation.sectionPath,
            score=citation.score,
            access_level=citation.accessLevel.value,
        )
        for citation in response.citations
    )
    meta = response.retrievalMeta
    return QuerySampleResult(
        record_id=record.id,
        question=record.question,
        reference_answer=record.reference_answer,
        expected_doc_ids=tuple(record.expected_doc_ids),
        expected_outcome=record.expected_outcome.value,
        actual_outcome=_actual_outcome(response),
        answered=response.answered,
        answer=response.answer,
        citations=citations,
        retrieved_contexts=retrieved_contexts
        if retrieved_contexts is not None
        else tuple(citation.context_text for citation in citations if citation.context_text),
        citation_document_ids=tuple(citation.document_id for citation in citations),
        route=meta.route.value,
        route_source=_optional_meta_string(meta, "routeSource"),
        route_reason=_optional_meta_string(meta, "routeReason"),
        retrievers_attempted=tuple(retriever.value for retriever in meta.retrieversAttempted),
        retrievers_used=tuple(retriever.value for retriever in meta.retrieversUsed),
        degradation_warnings=tuple(meta.degradationWarnings or ()),
        reranker_used=meta.rerankerUsed,
        model_id=meta.modelId,
        confidence=response.confidence,
        service_latency_ms=meta.latencyMs,
        client_latency_ms=client_latency_ms,
        trace_id=trace_id,
        guard_verdict=response.guardVerdict.model_dump(mode="json") if response.guardVerdict is not None else None,
    )


def _actual_outcome(response: contract.QueryResponse) -> ActualOutcome:
    if response.answered:
        return ActualOutcome.ANSWERED
    verdict = response.guardVerdict
    if verdict is not None and (verdict.safe is False or verdict.reason):
        return ActualOutcome.REFUSED_GUARD
    return ActualOutcome.REFUSED_NO_EVIDENCE


def _optional_meta_string(meta: object, name: str) -> str | None:
    value = getattr(meta, name, None)
    if value is None and hasattr(meta, "__pydantic_extra__"):
        value = (getattr(meta, "__pydantic_extra__") or {}).get(name)
    text = str(value).strip() if value is not None else ""
    return text or None


def _trace_id(headers: httpx.Headers) -> str | None:
    for name in ("x-langfuse-trace-id", "x-trace-id", "traceparent"):
        value = headers.get(name)
        if value:
            return value
    return None


def _format_parent_context(payload: dict[str, Any], parent: dict[str, Any]) -> str:
    title = str(payload.get("documentTitle") or "").strip()
    section = " > ".join(str(part) for part in parent.get("section_path", ()) if str(part).strip())
    content = str(parent.get("content") or "").strip()
    prefix = f"{title} / {section or 'Document'}".strip(" /")
    return f"{prefix}\n{content}".strip()


def _format_payload_context(payload: dict[str, Any]) -> str:
    title = str(payload.get("documentTitle") or "").strip()
    section_value = payload.get("sectionPath")
    section_parts = section_value if isinstance(section_value, list | tuple) else ()
    section = " > ".join(str(part) for part in section_parts if str(part).strip())
    content = str(payload.get("content") or "").strip()
    prefix = f"{title} / {section or 'Document'}".strip(" /")
    return f"{prefix}\n{content}".strip()


def _format_problem(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = {"detail": response.text}
    detail = payload.get("detail") or payload.get("title") or response.reason_phrase
    error_code = payload.get("errorCode")
    suffix = f" ({error_code})" if error_code else ""
    return f"/v1/query failed with HTTP {response.status_code}{suffix}: {detail}"
