from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import bm25s

from eval.schema import CorpusManifest


@dataclass(frozen=True, slots=True)
class BM25Document:
    document_id: str
    text: str
    title: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BM25Hit:
    document_id: str
    score: float
    rank: int
    document: BM25Document


class BM25Index:
    def __init__(self, documents: Sequence[BM25Document]) -> None:
        if not documents:
            raise ValueError("BM25Index requires at least one document")
        self._documents = tuple(documents)
        tokenized = _tokenize([document.text for document in self._documents])
        self._retriever = bm25s.BM25(corpus=list(self._documents))
        self._retriever.index(tokenized, show_progress=False)

    @classmethod
    def from_corpus(cls, corpus_dir: Path, manifest: CorpusManifest) -> BM25Index:
        documents = [
            BM25Document(
                document_id=entry.doc_id,
                title=entry.title,
                text=(corpus_dir / entry.path).read_text(encoding="utf-8"),
                metadata={
                    "language": entry.language,
                    "department": entry.department,
                    "doc_type": entry.doc_type,
                    "access_level": entry.access_level,
                },
            )
            for entry in sorted(manifest.documents, key=lambda item: item.doc_id)
        ]
        return cls(documents)

    def search(self, query: str, *, k: int = 10, min_score: float = 0.0) -> tuple[BM25Hit, ...]:
        if k < 1:
            raise ValueError("k must be positive")
        query_tokens = _tokenize([query])
        results = self._retriever.retrieve(
            query_tokens,
            corpus=list(self._documents),
            k=min(k, len(self._documents)),
            show_progress=False,
        )
        documents = results.documents[0]
        scores = results.scores[0]
        hits: list[BM25Hit] = []
        for rank, (document, score) in enumerate(zip(documents, scores, strict=True), start=1):
            score_value = float(score)
            if score_value <= min_score:
                continue
            hits.append(
                BM25Hit(
                    document_id=document.document_id,
                    score=score_value,
                    rank=rank,
                    document=document,
                )
            )
        return tuple(hits)


def _tokenize(texts: Sequence[str]) -> Any:
    return bm25s.tokenize(
        list(texts),
        lower=True,
        stopwords=[],
        show_progress=False,
        leave=False,
    )
