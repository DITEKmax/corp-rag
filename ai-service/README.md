# corp-rag-ai

Python FastAPI AI service for the Corporate RAG ingestion, indexing, and retrieval pipeline.

## Contract Codegen

Source contract YAML files live in the repository root under `contracts/`. Generated Python modules are written to `ai-service/src/corp_rag_ai/contracts/generated/` and remain ignored by git.

Local development:

- Run the root contract verification or generation command from the repository root.
- Generated modules are written to the same `src/corp_rag_ai/contracts/generated/` path that Docker uses.
- Do not commit generated contract outputs.

Docker build:

- `infra/docker-compose.yml` builds `python-ai` from the repository root with `dockerfile: ai-service/Dockerfile`.
- The Docker builder stage copies root `contracts/`, root `scripts/`, and `ai-service/` into `/repo`.
- Before codegen, the builder removes any existing generated contract directory to avoid stale files.
- The builder runs `generate_python_contracts.py` and `generate_constants.py`; the runtime stage copies only the generated `src` tree and service files.
- PyYAML is installed only in the builder stage. The runtime image must not include PyYAML as a production dependency.

## Local Commands

```bash
cd ai-service
uv sync
uv run uvicorn corp_rag_ai.main:app --reload
uv run pytest
```

## Local Model Cache And Memory

Phase 4 uses local `FlagEmbedding` for `BAAI/bge-m3` dense+sparse embeddings. The first live smoke or first container run can download about 2.3 GB of model weights into the Hugging Face cache.

Docker Compose mounts the named `bge-m3-cache` volume at `/root/.cache/huggingface` for `python-ai`. Keep that volume between runs so the model is not downloaded repeatedly. The compose service reserves 6 GB and caps `python-ai` at 8 GB for Phase 7 evaluation because the query path can load both local bge-m3 and the local bge reranker; Docker Desktop should have additional headroom for Java, Postgres, Qdrant, Neo4j, MinIO, RabbitMQ, and Langfuse.

Do not clear retained Docker volumes before the end-of-Phase 4 UAT. The retained RabbitMQ messages from Phase 3 are part of the first UAT scenario.

## Test Selection

Default tests are CI-safe and do not require a model download, Qdrant, Neo4j, or OpenRouter:

```bash
cd ai-service
uv run pytest tests
```

Live integration tests are marked `integration` and self-skip unless their explicit prerequisites are present:

| Test | Required prerequisite |
|---|---|
| Local bge-m3 smoke | `AI_EMBEDDING_LIVE_SMOKE_ENABLED=true` |
| Qdrant live smoke | `AI_QDRANT_LIVE_SMOKE_ENABLED=true` and reachable `QDRANT_URL` |
| Neo4j live smoke | `AI_NEO4J_LIVE_SMOKE_ENABLED=true` and reachable `NEO4J_URI` |
| DeepSeek/OpenRouter live extraction | `OPENROUTER_API_KEY` |
| Query API live smokes | `AI_QUERY_LIVE_SMOKE_ENABLED=true`, `AI_QUERY_LIVE_CORPUS_READY=true`, `AI_QUERY_LIVE_BASE_URL`, and `OPENROUTER_API_KEY` |

PowerShell live smoke example:

```powershell
cd ai-service
$env:AI_EMBEDDING_LIVE_SMOKE_ENABLED = "true"
$env:AI_QDRANT_LIVE_SMOKE_ENABLED = "true"
$env:AI_NEO4J_LIVE_SMOKE_ENABLED = "true"
$env:OPENROUTER_API_KEY = "your-openrouter-key"
uv run pytest -m integration
```

## Live DeepSeek/OpenRouter Entity Extraction Smoke

Entity extraction unit tests mock OpenAI-compatible chat completions and do not need credentials. The live integration smoke is skipped unless `OPENROUTER_API_KEY` is set.

The service uses `deepseek/deepseek-v4-flash:free` through OpenRouter by default.
Set `DEEPSEEK_MODEL_ID` only when overriding to a paid tier:

| Setting | Default |
|---|---|
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` |
| `DEEPSEEK_MODEL_ID` | `deepseek/deepseek-v4-flash:free` |

## Query Runtime Defaults

Phase 5 query behavior is configured through environment-backed settings:

| Setting | Default |
|---|---|
| `AI_QUERY_TIMEOUT_SECONDS` | `30` |
| `AI_ROUTER_CONFIDENCE_THRESHOLD` | `0.65` |
| `AI_RERANKER_ENABLED` | `true` |
| `AI_RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` |
| `AI_RERANKER_TIMEOUT_SECONDS` | `25` |
| `AI_RERANKER_LOAD_TIMEOUT_SECONDS` | `28` |
| `AI_QUERY_PREWARM_ENABLED` | `false` in plain settings, `true` in Compose |
| `AI_QUERY_PREWARM_TIMEOUT_SECONDS` | `45` |
| `AI_CONTEXT_TOKEN_CAP` | `4000` |
| `AI_WEAK_EVIDENCE_THRESHOLD` | `0.4` |
| `AI_FLAGGED_CHUNK_SCORE_MULTIPLIER` | `0.5` |

`POST /v1/query` accepts Java-resolved `accessFilter` values and returns `QueryResponse` with `answered`, `answer`, child-UUID `citations`, `confidence`, optional `guardVerdict`, and `retrievalMeta`. Safe refusals and timeouts are returned as `answered=false`; invalid boundary/configuration failures return Problem Details.

`AI_QUERY_TIMEOUT_SECONDS` is the outer REST request budget. The reranker has smaller internal budgets: `AI_RERANKER_TIMEOUT_SECONDS` bounds warm `compute_score(...)` work, and `AI_RERANKER_LOAD_TIMEOUT_SECONDS` bounds lazy local model load. Both must be strictly below `AI_QUERY_TIMEOUT_SECONDS`; startup settings validation fails if the effective reranker step budget is greater than or equal to the query timeout. When a reranker budget expires, the query keeps the raw retrieval order, returns `rerankerUsed=false`, and includes `reranker_unavailable` in `retrievalMeta.degradationWarnings`.

The default warm scoring budget is 25 seconds because local CPU scoring for `BAAI/bge-reranker-v2-m3` can be slow but must still leave room inside the 30 second request timeout. The lazy load budget is 28 seconds to give cold load slightly more headroom without letting reranking occupy the whole request. Compose enables `AI_QUERY_PREWARM_ENABLED=true` so startup tries to load local bge-m3 and reranker components before the first timed query. Prewarm never calls OpenRouter, RAGAS, or Langfuse, and failures are reported in diagnostics without blocking startup.

`/diagnostics` includes query readiness fields: `query_service`, `query_router`, `reranker_configured`, and `llm_reachable`. The LLM field is a cheap configured-state indicator and does not make a live OpenRouter call. Phase 7 also exposes process-local query counters (`query_count`, `answered_count`, `answered_rate`, `refused_no_evidence_count`, `guard_blocked_count`, `reranker_degraded_count`, `mean_latency_ms`), prewarm readiness, and Langfuse configured/reachable booleans.

## Langfuse Tracing

The service uses the legacy `langfuse~=2.0` Python SDK because local Compose runs `langfuse/langfuse:2.95.11`. Do not upgrade the container to Langfuse v3 for Phase 7.

Tracing no-ops when `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` are placeholders or the local Langfuse health endpoint is unreachable. When real local Langfuse keys are configured, each `/v1/query` creates one root trace with safe request/result metadata. Query graph nodes create child spans named after the actual node names, and the OpenRouter synthesis call is traced as a generation under `synthesize` with the prompt/output payload required for eval inspection. Secrets are never written to traces.

Java chat persistence, Java audit rows for query outcomes, and browser chat/source-viewer UI are Phase 6 responsibilities. Python now returns enough answer, citation, guard, and retrieval metadata for Java to persist and display.

Optional query live smokes:

```powershell
cd ai-service
$env:AI_QUERY_LIVE_SMOKE_ENABLED = "true"
$env:AI_QUERY_LIVE_CORPUS_READY = "true"
$env:AI_QUERY_LIVE_BASE_URL = "http://localhost:8000"
$env:AI_QUERY_LIVE_DEPARTMENTS = "HR"
$env:AI_QUERY_LIVE_DOC_TYPES = "POLICY"
$env:OPENROUTER_API_KEY = "your-openrouter-key"
uv run pytest tests/test_query_live_smokes.py -m integration -q -s
```

PowerShell:

```powershell
cd ai-service
$env:OPENROUTER_API_KEY = "your-openrouter-key"
uv run pytest tests/test_deepseek_extraction_live.py -m integration
```

Bash:

```bash
cd ai-service
OPENROUTER_API_KEY=your-openrouter-key uv run pytest tests/test_deepseek_extraction_live.py -m integration
```
