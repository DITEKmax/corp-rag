from __future__ import annotations

from uuid import UUID

import pytest

from corp_rag_ai.pipeline.indexing.graph_indexer import (
    GraphDocument,
    GraphDocumentIndex,
    GraphEntity,
    GraphEvidence,
    GraphRelationMention,
    Neo4jGraphIndex,
    build_graph_entity,
    deterministic_entity_id,
    deterministic_relation_mention_id,
    normalize_entity_name,
    normalize_relation_type,
)


class _FakeResult:
    async def consume(self) -> None:
        return None


class _FakeTx:
    def __init__(self) -> None:
        self.runs: list[tuple[str, dict[str, object]]] = []

    async def run(self, query: str, **kwargs):
        self.runs.append((query, kwargs))
        return _FakeResult()


class _FakeWriteSession:
    def __init__(self) -> None:
        self.tx = _FakeTx()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args) -> None:
        return None

    async def execute_write(self, callback, *args):
        return await callback(self.tx, *args)


class _FakeDriver:
    def __init__(self, session: _FakeWriteSession) -> None:
        self.session_instance = session

    def session(self, **_kwargs):
        return self.session_instance

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_replace_document_graph_cleans_document_only_and_merges_provenance_shape() -> None:
    session = _FakeWriteSession()
    graph_index = Neo4jGraphIndex(_FakeDriver(session))
    document_id = UUID("11111111-1111-1111-1111-111111111111")
    source = _entity(
        name="Alice Ivanova",
        entity_type="person",
        embedding=(0.1, 0.2),
        evidence=GraphEvidence(
            chunk_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            parent_chunk_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            section_path=("HR", "Access"),
        ),
    )
    target = _entity(name="VPN Policy", entity_type="policy", embedding=(0.3, 0.4))
    relation = GraphRelationMention(
        relation_id=deterministic_relation_mention_id(
            source.entity_id,
            target.entity_id,
            "GOVERNS_ACCESS",
        ),
        relation_type="GOVERNS_ACCESS",
        source_entity_id=source.entity_id,
        target_entity_id=target.entity_id,
        description="VPN Policy governs Alice's access.",
        evidence=source.mentions,
    )

    await graph_index.replace_document_graph(
        GraphDocumentIndex(
            document=GraphDocument(
                document_id=document_id,
                title="HR Access Policy",
                access_level="INTERNAL",
                department="HR",
                doc_type="POLICY",
                language="en",
            ),
            entities=(source, target),
            relations=(relation,),
        )
    )

    queries = [query for query, _params in session.tx.runs]
    assert queries[0] == "MATCH (d:Document {id: $documentId}) DETACH DELETE d"
    joined_queries = "\n".join(queries)
    assert ":Chunk" not in joined_queries
    assert "DETACH DELETE e" not in joined_queries
    assert "DETACH DELETE r" not in joined_queries
    assert "MERGE (d:Document {id: $document.id})" in joined_queries
    assert "MERGE (e:Entity {id: entity.id})" in joined_queries
    assert "ON CREATE SET e.name" in joined_queries
    assert "e.description = entity.description" in joined_queries
    assert "ON MATCH SET e.embedding" in joined_queries
    assert "MERGE (r:RelationMention {id: relation.id})" in joined_queries
    assert "MERGE (r)-[:SOURCE]->(source)" in joined_queries
    assert "MERGE (r)-[:TARGET]->(target)" in joined_queries
    assert "MERGE (r)-[ev:EVIDENCE" in joined_queries

    entity_params = session.tx.runs[2][1]
    entity_payload = entity_params["entities"][0]
    assert entity_payload["embedding"] == [0.1, 0.2]
    assert entity_payload["normalizedName"] == "alice ivanova"
    assert entity_payload["type"] == "person"

    mention_params = session.tx.runs[3][1]
    assert mention_params["mentions"] == [
        {
            "chunkId": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "parentChunkId": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "sectionPath": ["HR", "Access"],
            "entityId": str(source.entity_id),
        }
    ]


@pytest.mark.asyncio
async def test_cleanup_document_uses_locked_document_detach_delete() -> None:
    session = _FakeWriteSession()
    graph_index = Neo4jGraphIndex(_FakeDriver(session))

    await graph_index.cleanup_document(UUID("22222222-2222-2222-2222-222222222222"))

    assert session.tx.runs == [
        (
            "MATCH (d:Document {id: $documentId}) DETACH DELETE d",
            {"documentId": "22222222-2222-2222-2222-222222222222"},
        )
    ]


def test_deterministic_entity_and_relation_ids_use_normalized_names_and_types() -> None:
    normalized_name = normalize_entity_name("  Alice   Ivanova ")
    person_id = deterministic_entity_id(normalized_name, "person")
    same_person_id = deterministic_entity_id("alice ivanova", "PERSON")
    target_id = deterministic_entity_id("vpn policy", "policy")

    assert normalized_name == "alice ivanova"
    assert person_id == same_person_id
    assert normalize_relation_type("governs access") == "GOVERNS_ACCESS"
    assert deterministic_relation_mention_id(person_id, target_id, "governs access") == (
        deterministic_relation_mention_id(person_id, target_id, "GOVERNS_ACCESS")
    )


def _entity(
    *,
    name: str,
    entity_type: str,
    embedding: tuple[float, ...],
    evidence: GraphEvidence | None = None,
) -> GraphEntity:
    return build_graph_entity(
        name=name,
        entity_type=entity_type,
        description=f"{name} description",
        embedding=embedding,
        mentions=() if evidence is None else (evidence,),
    )
