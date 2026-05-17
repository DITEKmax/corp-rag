from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid5

from corp_rag_ai.domain.exceptions import (
    DEPENDENCY_UNAVAILABLE,
    INDEXING_PIPELINE_ERROR,
    IndexingStage,
    StageFailure,
    stage_failure,
)
from corp_rag_ai.pipeline.indexing.embedding import BGE_M3_DENSE_DIMENSION

ENTITY_EXTRACTION_NAMESPACE = UUID("f35ff807-8637-4798-a3fe-7b47f98c330d")
ENTITY_TYPES = ("person", "department", "policy", "system", "procedure", "role", "date", "concept")

VECTOR_INDEX_NAME = "entity_embedding_idx"
VECTOR_INDEX_TIMEOUT_SECONDS = 5.0
VECTOR_INDEX_POLL_SECONDS = 0.1
ONLINE_VECTOR_STATES = {"ONLINE", "POPULATING"}

_ENTITY_INDEX_QUERIES = (
    "CREATE INDEX entity_normalized_name_idx IF NOT EXISTS FOR (e:Entity) ON (e.normalizedName)",
    "CREATE INDEX entity_type_idx IF NOT EXISTS FOR (e:Entity) ON (e.type)",
    "CREATE INDEX document_id_idx IF NOT EXISTS FOR (d:Document) ON (d.id)",
    "CREATE INDEX document_access_level_idx IF NOT EXISTS FOR (d:Document) ON (d.accessLevel)",
    "CREATE INDEX relation_mention_type_idx IF NOT EXISTS FOR (r:RelationMention) ON (r.type)",
    f"""CREATE VECTOR INDEX {VECTOR_INDEX_NAME} IF NOT EXISTS
FOR (e:Entity)
ON e.embedding
OPTIONS {{ indexConfig: {{
  `vector.dimensions`: {BGE_M3_DENSE_DIMENSION},
  `vector.similarity_function`: 'cosine'
}}}}""",
)

_CLEANUP_DOCUMENT_QUERY = "MATCH (d:Document {id: $documentId}) DETACH DELETE d"
_MERGE_DOCUMENT_QUERY = """
MERGE (d:Document {id: $document.id})
SET d.title = $document.title,
    d.accessLevel = $document.accessLevel,
    d.department = $document.department,
    d.docType = $document.docType,
    d.language = $document.language
"""
_MERGE_ENTITIES_QUERY = """
UNWIND $entities AS entity
MERGE (e:Entity {id: entity.id})
ON CREATE SET e.name = entity.name,
              e.normalizedName = entity.normalizedName,
              e.type = entity.type,
              e.description = entity.description,
              e.embedding = entity.embedding
ON MATCH SET e.embedding = coalesce(e.embedding, entity.embedding)
"""
_MERGE_MENTIONS_QUERY = """
MATCH (d:Document {id: $documentId})
UNWIND $mentions AS mention
MATCH (e:Entity {id: mention.entityId})
MERGE (e)-[m:MENTIONED_IN {
  chunkId: mention.chunkId,
  parentChunkId: mention.parentChunkId
}]->(d)
SET m.sectionPath = mention.sectionPath
"""
_MERGE_RELATIONS_QUERY = """
MATCH (d:Document {id: $documentId})
UNWIND $relations AS relation
MATCH (source:Entity {id: relation.sourceEntityId})
MATCH (target:Entity {id: relation.targetEntityId})
MERGE (r:RelationMention {id: relation.id})
ON CREATE SET r.type = relation.type,
              r.description = relation.description
MERGE (r)-[:SOURCE]->(source)
MERGE (r)-[:TARGET]->(target)
WITH d, r, relation
UNWIND relation.evidence AS evidence
MERGE (r)-[ev:EVIDENCE {
  chunkId: evidence.chunkId,
  parentChunkId: evidence.parentChunkId
}]->(d)
"""


class Neo4jGraphSchemaError(RuntimeError):
    """Raised when Neo4j graph schema initialization cannot satisfy the contract."""


@dataclass(frozen=True, slots=True)
class GraphDocument:
    document_id: UUID
    title: str
    access_level: str
    department: str
    doc_type: str
    language: str

    def to_cypher(self) -> dict[str, str]:
        return {
            "id": str(self.document_id),
            "title": self.title,
            "accessLevel": self.access_level,
            "department": self.department,
            "docType": self.doc_type,
            "language": self.language,
        }


@dataclass(frozen=True, slots=True)
class GraphEvidence:
    chunk_id: UUID
    parent_chunk_id: UUID
    section_path: tuple[str, ...] = ()

    def to_cypher(self) -> dict[str, object]:
        return {
            "chunkId": str(self.chunk_id),
            "parentChunkId": str(self.parent_chunk_id),
            "sectionPath": list(self.section_path),
        }


@dataclass(frozen=True, slots=True)
class GraphEntity:
    entity_id: UUID
    name: str
    normalized_name: str
    entity_type: str
    description: str
    embedding: tuple[float, ...]
    mentions: tuple[GraphEvidence, ...] = ()

    def to_cypher(self) -> dict[str, object]:
        return {
            "id": str(self.entity_id),
            "name": self.name,
            "normalizedName": self.normalized_name,
            "type": self.entity_type,
            "description": self.description,
            "embedding": [float(value) for value in self.embedding],
        }


@dataclass(frozen=True, slots=True)
class GraphRelationMention:
    relation_id: UUID
    relation_type: str
    source_entity_id: UUID
    target_entity_id: UUID
    description: str
    evidence: tuple[GraphEvidence, ...] = ()

    def to_cypher(self) -> dict[str, object]:
        return {
            "id": str(self.relation_id),
            "type": self.relation_type,
            "sourceEntityId": str(self.source_entity_id),
            "targetEntityId": str(self.target_entity_id),
            "description": self.description,
            "evidence": [item.to_cypher() for item in self.evidence],
        }


@dataclass(frozen=True, slots=True)
class GraphDocumentIndex:
    document: GraphDocument
    entities: tuple[GraphEntity, ...] = ()
    relations: tuple[GraphRelationMention, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_cypher(self) -> dict[str, object]:
        mentions: list[dict[str, object]] = []
        for entity in self.entities:
            for mention in entity.mentions:
                item = mention.to_cypher()
                item["entityId"] = str(entity.entity_id)
                mentions.append(item)
        return {
            "document": self.document.to_cypher(),
            "entities": [entity.to_cypher() for entity in self.entities],
            "mentions": mentions,
            "relations": [relation.to_cypher() for relation in self.relations],
        }


@dataclass(slots=True)
class _GraphEntityBuilder:
    entity_id: UUID
    name: str
    normalized_name: str
    entity_type: str
    description: str
    mentions: list[GraphEvidence] = field(default_factory=list)


@dataclass(slots=True)
class _GraphRelationBuilder:
    relation_id: UUID
    relation_type: str
    source_entity_id: UUID
    target_entity_id: UUID
    description: str
    evidence: list[GraphEvidence] = field(default_factory=list)


class Neo4jGraphIndex:
    def __init__(self, driver: Any, *, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    @classmethod
    def from_uri(
        cls,
        uri: str,
        *,
        user: str,
        password: str,
        database: str = "neo4j",
    ) -> Neo4jGraphIndex:
        from neo4j import AsyncGraphDatabase

        return cls(AsyncGraphDatabase.driver(uri, auth=(user, password)), database=database)

    async def close(self) -> None:
        await self._driver.close()

    async def ensure_graph_schema(
        self,
        *,
        timeout_seconds: float = VECTOR_INDEX_TIMEOUT_SECONDS,
        poll_interval_seconds: float = VECTOR_INDEX_POLL_SECONDS,
    ) -> None:
        async with self._driver.session(database=self._database) as session:
            for query in _ENTITY_INDEX_QUERIES:
                result = await session.run(query)
                await _consume(result)
            await _wait_for_vector_index(
                session,
                timeout_seconds=timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
            )

    async def cleanup_document(self, document_id: UUID | str) -> None:
        async with self._driver.session(database=self._database) as session:
            try:
                await session.execute_write(_cleanup_document_graph, str(document_id))
            except StageFailure:
                raise
            except Exception as exc:  # pragma: no cover - exact Neo4j exceptions vary
                raise _graph_failure(exc) from exc

    async def replace_document_graph(self, document_graph: GraphDocumentIndex) -> None:
        params = document_graph.to_cypher()
        async with self._driver.session(database=self._database) as session:
            try:
                await session.execute_write(_write_document_graph, params)
            except StageFailure:
                raise
            except Exception as exc:  # pragma: no cover - exact Neo4j exceptions vary
                raise _graph_failure(exc) from exc


def normalize_entity_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def normalize_entity_type(entity_type: str) -> str:
    normalized = entity_type.strip().lower()
    if normalized not in ENTITY_TYPES:
        raise ValueError(f"unknown entity type: {entity_type}")
    return normalized


def normalize_relation_type(relation_type: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", relation_type.strip()).strip("_").upper()
    if not normalized:
        raise ValueError("relation type must not be blank")
    return normalized


def deterministic_entity_id(normalized_name: str, entity_type: str) -> UUID:
    return uuid5(ENTITY_EXTRACTION_NAMESPACE, f"{normalized_name}:{normalize_entity_type(entity_type)}")


def deterministic_relation_mention_id(source_entity_id: UUID, target_entity_id: UUID, relation_type: str) -> UUID:
    return uuid5(source_entity_id, f"{target_entity_id}:{normalize_relation_type(relation_type)}")


def build_graph_entity(
    *,
    name: str,
    entity_type: str,
    description: str,
    embedding: Sequence[float],
    mentions: Sequence[GraphEvidence] = (),
) -> GraphEntity:
    normalized_type = normalize_entity_type(entity_type)
    normalized_name = normalize_entity_name(name)
    return GraphEntity(
        entity_id=deterministic_entity_id(normalized_name, normalized_type),
        name=name.strip(),
        normalized_name=normalized_name,
        entity_type=normalized_type,
        description=description.strip(),
        embedding=tuple(float(value) for value in embedding),
        mentions=tuple(mentions),
    )


async def _cleanup_document_graph(tx: Any, document_id: str) -> None:
    result = await tx.run(_CLEANUP_DOCUMENT_QUERY, documentId=document_id)
    await _consume(result)


async def _write_document_graph(tx: Any, params: Mapping[str, object]) -> None:
    document_id = params["document"]["id"]  # type: ignore[index]
    for query, kwargs in (
        (_CLEANUP_DOCUMENT_QUERY, {"documentId": document_id}),
        (_MERGE_DOCUMENT_QUERY, {"document": params["document"]}),
        (_MERGE_ENTITIES_QUERY, {"entities": params["entities"]}),
        (_MERGE_MENTIONS_QUERY, {"documentId": document_id, "mentions": params["mentions"]}),
        (_MERGE_RELATIONS_QUERY, {"documentId": document_id, "relations": params["relations"]}),
    ):
        result = await tx.run(query, **kwargs)
        await _consume(result)


async def _wait_for_vector_index(
    session: Any,
    *,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        result = await session.run("SHOW VECTOR INDEXES YIELD name, state RETURN name, state")
        for record in await _records(result):
            name = _record_value(record, "name")
            state = str(_record_value(record, "state") or "").upper()
            if name != VECTOR_INDEX_NAME:
                continue
            if state in ONLINE_VECTOR_STATES:
                return
            if state == "FAILED":
                raise Neo4jGraphSchemaError(f"Neo4j vector index {VECTOR_INDEX_NAME} is FAILED")
        await asyncio.sleep(poll_interval_seconds)
    raise Neo4jGraphSchemaError(
        f"Timed out waiting {timeout_seconds:.1f}s for Neo4j vector index "
        f"{VECTOR_INDEX_NAME} to reach ONLINE or POPULATING"
    )


async def _consume(result: Any) -> None:
    consume = getattr(result, "consume", None)
    if consume is None:
        return
    consumed = consume()
    if hasattr(consumed, "__await__"):
        await consumed


async def _records(result: Any) -> list[Any]:
    data = getattr(result, "data", None)
    if data is not None:
        records = data()
        if hasattr(records, "__await__"):
            records = await records
        return list(records)
    if hasattr(result, "__aiter__"):
        return [record async for record in result]
    return list(result or [])


def _record_value(record: Any, key: str) -> Any:
    if isinstance(record, Mapping):
        return record.get(key)
    getter = getattr(record, "get", None)
    if getter is not None:
        return getter(key)
    return getattr(record, key, None)


def _graph_failure(exc: Exception) -> StageFailure:
    retryable = _is_dependency_error(exc)
    return stage_failure(
        stage=IndexingStage.GRAPH_UPSERT,
        error_code=DEPENDENCY_UNAVAILABLE if retryable else INDEXING_PIPELINE_ERROR,
        retryable=retryable,
        detail=exc.__class__.__name__,
    )


def _is_dependency_error(exc: Exception) -> bool:
    name = exc.__class__.__name__.lower()
    return "serviceunavailable" in name or "sessionexpired" in name or "timeout" in name or "transient" in name
