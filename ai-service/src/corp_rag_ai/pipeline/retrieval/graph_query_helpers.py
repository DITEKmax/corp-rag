from __future__ import annotations

import re

from corp_rag_ai.domain.query import AccessFilter


DOCUMENT_ACCESS_PREDICATE = (
    "{alias}.accessLevel IN $accessLevels "
    "AND {alias}.docType IN $docTypes "
    "AND ($departmentWildcard = true OR {alias}.department IN $departments)"
)


def graph_access_params(access_filter: AccessFilter) -> dict[str, object]:
    return {
        "accessLevels": list(access_filter.access_levels),
        "docTypes": list(access_filter.doc_types),
        "departments": list(access_filter.departments),
        "departmentWildcard": access_filter.department_wildcard,
    }


def document_access_predicate(alias: str = "d") -> str:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", alias):
        raise ValueError("Cypher alias must be a simple identifier")
    return DOCUMENT_ACCESS_PREDICATE.format(alias=alias)


def aggregation_query() -> str:
    return f"""
WITH $queryTerms AS queryTerms
MATCH (e:Entity)-[mention:MENTIONED_IN]->(d:Document)
WHERE {document_access_predicate("d")}
WITH e, mention, d, queryTerms,
     [term IN queryTerms WHERE
        toLower(d.title) CONTAINS term OR
        toLower(e.name) CONTAINS term OR
        toLower(coalesce(e.type, '')) CONTAINS term OR
        toLower(coalesce(d.department, '')) CONTAINS term
     ] AS matchedTerms
WHERE size(queryTerms) > 0 AND size(matchedTerms) > 0
WITH e, mention, d, matchedTerms,
     toFloat(size(matchedTerms)) / toFloat(size(queryTerms)) AS queryMatchScore
RETURN mention.chunkId AS chunkId,
       mention.parentChunkId AS parentChunkId,
       mention.sectionPath AS sectionPath,
       d.id AS documentId,
       d.title AS documentTitle,
       d.accessLevel AS accessLevel,
       e.name AS entityName,
       e.type AS entityType,
       'entity:' + e.name AS graphPath,
       matchedTerms AS matchedTerms,
       queryMatchScore AS score
ORDER BY queryMatchScore DESC, e.name
LIMIT $limit
"""


def multi_hop_query(max_hops: int) -> str:
    hops = _validated_hops(max_hops)
    return f"""
MATCH path=(start:Entity)-[:SOURCE|TARGET*1..{hops}]-(relation:RelationMention)-[evidence:EVIDENCE]->(d:Document)
WHERE {document_access_predicate("d")}
RETURN evidence.chunkId AS chunkId,
       evidence.parentChunkId AS parentChunkId,
       evidence.sectionPath AS sectionPath,
       d.id AS documentId,
       d.title AS documentTitle,
       d.accessLevel AS accessLevel,
       relation.type AS relationType,
       relation.description AS relationDescription,
       reduce(summary = '', node IN nodes(path) | summary + coalesce(node.name, node.type, '') + ' ') AS graphPath,
       0.8 AS score
LIMIT $limit
"""


def comparison_query() -> str:
    return f"""
MATCH (e:Entity)-[mention:MENTIONED_IN]->(d:Document)
WHERE {document_access_predicate("d")}
  AND ($entityNames = [] OR any(name IN $entityNames WHERE e.normalizedName CONTAINS name))
RETURN mention.chunkId AS chunkId,
       mention.parentChunkId AS parentChunkId,
       mention.sectionPath AS sectionPath,
       d.id AS documentId,
       d.title AS documentTitle,
       d.accessLevel AS accessLevel,
       e.name AS entityName,
       e.normalizedName AS normalizedEntityName,
       e.type AS entityType,
       'comparison:' + e.name AS graphPath,
       0.7 AS score
ORDER BY e.normalizedName
LIMIT $limit
"""


def _validated_hops(max_hops: int) -> int:
    if max_hops < 1 or max_hops > 3:
        raise ValueError("graph traversal max_hops must be between 1 and 3")
    return max_hops
