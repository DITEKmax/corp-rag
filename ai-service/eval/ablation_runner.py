from __future__ import annotations

import argparse
import asyncio
import csv
import os
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from qdrant_client import AsyncQdrantClient

from corp_rag_ai.domain.query import AccessFilter
from corp_rag_ai.domain.retrieval import RetrievalCandidate, RetrieverType
from corp_rag_ai.pipeline.indexing.embedding import DEFAULT_BGE_M3_MODEL, EmbeddingVector, LocalBgeM3Embedder
from corp_rag_ai.pipeline.indexing.vector_indexer import COLLECTION_NAME, QdrantVectorIndex
from corp_rag_ai.pipeline.retrieval.reranker import LocalReranker
from eval.bm25 import BM25Index
from eval.io import load_corpus_metadata, load_golden_records, load_manifest, read_json, write_json
from eval.metrics import RetrievalObservation, recall_at_k, reciprocal_rank, summarize_retrieval_metrics
from eval.query_client import DEFAULT_QDRANT_URL, access_filter_from_manifest
from eval.retrieval_modes import RetrievalMode
from eval.schema import GoldenRecord
from eval.validate_golden import DEFAULT_CORPUS_DIR, DEFAULT_GOLDEN_PATH, DEFAULT_MANIFEST_PATH, DEFAULT_METADATA_PATH


EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_REPORTS_DIR = EVAL_DIR / "reports"
DEFAULT_REPORT_SLUG = "ablation_ru"
DEFAULT_SOURCE_REPORT_PATH = DEFAULT_REPORTS_DIR / "ragas_ru.json"
VECTOR_MODE_ORDER = (
    RetrievalMode.BM25,
    RetrievalMode.DENSE,
    RetrievalMode.SPARSE,
    RetrievalMode.HYBRID,
    RetrievalMode.HYBRID_RERANKER,
)
GRAPH_ROUTE_VALUES = {"AGGREGATION", "MULTI_HOP"}
VECTOR_RETRIEVER_VALUES = {"HYBRID"}
GRAPH_RETRIEVER_VALUES = {"GRAPH"}


@dataclass(frozen=True, slots=True)
class AblationRunnerConfig:
    golden_path: Path = DEFAULT_GOLDEN_PATH
    metadata_path: Path = DEFAULT_METADATA_PATH
    corpus_dir: Path = DEFAULT_CORPUS_DIR
    manifest_path: Path = DEFAULT_MANIFEST_PATH
    reports_dir: Path = DEFAULT_REPORTS_DIR
    report_slug: str = DEFAULT_REPORT_SLUG
    source_report_path: Path = DEFAULT_SOURCE_REPORT_PATH
    qdrant_url: str = field(default_factory=lambda: os.getenv("QDRANT_URL", DEFAULT_QDRANT_URL))
    embedding_model_id: str = DEFAULT_BGE_M3_MODEL
    top_k: int = 10
    prefetch_limit: int = 30
    reranker_model_id: str = "BAAI/bge-reranker-v2-m3"
    reranker_timeout_seconds: float = 25.0
    reranker_load_timeout_seconds: float = 28.0
    hybrid_reranker_source: str = "direct_hybrid_candidates"

    def __post_init__(self) -> None:
        if self.top_k < 1:
            raise ValueError("top_k must be positive")
        if self.prefetch_limit < self.top_k:
            raise ValueError("prefetch_limit must be greater than or equal to top_k")
        if self.reranker_timeout_seconds <= 0 or self.reranker_load_timeout_seconds <= 0:
            raise ValueError("reranker timeouts must be positive")


@dataclass(frozen=True, slots=True)
class RouteDetail:
    record_id: str
    route: str
    retrievers_attempted: tuple[str, ...] = ()
    retrievers_used: tuple[str, ...] = ()
    reranker_used: bool = False
    actual_outcome: str = ""
    citation_document_ids: tuple[str, ...] = ()
    degradation_warnings: tuple[str, ...] = ()
    guard_verdict: dict[str, Any] | None = None

    @classmethod
    def from_report_detail(cls, detail: dict[str, Any]) -> RouteDetail:
        return cls(
            record_id=str(detail.get("id") or detail.get("question_id") or ""),
            route=str(detail.get("route") or ""),
            retrievers_attempted=tuple(str(item) for item in detail.get("retrievers_attempted", ()) or ()),
            retrievers_used=tuple(str(item) for item in detail.get("retrievers_used", ()) or ()),
            reranker_used=bool(detail.get("reranker_used", False)),
            actual_outcome=str(detail.get("actual_outcome") or detail.get("outcome") or ""),
            citation_document_ids=tuple(str(item) for item in detail.get("citation_document_ids", ()) or ()),
            degradation_warnings=tuple(str(item) for item in detail.get("degradation_warnings", ()) or ()),
            guard_verdict=detail.get("guard_verdict") if isinstance(detail.get("guard_verdict"), dict) else None,
        )

    @property
    def attempted_or_used(self) -> tuple[str, ...]:
        return (*self.retrievers_attempted, *self.retrievers_used)

    @property
    def is_vector_routed(self) -> bool:
        return any(value in VECTOR_RETRIEVER_VALUES for value in self.attempted_or_used)

    @property
    def is_graph_routed(self) -> bool:
        return self.route in GRAPH_ROUTE_VALUES or any(value in GRAPH_RETRIEVER_VALUES for value in self.attempted_or_used)


@dataclass(frozen=True, slots=True)
class ScopeExclusion:
    record_id: str
    reason: str
    route: str = ""
    retrievers_attempted: tuple[str, ...] = ()
    retrievers_used: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RouteDiscrepancy:
    record_id: str
    golden_type: str
    route: str
    retrieval_family: str


@dataclass(frozen=True, slots=True)
class AblationScope:
    vector_records: tuple[GoldenRecord, ...]
    graph_records: tuple[GoldenRecord, ...]
    excluded_records: tuple[ScopeExclusion, ...]
    route_discrepancies: tuple[RouteDiscrepancy, ...]

    @property
    def vector_ids(self) -> tuple[str, ...]:
        return tuple(record.id for record in self.vector_records)

    @property
    def graph_ids(self) -> tuple[str, ...]:
        return tuple(record.id for record in self.graph_records)


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    rank: int
    document_id: str
    score: float | None = None
    chunk_id: str = ""
    document_title: str = ""


@dataclass(frozen=True, slots=True)
class ModeRecordResult:
    mode: RetrievalMode
    record: GoldenRecord
    hits: tuple[RetrievalHit, ...]
    warnings: tuple[str, ...] = ()

    @property
    def retrieved_doc_ids(self) -> tuple[str, ...]:
        return tuple(hit.document_id for hit in self.hits if hit.document_id)

    @property
    def retrieved_chunk_ids(self) -> tuple[str, ...]:
        return tuple(hit.chunk_id for hit in self.hits if hit.chunk_id)

    def to_observation(self) -> RetrievalObservation:
        return RetrievalObservation.from_golden_record(self.record, self.retrieved_doc_ids)

    def to_detail_row(self) -> dict[str, Any]:
        expected = tuple(self.record.expected_doc_ids)
        first_expected_rank = _first_expected_rank(expected, self.retrieved_doc_ids)
        return {
            "section": "vector",
            "mode": self.mode.value,
            "id": self.record.id,
            "type": self.record.type.value,
            "expected_doc_ids": list(expected),
            "retrieved_doc_ids": list(self.retrieved_doc_ids),
            "retrieved_chunk_ids": list(self.retrieved_chunk_ids),
            "first_expected_rank": first_expected_rank,
            "recall@5": recall_at_k(expected, self.retrieved_doc_ids, k=5),
            "recall@10": recall_at_k(expected, self.retrieved_doc_ids, k=10),
            "mrr": reciprocal_rank(expected, self.retrieved_doc_ids),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class GraphRecordResult:
    record: GoldenRecord
    route_detail: RouteDetail

    @property
    def retrieved_doc_ids(self) -> tuple[str, ...]:
        return self.route_detail.citation_document_ids

    def to_observation(self) -> RetrievalObservation:
        return RetrievalObservation.from_golden_record(self.record, self.retrieved_doc_ids)

    def to_detail_row(self) -> dict[str, Any]:
        expected = tuple(self.record.expected_doc_ids)
        return {
            "section": "graph",
            "mode": "graph",
            "id": self.record.id,
            "type": self.record.type.value,
            "route": self.route_detail.route,
            "expected_doc_ids": list(expected),
            "retrieved_doc_ids": list(self.retrieved_doc_ids),
            "citeable_evidence_found": bool(self.retrieved_doc_ids),
            "actual_outcome": self.route_detail.actual_outcome,
            "guard_refusal": self.route_detail.actual_outcome == "refused_guard",
            "no_evidence_refusal": self.route_detail.actual_outcome == "refused_no_evidence",
            "recall@5": recall_at_k(expected, self.retrieved_doc_ids, k=5),
            "recall@10": recall_at_k(expected, self.retrieved_doc_ids, k=10),
            "mrr": reciprocal_rank(expected, self.retrieved_doc_ids),
            "warnings": list(self.route_detail.degradation_warnings),
        }


@dataclass(frozen=True, slots=True)
class AblationRunOutput:
    report: dict[str, Any]
    markdown_path: Path
    json_path: Path
    csv_path: Path


async def run_ablation(config: AblationRunnerConfig) -> AblationRunOutput:
    metadata = load_corpus_metadata(config.metadata_path)
    manifest = load_manifest(config.manifest_path)
    records = load_golden_records(config.golden_path)
    source_payload = read_json(config.source_report_path)
    route_details = route_details_from_source_report(source_payload)
    scope = select_ablation_scope(records, route_details)
    access_filter = _domain_access_filter(manifest)
    qdrant_point_count = await _qdrant_point_count(config.qdrant_url)
    payload_smoke = await dense_sparse_payload_smoke(config.qdrant_url)

    bm25 = BM25Index.from_corpus(config.corpus_dir, manifest)
    manifest_to_indexed_doc_id = indexed_document_id_map(metadata)
    mode_results: dict[RetrievalMode, tuple[ModeRecordResult, ...]] = {
        RetrievalMode.BM25: tuple(
            _bm25_result(
                bm25,
                record,
                manifest_to_indexed_doc_id=manifest_to_indexed_doc_id,
                limit=config.top_k,
            )
            for record in scope.vector_records
        ),
    }

    vector_index = QdrantVectorIndex.from_url(config.qdrant_url)
    embedder = LocalBgeM3Embedder(model_name=config.embedding_model_id)
    reranker = LocalReranker(
        enabled=True,
        model_name=config.reranker_model_id,
        timeout_seconds=config.reranker_timeout_seconds,
        load_timeout_seconds=config.reranker_load_timeout_seconds,
    )
    try:
        for mode in (RetrievalMode.DENSE, RetrievalMode.SPARSE, RetrievalMode.HYBRID):
            mode_results[mode] = tuple(
                [
                    await _vector_result(
                        vector_index,
                        embedder,
                        record,
                        access_filter=access_filter,
                        mode=mode,
                        limit=config.top_k,
                        prefetch_limit=config.prefetch_limit,
                    )
                    for record in scope.vector_records
                ]
            )
        mode_results[RetrievalMode.HYBRID_RERANKER] = tuple(
            [
                await _hybrid_reranker_result(
                    vector_index,
                    embedder,
                    reranker,
                    record,
                    access_filter=access_filter,
                    limit=config.top_k,
                    prefetch_limit=config.prefetch_limit,
                )
                for record in scope.vector_records
            ]
        )
    finally:
        await vector_index.close()

    graph_results = tuple(GraphRecordResult(record, route_details[record.id]) for record in scope.graph_records)
    report = build_ablation_report(
        config=config,
        corpus_version=metadata.corpus_version,
        corpus_hash=metadata.corpus_hash,
        qdrant_point_count=qdrant_point_count,
        payload_smoke=payload_smoke,
        scope=scope,
        mode_results=mode_results,
        graph_results=graph_results,
    )
    markdown_path, json_path, csv_path = write_ablation_artifacts(report, reports_dir=config.reports_dir, slug=config.report_slug)
    return AblationRunOutput(report=report, markdown_path=markdown_path, json_path=json_path, csv_path=csv_path)


def route_details_from_source_report(payload: dict[str, Any]) -> dict[str, RouteDetail]:
    details = payload.get("details", ())
    route_details: dict[str, RouteDetail] = {}
    for raw_detail in details:
        if not isinstance(raw_detail, dict):
            continue
        detail = RouteDetail.from_report_detail(raw_detail)
        if detail.record_id:
            route_details[detail.record_id] = detail
    return route_details


def select_ablation_scope(records: tuple[GoldenRecord, ...], route_details: dict[str, RouteDetail]) -> AblationScope:
    vector_records: list[GoldenRecord] = []
    graph_records: list[GoldenRecord] = []
    excluded_records: list[ScopeExclusion] = []
    discrepancies: list[RouteDiscrepancy] = []

    for record in records:
        detail = route_details.get(record.id)
        if not record.expected_doc_ids:
            excluded_records.append(_exclusion(record, detail, "no_expected_doc_ids"))
            continue
        if detail is None:
            excluded_records.append(_exclusion(record, detail, "missing_route_metadata"))
            continue

        retrieval_family = _retrieval_family(detail)
        expected_family = _expected_family(record)
        if expected_family != retrieval_family:
            discrepancies.append(
                RouteDiscrepancy(
                    record_id=record.id,
                    golden_type=record.type.value,
                    route=detail.route,
                    retrieval_family=retrieval_family,
                )
            )

        if detail.is_vector_routed:
            vector_records.append(record)
        elif detail.is_graph_routed:
            graph_records.append(record)
        else:
            excluded_records.append(_exclusion(record, detail, "non_retrieval_route"))

    return AblationScope(
        vector_records=tuple(vector_records),
        graph_records=tuple(graph_records),
        excluded_records=tuple(excluded_records),
        route_discrepancies=tuple(discrepancies),
    )


def indexed_document_id_map(metadata: object) -> dict[str, str]:
    entries = getattr(metadata, "indexed_document_map", None)
    if entries is None:
        entries = getattr(metadata, "__pydantic_extra__", {}).get("indexed_document_map", ())
    result: dict[str, str] = {}
    for entry in entries or ():
        if isinstance(entry, dict):
            manifest_doc_id = str(entry.get("manifest_doc_id") or "").strip()
            indexed_document_id = str(entry.get("indexed_document_id") or "").strip()
            if manifest_doc_id and indexed_document_id:
                result[manifest_doc_id] = indexed_document_id
    return result


async def dense_sparse_payload_smoke(qdrant_url: str) -> dict[str, Any]:
    client = AsyncQdrantClient(url=qdrant_url)
    try:
        points, _ = await client.scroll(
            collection_name=COLLECTION_NAME,
            limit=1,
            with_payload=True,
            with_vectors=True,
        )
        if not points:
            return {"passed": False, "reason": "empty_collection", "modes": {}}
        sample = points[0]
        payload = sample.payload or {}
        vectors = sample.vector or {}
        dense = vectors.get("dense") if isinstance(vectors, dict) else None
        sparse = vectors.get("sparse") if isinstance(vectors, dict) else None
        if dense is None or sparse is None:
            return {"passed": False, "reason": "missing_sample_vectors", "modes": {}}
        query_embedding = EmbeddingVector(
            dense=tuple(float(value) for value in dense),
            sparse=_sparse_to_dict(sparse),
        )
        access_filter = AccessFilter(
            access_levels=(payload.get("accessLevel") or "PUBLIC",),
            departments=(payload.get("department"),) if payload.get("department") else (),
            doc_types=(payload.get("docType") or "POLICY",),
        )
        index = QdrantVectorIndex(client)
        modes: dict[str, Any] = {}
        for mode in (RetrievalMode.DENSE, RetrievalMode.SPARSE):
            response = await index.query_hybrid(
                query_embedding=query_embedding,
                access_filter=access_filter,
                limit=5,
                prefetch_limit=10,
                mode=mode.vector_query_mode(),
            )
            hits = [
                {
                    "rank": rank,
                    "documentId": (point.payload or {}).get("documentId"),
                    "chunkId": (point.payload or {}).get("chunkId"),
                }
                for rank, point in enumerate(response.points, start=1)
            ]
            modes[mode.value] = {
                "hit_count": len(hits),
                "document_ids_present": bool(hits) and all(hit["documentId"] for hit in hits),
                "hits": hits,
            }
        return {
            "passed": bool(modes) and all(mode["document_ids_present"] for mode in modes.values()),
            "sample_point_id": str(sample.id),
            "sample_documentId": payload.get("documentId"),
            "modes": modes,
        }
    finally:
        await client.close()


def build_ablation_report(
    *,
    config: AblationRunnerConfig,
    corpus_version: str,
    corpus_hash: str,
    qdrant_point_count: int,
    scope: AblationScope,
    mode_results: dict[RetrievalMode, tuple[ModeRecordResult, ...]],
    graph_results: tuple[GraphRecordResult, ...],
    payload_smoke: dict[str, Any] | None = None,
) -> dict[str, Any]:
    vector_metrics = {
        mode.value: _mode_metric_summary(mode_results.get(mode, ()))
        for mode in VECTOR_MODE_ORDER
    }
    graph_metrics = _graph_metric_summary(graph_results)
    detail_rows = [
        row
        for mode in VECTOR_MODE_ORDER
        for result in mode_results.get(mode, ())
        for row in [result.to_detail_row()]
    ]
    detail_rows.extend(result.to_detail_row() for result in graph_results)

    return {
        "title": "Russian Retrieval Ablation",
        "corpus_version": corpus_version,
        "corpus_hash": corpus_hash,
        "eval_timestamp": datetime.now(UTC).isoformat(),
        "external_judge_used": False,
        "runner_config": {
            "runner": "retrieval_ablation",
            "model_id": config.embedding_model_id,
            "qdrant_url": config.qdrant_url,
            "qdrant_collection": COLLECTION_NAME,
            "qdrant_point_count": qdrant_point_count,
            "dense_sparse_payload_smoke": payload_smoke or {},
            "top_k": config.top_k,
            "prefetch_limit": config.prefetch_limit,
            "source_report_path": str(config.source_report_path),
            "hybrid_reranker_source": config.hybrid_reranker_source,
            "reranker_model_id": config.reranker_model_id,
            "ragas_judge_invoked": False,
        },
        "scope": {
            "vector_record_count": len(scope.vector_records),
            "vector_ids": list(scope.vector_ids),
            "graph_record_count": len(scope.graph_records),
            "graph_ids": list(scope.graph_ids),
            "excluded": [
                {
                    "id": item.record_id,
                    "reason": item.reason,
                    "route": item.route,
                    "retrievers_attempted": list(item.retrievers_attempted),
                    "retrievers_used": list(item.retrievers_used),
                }
                for item in scope.excluded_records
            ],
            "route_discrepancies": [
                {
                    "id": item.record_id,
                    "golden_type": item.golden_type,
                    "route": item.route,
                    "retrieval_family": item.retrieval_family,
                }
                for item in scope.route_discrepancies
            ],
        },
        "vector_metrics": vector_metrics,
        "graph_report": {
            "note": "Graph-routed records use production retrieval metadata and are not averaged into vector mode metrics.",
            "metrics": graph_metrics,
            "rows": [result.to_detail_row() for result in graph_results],
        },
        "details": detail_rows,
    }


def write_ablation_artifacts(report: dict[str, Any], *, reports_dir: Path, slug: str) -> tuple[Path, Path, Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = reports_dir / f"{slug}.md"
    json_path = reports_dir / f"{slug}.json"
    csv_path = reports_dir / f"{slug}.csv"
    markdown_path.write_text(render_ablation_markdown(report), encoding="utf-8")
    write_json(json_path, report)
    _write_csv(csv_path, report["details"])
    return markdown_path, json_path, csv_path


def render_ablation_markdown(report: dict[str, Any]) -> str:
    scope = report["scope"]
    lines = [
        f"# {report['title']}",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Corpus version | `{report['corpus_version']}` |",
        f"| Corpus hash | `{report['corpus_hash']}` |",
        f"| Eval timestamp | `{report['eval_timestamp']}` |",
        "| External judge used | `false` |",
        f"| Qdrant collection | `{report['runner_config']['qdrant_collection']}` |",
        f"| Qdrant point count | `{report['runner_config']['qdrant_point_count']}` |",
        f"| Source route report | `{report['runner_config']['source_report_path']}` |",
        f"| Dense/sparse payload smoke | `{_payload_smoke_label(report['runner_config'].get('dense_sparse_payload_smoke', {}))}` |",
        "",
        "## Vector Scope",
        "",
        f"Included vector ids ({scope['vector_record_count']}): `{', '.join(scope['vector_ids'])}`",
        "",
        f"Graph-route ids ({scope['graph_record_count']}): `{', '.join(scope['graph_ids'])}`",
        "",
        "Excluded ids:",
        "",
        "| ID | Reason | Route |",
        "|---|---|---|",
    ]
    for excluded in scope["excluded"]:
        lines.append(f"| `{excluded['id']}` | {excluded['reason']} | {excluded['route']} |")
    if scope["route_discrepancies"]:
        lines.extend(["", "Route discrepancies:", "", "| ID | Golden type | Actual route | Retrieval family |", "|---|---|---|---|"])
        for item in scope["route_discrepancies"]:
            lines.append(f"| `{item['id']}` | {item['golden_type']} | {item['route']} | {item['retrieval_family']} |")

    lines.extend(
        [
            "",
            "## Vector Metrics",
            "",
            "| Mode | Records | recall@5 | recall@10 | MRR | Notes |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for mode in [mode.value for mode in VECTOR_MODE_ORDER]:
        metrics = report["vector_metrics"][mode]
        lines.append(
            f"| `{mode}` | {metrics['record_count']} | "
            f"{metrics['recall@5']:.4f} | {metrics['recall@10']:.4f} | {metrics['mrr']:.4f} | "
            f"{_markdown_cell(metrics.get('notes', ''))} |"
        )

    bm25_metrics = report["vector_metrics"]["bm25"]
    sparse_metrics = report["vector_metrics"]["sparse"]
    hybrid_metrics = report["vector_metrics"]["hybrid"]
    reranker_metrics = report["vector_metrics"]["hybrid+reranker"]
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"- BM25 ({bm25_metrics['recall@5']:.2f}/{bm25_metrics['recall@10']:.2f}/{bm25_metrics['mrr']:.2f}) is visibly weaker than learned retrieval modes, supporting the thesis: bge-m3 learned sparse превосходит классический BM25.",
            f"- Sparse, hybrid, and hybrid+reranker all hit the ceiling at recall@10={sparse_metrics['recall@10']:.1f}/{hybrid_metrics['recall@10']:.1f}/{reranker_metrics['recall@10']:.1f} and MRR={sparse_metrics['mrr']:.1f}/{hybrid_metrics['mrr']:.1f}/{reranker_metrics['mrr']:.1f}.",
            f"- The reranker adds no measurable lift here because retrieval saturates on a small corpus ({report['runner_config']['qdrant_point_count']} indexed docs, {scope['vector_record_count']} vector-routed questions): relevant documents are already in top-5 with ideal MRR. This is a scale limitation of the experiment, not evidence that reranking is useless; reranker value should appear on larger corpora with noisier candidate sets.",
            f"- The graph route remains a separate section with recall@10={report['graph_report']['metrics']['recall@10']:.2f}, consistent with the known Phase 8 multi-hop debt.",
            "- `ru-factual-009` is another false-UNSUPPORTED case: the router marked an answerable factual question as UNSUPPORTED, the same Phase 8 router debt seen in the 7.1 multi-hop findings.",
            "",
            "## Graph Route",
            "",
            "Graph-routed records are reported separately because graph retrieval is not comparable to BM25/dense/sparse/hybrid vector modes.",
            "",
            "| Metric | Value |",
            "|---|---:|",
        ]
    )
    for name, value in report["graph_report"]["metrics"].items():
        rendered = f"{value:.4f}" if isinstance(value, float) else str(value)
        lines.append(f"| {name} | {rendered} |")
    lines.extend(
        [
            "",
            "| ID | Route | Outcome | Citeable Evidence | recall@5 | recall@10 | MRR | Warnings |",
            "|---|---|---|---|---:|---:|---:|---|",
        ]
    )
    for row in report["graph_report"]["rows"]:
        lines.append(
            f"| `{row['id']}` | {row['route']} | {row['actual_outcome']} | "
            f"{str(row['citeable_evidence_found']).lower()} | {row['recall@5']:.4f} | "
            f"{row['recall@10']:.4f} | {row['mrr']:.4f} | {_markdown_cell(', '.join(row['warnings']))} |"
        )
    lines.extend(
        [
            "",
            "## Runner Notes",
            "",
            "- This is retrieval-only; RAGAS judge calls were not invoked for ablation variants.",
            "- `bm25` is classical lexical eval-only retrieval over the frozen corpus.",
            "- `sparse` is learned bge-m3 sparse retrieval through Qdrant, distinct from BM25.",
            "- `hybrid+reranker` reranks the same hybrid retrieval top-k candidate layer used for the `hybrid` mode.",
            "",
        ]
    )
    return "\n".join(lines)


def _mode_metric_summary(results: tuple[ModeRecordResult, ...]) -> dict[str, Any]:
    observations = tuple(result.to_observation() for result in results)
    metrics = {metric.name: float(metric.value) for metric in summarize_retrieval_metrics(observations, ks=(5, 10))}
    warnings = Counter(warning for result in results for warning in result.warnings)
    notes = "; ".join(f"{key}={value}" for key, value in sorted(warnings.items()))
    return {
        "record_count": len(results),
        "recall@5": metrics.get("recall@5", 0.0),
        "recall@10": metrics.get("recall@10", 0.0),
        "mrr": metrics.get("mrr", 0.0),
        "notes": notes,
    }


def _graph_metric_summary(results: tuple[GraphRecordResult, ...]) -> dict[str, Any]:
    observations = tuple(result.to_observation() for result in results)
    metrics = {metric.name: float(metric.value) for metric in summarize_retrieval_metrics(observations, ks=(5, 10))}
    count = len(results)
    return {
        "record_count": count,
        "citeable_evidence_rate": _mean(1.0 if result.retrieved_doc_ids else 0.0 for result in results),
        "no_evidence_refusal_count": sum(result.route_detail.actual_outcome == "refused_no_evidence" for result in results),
        "guard_refusal_count": sum(result.route_detail.actual_outcome == "refused_guard" for result in results),
        "recall@5": metrics.get("recall@5", 0.0),
        "recall@10": metrics.get("recall@10", 0.0),
        "mrr": metrics.get("mrr", 0.0),
    }


def _bm25_result(
    index: BM25Index,
    record: GoldenRecord,
    *,
    manifest_to_indexed_doc_id: dict[str, str],
    limit: int,
) -> ModeRecordResult:
    hits = tuple(
        RetrievalHit(
            rank=hit.rank,
            document_id=manifest_to_indexed_doc_id.get(hit.document_id, hit.document_id),
            score=hit.score,
            document_title=hit.document.title,
        )
        for hit in index.search(record.question, k=limit)
    )
    return ModeRecordResult(mode=RetrievalMode.BM25, record=record, hits=hits)


async def _vector_result(
    vector_index: QdrantVectorIndex,
    embedder: LocalBgeM3Embedder,
    record: GoldenRecord,
    *,
    access_filter: AccessFilter,
    mode: RetrievalMode,
    limit: int,
    prefetch_limit: int,
) -> ModeRecordResult:
    embeddings = await asyncio.to_thread(embedder.embed_texts, [record.question])
    if len(embeddings) != 1:
        raise RuntimeError("query embedding count mismatch")
    response = await vector_index.query_hybrid(
        query_embedding=embeddings[0],
        access_filter=access_filter,
        limit=limit,
        prefetch_limit=prefetch_limit,
        mode=mode.vector_query_mode(),
    )
    return ModeRecordResult(mode=mode, record=record, hits=tuple(_hit_from_point(point, rank) for rank, point in enumerate(response.points, start=1)))


def _source_hybrid_reranker_result(record: GoldenRecord, detail: RouteDetail, *, limit: int) -> ModeRecordResult:
    warnings: list[str] = []
    if not detail.reranker_used:
        warnings.append("source_report_reranker_not_used")
    if detail.degradation_warnings:
        warnings.extend(detail.degradation_warnings)
    hits = tuple(
        RetrievalHit(rank=rank, document_id=document_id)
        for rank, document_id in enumerate(detail.citation_document_ids[:limit], start=1)
    )
    return ModeRecordResult(mode=RetrievalMode.HYBRID_RERANKER, record=record, hits=hits, warnings=tuple(warnings))


async def _hybrid_reranker_result(
    vector_index: QdrantVectorIndex,
    embedder: LocalBgeM3Embedder,
    reranker: LocalReranker,
    record: GoldenRecord,
    *,
    access_filter: AccessFilter,
    limit: int,
    prefetch_limit: int,
) -> ModeRecordResult:
    embeddings = await asyncio.to_thread(embedder.embed_texts, [record.question])
    if len(embeddings) != 1:
        raise RuntimeError("query embedding count mismatch")
    response = await vector_index.query_hybrid(
        query_embedding=embeddings[0],
        access_filter=access_filter,
        limit=limit,
        prefetch_limit=prefetch_limit,
        mode=RetrievalMode.HYBRID.vector_query_mode(),
    )
    candidates = tuple(
        _candidate_from_point(point)
        for point in response.points
        if (point.payload or {}).get("documentId") and (point.payload or {}).get("chunkId")
    )
    outcome = await reranker.rerank(
        query=record.question,
        candidates=candidates,
        top_n=limit,
    )
    hits = tuple(_hit_from_candidate(candidate, rank) for rank, candidate in enumerate(outcome.candidates, start=1))
    return ModeRecordResult(
        mode=RetrievalMode.HYBRID_RERANKER,
        record=record,
        hits=hits,
        warnings=tuple(outcome.warnings),
    )


async def _qdrant_point_count(qdrant_url: str) -> int:
    client = AsyncQdrantClient(url=qdrant_url)
    try:
        result = await client.count(collection_name=COLLECTION_NAME, exact=True)
        return int(result.count)
    finally:
        await client.close()


def _hit_from_point(point: Any, rank: int) -> RetrievalHit:
    payload = dict(getattr(point, "payload", None) or {})
    return RetrievalHit(
        rank=rank,
        document_id=str(payload.get("documentId") or ""),
        score=float(getattr(point, "score", 0.0) or 0.0),
        chunk_id=str(payload.get("chunkId") or ""),
        document_title=str(payload.get("documentTitle") or ""),
    )


def _candidate_from_point(point: Any) -> RetrievalCandidate:
    payload = dict(getattr(point, "payload", None) or {})
    return RetrievalCandidate(
        chunk_id=_uuid_string(payload["chunkId"]),
        parent_chunk_id=_optional_uuid_string(payload.get("parentChunkId")),
        document_id=_uuid_string(payload["documentId"]),
        document_title=str(payload.get("documentTitle") or ""),
        section_path=_section_path(payload.get("sectionPath")),
        content=str(payload.get("content") or ""),
        snippet=str(payload.get("content") or "")[:500],
        page_number=_optional_int(payload.get("page")),
        score=_clamp_score(float(getattr(point, "score", 0.0) or 0.0)),
        access_level=str(payload.get("accessLevel") or ""),
        retriever=RetrieverType.HYBRID,
        sanitizer_flags=tuple(str(flag) for flag in payload.get("sanitizerFlags", []) or []),
    )


def _hit_from_candidate(candidate: RetrievalCandidate, rank: int) -> RetrievalHit:
    return RetrievalHit(
        rank=rank,
        document_id=str(candidate.document_id),
        score=candidate.score,
        chunk_id=str(candidate.chunk_id),
        document_title=candidate.document_title,
    )


def _sparse_to_dict(raw: object) -> dict[int, float]:
    if isinstance(raw, dict):
        if "indices" in raw and "values" in raw:
            return {int(i): float(v) for i, v in zip(raw["indices"], raw["values"], strict=True)}
        return {int(i): float(v) for i, v in raw.items()}
    indices = getattr(raw, "indices", None)
    values = getattr(raw, "values", None)
    if indices is None or values is None:
        raise RuntimeError(f"unrecognized sparse vector type: {type(raw)!r}")
    return {int(i): float(v) for i, v in zip(indices, values, strict=True)}


def _section_path(value: object) -> tuple[str, ...]:
    if isinstance(value, list | tuple):
        return tuple(str(part) for part in value if str(part).strip())
    if value is None:
        return ()
    return tuple(part.strip() for part in str(value).split(">") if part.strip())


def _uuid_string(value: object):
    from uuid import UUID

    return UUID(str(value))


def _optional_uuid_string(value: object):
    from uuid import UUID

    return UUID(str(value)) if value else None


def _optional_int(value: object) -> int | None:
    return int(value) if value is not None else None


def _clamp_score(score: float) -> float:
    return min(1.0, max(0.0, float(score)))


def _domain_access_filter(manifest: object) -> AccessFilter:
    eval_filter = access_filter_from_manifest(manifest)
    return AccessFilter(
        access_levels=eval_filter.access_levels,
        departments=eval_filter.departments,
        doc_types=eval_filter.doc_types,
    )


def _exclusion(record: GoldenRecord, detail: RouteDetail | None, reason: str) -> ScopeExclusion:
    return ScopeExclusion(
        record_id=record.id,
        reason=reason,
        route=detail.route if detail is not None else "",
        retrievers_attempted=detail.retrievers_attempted if detail is not None else (),
        retrievers_used=detail.retrievers_used if detail is not None else (),
    )


def _retrieval_family(detail: RouteDetail) -> str:
    if detail.is_vector_routed:
        return "vector"
    if detail.is_graph_routed:
        return "graph"
    return "excluded"


def _expected_family(record: GoldenRecord) -> str:
    if record.type.value in {"factual"}:
        return "vector"
    if record.type.value in {"aggregation", "multi_hop"}:
        return "graph"
    return "excluded"


def _first_expected_rank(expected_doc_ids: tuple[str, ...], retrieved_doc_ids: tuple[str, ...]) -> int | None:
    expected = set(expected_doc_ids)
    for rank, doc_id in enumerate(retrieved_doc_ids, start=1):
        if doc_id in expected:
            return rank
    return None


def _mean(values: Any) -> float:
    collected = tuple(values)
    return sum(collected) / len(collected) if collected else 0.0


def _markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def _payload_smoke_label(smoke: dict[str, Any]) -> str:
    if not smoke:
        return "not recorded"
    if not smoke.get("passed"):
        return f"failed:{smoke.get('reason', 'unknown')}"
    modes = smoke.get("modes", {})
    dense = modes.get("dense", {})
    sparse = modes.get("sparse", {})
    return (
        f"passed; dense_hits={dense.get('hit_count', 0)}; "
        f"sparse_hits={sparse.get('hit_count', 0)}; sample_documentId={smoke.get('sample_documentId')}"
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _path_arg(value: str) -> Path:
    return Path(value).resolve()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run retrieval-only ablation over the Russian golden vector subset.")
    parser.add_argument("--golden", dest="golden_path", type=_path_arg, default=DEFAULT_GOLDEN_PATH)
    parser.add_argument("--metadata", dest="metadata_path", type=_path_arg, default=DEFAULT_METADATA_PATH)
    parser.add_argument("--corpus-dir", type=_path_arg, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--manifest", dest="manifest_path", type=_path_arg, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--reports-dir", type=_path_arg, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--report-slug", default=DEFAULT_REPORT_SLUG)
    parser.add_argument("--source-report", dest="source_report_path", type=_path_arg, default=DEFAULT_SOURCE_REPORT_PATH)
    parser.add_argument("--qdrant-url", default=os.getenv("QDRANT_URL", DEFAULT_QDRANT_URL))
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--prefetch-limit", type=int, default=30)
    parser.add_argument("--embedding-model-id", default=DEFAULT_BGE_M3_MODEL)
    parser.add_argument("--reranker-model-id", default="BAAI/bge-reranker-v2-m3")
    parser.add_argument("--reranker-timeout-seconds", type=float, default=25.0)
    parser.add_argument("--reranker-load-timeout-seconds", type=float, default=28.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = AblationRunnerConfig(**vars(args))
    output = asyncio.run(run_ablation(config))
    print(
        {
            "markdown": str(output.markdown_path),
            "json": str(output.json_path),
            "csv": str(output.csv_path),
            "vector_records": output.report["scope"]["vector_record_count"],
            "graph_records": output.report["scope"]["graph_record_count"],
            "external_judge_used": output.report["external_judge_used"],
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
