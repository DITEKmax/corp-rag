from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GoldenQuestionType(str, Enum):
    FACTUAL = "factual"
    AGGREGATION = "aggregation"
    MULTI_HOP = "multi_hop"
    OUT_OF_SCOPE = "out_of_scope"


class ExpectedOutcome(str, Enum):
    ANSWERED = "answered"
    REFUSED_NO_EVIDENCE = "refused_no_evidence"
    REFUSED_GUARD = "refused_guard"


class GoldenRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: GoldenQuestionType
    question: str
    reference_answer: str
    expected_doc_ids: list[str] = Field(default_factory=list)
    expected_chunk_hint: str | None = None
    expected_outcome: ExpectedOutcome
    notes: str = ""

    @field_validator("id", "question", "reference_answer")
    @classmethod
    def _required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("field must be non-empty")
        return value

    @field_validator("expected_doc_ids")
    @classmethod
    def _dedupe_doc_ids(cls, value: list[str]) -> list[str]:
        result: list[str] = []
        for item in value:
            doc_id = item.strip()
            if doc_id and doc_id not in result:
                result.append(doc_id)
        return result

    @model_validator(mode="after")
    def _answered_requires_docs(self) -> GoldenRecord:
        if self.expected_outcome is ExpectedOutcome.ANSWERED and not self.expected_doc_ids:
            raise ValueError("answered golden records require expected_doc_ids")
        return self


class CorpusManifestEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    title: str
    path: str
    language: str = "ru"
    department: str
    doc_type: str
    access_level: str
    summary: str

    @field_validator("doc_id", "title", "path", "language", "department", "doc_type", "access_level", "summary")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("field must be non-empty")
        return value


class CorpusManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    corpus_version: str
    language: str = "ru"
    documents: list[CorpusManifestEntry]

    @model_validator(mode="after")
    def _doc_ids_unique(self) -> CorpusManifest:
        ids = [entry.doc_id for entry in self.documents]
        if len(ids) != len(set(ids)):
            raise ValueError("corpus manifest doc_id values must be unique")
        return self


class CorpusMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    corpus_version: str
    corpus_hash: str
    hash_algorithm: str = "sha256"
    document_count: int
    language: str = "ru"
    source_manifest: str
    frozen_at: datetime
    golden_authoring_status: str
    indexed: bool = False
    indexed_document_ids: list[str] = Field(default_factory=list)
    notes: str = ""


class RunnerConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    runner: str
    model_id: str
    corpus_version: str
    corpus_hash: str
    external_judge_used: bool = False
    options: dict[str, Any] = Field(default_factory=dict)


class MetricSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    value: float | int | str
    threshold: float | int | None = None
    passed: bool | None = None
    notes: str = ""


class ReportArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    markdown_path: Path
    json_path: Path
    csv_path: Path | None = None


class EvaluationReport(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str
    corpus_version: str
    corpus_hash: str
    model_id: str
    eval_timestamp: datetime
    runner_config: RunnerConfig
    external_judge_used: bool
    metrics: list[MetricSummary]
    details: list[dict[str, Any]] = Field(default_factory=list)
