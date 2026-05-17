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
