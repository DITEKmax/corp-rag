---
phase: "04-python-ingestion-indexing"
plan: "01"
subsystem: docker-codegen
tags: [docker, codegen, contracts, compose, python-ai]
requires:
  - phase: "03-documents-events-audit"
    provides: "document lifecycle contracts, RabbitMQ topology, and accumulated UAT messages"
provides:
  - "python-ai repo-root Docker build with isolated contract codegen"
  - "root .dockerignore pruning for Python image builds"
  - "compose resource contour for local bge-m3 cache and memory budget"
affects: ["python-ai", "infra", "contracts"]
tech-stack:
  added: []
  patterns: ["repo-root Docker context with build-only codegen tooling"]
key-files:
  created:
    - ".dockerignore"
    - ".planning/phases/04-python-ingestion-indexing/04-01-SUMMARY.md"
  modified:
    - "ai-service/Dockerfile"
    - "ai-service/README.md"
    - "ai-service/pyproject.toml"
    - "ai-service/uv.lock"
    - "infra/docker-compose.yml"
key-decisions:
  - "Runtime uses plain uvicorn instead of uvicorn[standard] because the standard extra pulls PyYAML into the production image."
patterns-established:
  - "Docker builder deletes generated contracts before running root generator scripts, so stale host files cannot enter the runtime image."
  - "Generated Python contract outputs remain ignored locally and are produced identically by Docker codegen."
requirements-completed: []
duration: "about 1 hour"
completed: "2026-05-17"
---

# Phase 04 Plan 01: Repo-Root Python Docker Codegen Summary

**python-ai now clean-builds from repo root and regenerates Python contracts inside Docker.**

## Accomplishments

- Reworked `ai-service/Dockerfile` into a builder/runtime multi-stage image using the same uv base for both stages.
- Changed `python-ai` compose build to `context: ..` and `dockerfile: ai-service/Dockerfile`, symmetric with the Java backend root-context build.
- Added root `.dockerignore` pruning for `.git`, `.planning`, caches, frontend node modules, backend target output, and local generated Python contracts.
- Added compose `bge-m3-cache` volume and 4GB/3GB memory contour for the future local FlagEmbedding runtime.
- Updated `ai-service/README.md` to document local-vs-Docker contract codegen behavior.
- Changed runtime dependency from `uvicorn[standard]` to plain `uvicorn` because the standard extra installs PyYAML in production.

## Task Commits

1. **Wave 1 implementation** - `64073f1` (`build(04): make python-ai docker codegen deterministic`)

**Plan metadata:** this summary commit

## Verification

- `docker compose -f infra/docker-compose.yml config` - passed; rendered root build context, `bge-m3-cache`, and memory settings.
- Removed local `ai-service/src/corp_rag_ai/contracts/generated`, then ran `docker compose -f infra/docker-compose.yml build python-ai` - passed.
- Created local ignored `generated/zombie.py`, rebuilt `python-ai`, and inspected `/app/src/corp_rag_ai/contracts/generated` - generated modules were present and `zombie.py` was absent.
- `docker exec corp-rag-python-ai-1 python -c "import importlib.util; ... find_spec('yaml') is None ..."` - passed; runtime image has no PyYAML import.
- `docker exec corp-rag-python-ai-1 python -c "... /health ..."` - returned `{"status":"healthy"}`.
- `docker exec corp-rag-python-ai-1 python -c "... /ready ..."` - returned `{"status":"ready"}`.
- `uv run pytest` - not a useful gate yet; pytest collected 0 tests and exited with code 1.

## Deviations From Plan

- `ai-service/src/corp_rag_ai/config.py` was left unchanged because no Wave 1 code reads model/cache settings yet; compose owns the cache mount and memory budget.
- `uvicorn[standard]` was replaced with `uvicorn` to satisfy the locked runtime-without-PyYAML guarantee.

## Issues Encountered

- The first Docker build correctly regenerated contracts, but showed PyYAML in the runtime environment via `uvicorn[standard]`. Tightening the dependency to plain `uvicorn` fixed it.
- Sandboxed Docker access could not read local Docker buildx state; the build was rerun with approved Docker permissions.

## Next Plan Readiness

Ready for `04-02-PLAN.md`: Python container builds deterministically from clean root context, generated contract modules are available in the image, and compose has the local model cache contour for later embedding work.

## Self-Check: PASSED

- Clean Docker build passed without host-generated Python contracts.
- Stale generated host file did not enter the final image.
- Runtime image lacks PyYAML.
- `/health` and `/ready` return 200.
- Generator scripts were not modified.

---
*Phase: 04-python-ingestion-indexing*
*Completed: 2026-05-17*
