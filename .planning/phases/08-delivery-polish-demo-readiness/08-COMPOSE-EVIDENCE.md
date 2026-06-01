# Phase 8 Compose Readiness Evidence

- Success: `true`
- Generated at: `2026-06-01T21:36:22.244192Z`
- Compose file: `infra/docker-compose.yml`
- Env file: `infra/.env`
- Services healthy: `9/9`

## Services

| Service | Container | State | Health | Status |
|---------|-----------|-------|--------|--------|
| postgres | corp-rag-postgres-1 | running | healthy | Up 29 minutes (healthy) |
| minio | corp-rag-minio-1 | running | healthy | Up 29 minutes (healthy) |
| rabbitmq | corp-rag-rabbitmq-1 | running | healthy | Up 29 minutes (healthy) |
| qdrant | corp-rag-qdrant-1 | running | healthy | Up 29 minutes (healthy) |
| neo4j | corp-rag-neo4j-1 | running | healthy | Up 29 minutes (healthy) |
| langfuse | corp-rag-langfuse-1 | running | healthy | Up 29 minutes (healthy) |
| java-backend | corp-rag-java-backend-1 | running | healthy | Up 29 minutes (healthy) |
| python-ai | corp-rag-python-ai-1 | running | healthy | Up 29 minutes (healthy) |
| frontend | corp-rag-frontend-1 | running | healthy | Up 29 minutes (healthy) |

## Diagnostics

`{"amqp_connection": true, "amqp_runtime": true, "answered_count": 0, "answered_rate": 0.0, "graph_index": true, "guard_blocked_count": 0, "langfuse_configured": true, "langfuse_reachable": true, "llm_reachable": true, "mean_latency_ms": 0, "qdrant_index": true, "query_count": 0, "query_prewarm_embedding_ready": true, "query_prewarm_enabled": true, "query_prewarm_reranker_ready": true, "query_router": true, "query_service": true, "refused_no_evidence_count": 0, "reranker_configured": true, "reranker_degraded_count": 0}`

## Docker Memory

`{"docker_total_bytes": 12544360448, "documented_python_ai_limit": "10g", "documented_python_ai_reservation": "8g", "documented_wsl_memory": "12GB", "python_ai_container": "c919bba1e218f017d52ef560dac6e5b6f1bf3c9f391fbc190a15572bb3b7e5c0", "python_ai_limit_bytes": 10737418240, "python_ai_reservation_bytes": 8589934592}`
