from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module


@dataclass(frozen=True, slots=True)
class AmqpTopology:
    documents_exchange: str
    document_uploaded_queue: str
    document_deleted_queue: str
    document_indexed_routing_key: str
    document_indexing_failed_routing_key: str


def load_generated_topology() -> AmqpTopology:
    try:
        exchange_names = import_module("corp_rag_ai.contracts.generated.exchange_names")
        queue_names = import_module("corp_rag_ai.contracts.generated.queue_names")
        routing_keys = import_module("corp_rag_ai.contracts.generated.routing_keys")
    except ModuleNotFoundError as exc:
        raise RuntimeError("Generated contract constants are missing; run contract codegen first.") from exc

    return AmqpTopology(
        documents_exchange=exchange_names.DOCUMENTS_TOPIC,
        document_uploaded_queue=queue_names.AI_DOCUMENT_UPLOADED,
        document_deleted_queue=queue_names.AI_DOCUMENT_DELETED,
        document_indexed_routing_key=routing_keys.DOCUMENT_INDEXED,
        document_indexing_failed_routing_key=routing_keys.DOCUMENT_INDEXING_FAILED,
    )

