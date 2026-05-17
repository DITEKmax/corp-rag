from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest

from corp_rag_ai.pipeline.indexing.embedding import EmbeddingVector
from corp_rag_ai.pipeline.indexing.entity_extractor import (
    DeepSeekEntityExtractor,
    EntityExtractionSource,
    build_graph_document_index,
)
from corp_rag_ai.pipeline.indexing.graph_indexer import GraphDocument

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "entity_extraction" / "01_hr_policy_basic.json"


class _FakeResponse:
    def __init__(self, payload) -> None:
        self.choices = [_FakeChoice(json.dumps(payload))]


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeCompletions:
    def __init__(self, payload) -> None:
        self.payload = payload

    async def create(self, **_kwargs):
        return _FakeResponse(self.payload)


class _FakeChat:
    def __init__(self, payload) -> None:
        self.completions = _FakeCompletions(payload)


class _FakeClient:
    def __init__(self, payload) -> None:
        self.chat = _FakeChat(payload)


class _FakeEmbedder:
    def __init__(self) -> None:
        self.text_batches: list[list[str]] = []

    def embed_texts(self, texts) -> tuple[EmbeddingVector, ...]:
        batch = list(texts)
        self.text_batches.append(batch)
        return tuple(
            EmbeddingVector(
                dense=(float(index), float(index) + 0.5),
                sparse={index + 1: 1.0},
            )
            for index, _text in enumerate(batch)
        )


async def _no_sleep(_seconds: float) -> None:
    return None


@pytest.mark.asyncio
async def test_golden_fixture_maps_deduplicates_and_embeds_unique_entities() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    extractor = DeepSeekEntityExtractor(
        client=_FakeClient(fixture["mockDeepSeekResponse"]),
        sleep=_no_sleep,
    )
    parent_result = await extractor.extract_parent(
        _source(fixture["sources"][0]),
        document_title=fixture["document"]["title"],
        language=fixture["document"]["language"],
    )
    embedder = _FakeEmbedder()

    graph = build_graph_document_index(
        document=_document(fixture["document"]),
        parent_extractions=[parent_result],
        embedder=embedder,
    )

    expected_entity_keys = [tuple(item) for item in fixture["expected"]["entityKeys"]]
    actual_entity_keys = [(entity.normalized_name, entity.entity_type) for entity in graph.entities]
    assert actual_entity_keys == expected_entity_keys
    assert [relation.relation_type for relation in graph.relations] == fixture["expected"]["relationTypes"]
    assert len({entity.entity_id for entity in graph.entities}) == len(graph.entities)
    assert len({relation.relation_id for relation in graph.relations}) == len(graph.relations)
    assert len(embedder.text_batches) == 1
    assert len(embedder.text_batches[0]) == len(graph.entities)
    assert all("type:" in text for text in embedder.text_batches[0])
    assert [entity.embedding for entity in graph.entities] == [
        (0.0, 0.5),
        (1.0, 1.5),
        (2.0, 2.5),
        (3.0, 3.5),
    ]

    hr_department = graph.entities[0]
    assert hr_department.description == "Department that owns the remote work policy."
    assert len(hr_department.mentions) == 1
    assert hr_department.mentions[0].chunk_id == UUID(fixture["sources"][0]["chunkId"])


def _source(raw: dict[str, object]) -> EntityExtractionSource:
    return EntityExtractionSource(
        text=str(raw["text"]),
        chunk_id=UUID(str(raw["chunkId"])),
        parent_chunk_id=UUID(str(raw["parentChunkId"])),
        section_path=tuple(str(item) for item in raw["sectionPath"]),
    )


def _document(raw: dict[str, object]) -> GraphDocument:
    return GraphDocument(
        document_id=UUID(str(raw["documentId"])),
        title=str(raw["title"]),
        access_level=str(raw["accessLevel"]),
        department=str(raw["department"]),
        doc_type=str(raw["docType"]),
        language=str(raw["language"]),
    )
