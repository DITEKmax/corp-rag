# Local Demo Stack Runbook

This repository uses one local Docker Compose topology for the MVP demo:
`infra/docker-compose.yml`. It is production-like only in the sense that it
starts the full local stack on a laptop. It is not a deployment topology, and
there is no `docker-compose.prod.yml`.

## Services

The demo stack is ready only when all 9/9 services are running and healthy:

| Service | URL / port |
|---|---|
| PostgreSQL | `localhost:5432` |
| MinIO API | `http://localhost:9000` |
| MinIO Console | `http://localhost:9001` |
| RabbitMQ AMQP | `localhost:5672` |
| RabbitMQ Management | `http://localhost:15672` |
| Qdrant REST | `http://localhost:6333` |
| Neo4j Browser | `http://localhost:7474` |
| Langfuse | `http://localhost:3000` |
| Java backend | `http://localhost:8080` |
| Python AI | `http://localhost:8000` |
| Frontend | `http://localhost:80` |

## Prerequisites

- Docker Desktop with WSL memory set to `12GB`.
- Local `python-ai` memory contour: `PYTHON_AI_MEMORY_LIMIT=10g` and `PYTHON_AI_MEMORY_RESERVATION=8g`.
- An ignored `infra/.env` copied from `infra/.env.example` or `../.env.example`.
- `ADMIN_USERNAME`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD` in `infra/.env` for Java admin bootstrap and seed reset.
- `OPENROUTER_API_KEY` in `infra/.env` for live DeepSeek/OpenRouter entity extraction.

The 10g Python AI limit and 8g reservation are intentional. The previous 8g
limit contour was too tight for the live demo path with bge-m3, reranker,
graph extraction, and prewarm.
Do not reduce it in the runbook or examples to make a check pass.

## Start

From the repository root:

```powershell
if (!(Test-Path infra/.env)) { Copy-Item infra/.env.example infra/.env }
docker compose --env-file infra/.env -f infra/docker-compose.yml up -d --build
docker compose --env-file infra/.env -f infra/docker-compose.yml ps
```

Or through Makefile wrappers:

```powershell
make compose-up COMPOSE_ENV=infra/.env
make compose-ps COMPOSE_ENV=infra/.env
```

Important: do not run `docker compose down -v` for normal demo reset, troubleshooting, or
seed refresh. Volume wiping bypasses the product lifecycle and destroys review
evidence. Keep the Hugging Face cache volume (`bge-m3-cache`) so `BAAI/bge-m3`
and `BAAI/bge-reranker-v2-m3` survive container recreation.

## Health And Diagnostics

Capture deterministic readiness evidence without mutating Docker state:

```powershell
python scripts/check_demo_stack.py --compose-file infra/docker-compose.yml --env-file infra/.env --output .planning/phases/08-delivery-polish-demo-readiness/08-COMPOSE-EVIDENCE.md
```

Expected result:

- `services_healthy=9/9`
- `/diagnostics` is reachable at `http://localhost:8000/diagnostics`
- evidence contains no secret values

Useful direct checks:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
Invoke-RestMethod http://localhost:8000/diagnostics
Invoke-RestMethod http://localhost:8080/actuator/health
Invoke-RestMethod http://localhost:6333/collections/documents_chunks
docker compose --env-file infra/.env -f infra/docker-compose.yml exec neo4j cypher-shell -u neo4j -p local-neo4j-password "RETURN 1;"
```

## Seed Corpus

The demo corpus reset uses the normal Java document lifecycle. It logs in to
Java, deletes only previous seed documents through Java DELETE, uploads the 16
manifest documents, waits for indexing, and writes Java/Qdrant/Neo4j evidence.

```powershell
.\scripts\seed-demo-corpus.ps1
```

Successful Phase 8 seed evidence should show:

- Java documents: `16/16`
- Qdrant document ids: `16/16`
- Neo4j document nodes: `16/16`
- non-seed Java documents: `0`

Evidence files:

- `.planning/phases/08-delivery-polish-demo-readiness/08-SEED-EVIDENCE.md`
- `.planning/phases/08-delivery-polish-demo-readiness/08-SEED-EVIDENCE.json`

## Troubleshooting

- If `python-ai` is not healthy, inspect startup/prewarm:
  `docker logs corp-rag-python-ai-1 --tail 120`.
- If model loading is slow, keep the `bge-m3-cache` volume and rerun compose;
  do not clear model/cache volumes for normal demo setup.
- If memory pressure appears, keep WSL at `12GB` and `PYTHON_AI_MEMORY_LIMIT=10g`;
  reducing the limit can reproduce the earlier 8g failure mode.
- If seed evidence shows Java/Qdrant success but Neo4j missing documents,
  inspect `python-ai` logs for entity extraction warnings before rerunning seed.
- If a service is missing or unhealthy, rerun `python scripts/check_demo_stack.py`
  and use its concrete service names as the blocker list.

## Query Observability

Phase 7 uses the Python `langfuse~=2.0` SDK with the existing
`langfuse/langfuse:2.95.11` container. Put real local Langfuse project keys in
ignored `infra/.env` to enable traces; placeholders intentionally no-op.
`/diagnostics` reports readiness booleans, query counters, prewarm readiness,
and `langfuse_configured` / `langfuse_reachable`.

Optional live query smoke:

```powershell
cd ai-service
$env:AI_QUERY_LIVE_SMOKE_ENABLED = "true"
$env:AI_QUERY_LIVE_CORPUS_READY = "true"
$env:AI_QUERY_LIVE_BASE_URL = "http://localhost:8000"
$env:OPENROUTER_API_KEY = "<openrouter-key>"
uv run pytest tests/test_query_live_smokes.py -m integration -q -s
```
