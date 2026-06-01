# Phase 8: Delivery Polish & Demo Readiness - Research

**Researched:** 2026-06-01
**Domain:** local delivery packaging, demo corpus reset, final regression evidence, demo documentation
**Confidence:** HIGH

## Summary

Phase 8 should not add a second deployment topology. The existing `infra/docker-compose.yml` already defines the full local MVP stack and the currently running stack reports all nine services healthy. The plan should harden the local runbook, evidence capture, and demo reset path around that compose file instead of creating `prod-compose` or clearing volumes. [VERIFIED: local code, Docker compose]

The central implementation risk is the seed/reset path. The corpus must be reset through the Java document API so normal Java delete/upload, outbox, RabbitMQ, Python cleanup, Qdrant, and Neo4j paths are exercised. The seed tooling should preserve manifest titles, write a stable seed marker in `description`, delete previous seed documents through Java, upload the 16 manifest documents, wait for indexing, and record a fresh document-id map for final eval evidence. [VERIFIED: local code]

**Primary recommendation:** split Phase 8 into five plans: seed reset, compose/runbook readiness, final regression evidence, demo assets, and narrow polish/traceability.

## User Constraints

Authoritative constraints are captured in `.planning/phases/08-delivery-polish-demo-readiness/08-CONTEXT.md`. The planner must honor the locked decisions there, especially:

- Use the single existing `infra/docker-compose.yml`; do not create a prod compose file.
- Seed reset must use normal Java document APIs and must not wipe Docker volumes.
- Preserve guard, citation, access-filter, weak-evidence, and refusal behavior.
- Explicitly waive current Russian multi-hop graph retrieval debt for Phase 8 rather than hiding it.
- Final regression must prove compose health, seed/indexing, chat/citation, and one production-path RAGAS/eval run.
- Demo assets must include README updates, a real architecture diagram, and a short-video-ready script/checklist.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Local stack startup and health evidence | Infrastructure / Docker Compose | Docs | Compose already owns the nine-service local runtime and healthchecks. |
| Seed corpus reset | Java API / Backend | Python eval tooling | Product document lifecycle must go through Java; Python tooling can automate calls and verify AI-owned stores. |
| Index cleanup verification | Python AI stores | Java metadata | Qdrant and Neo4j cleanliness must be checked after Java delete events flow through Python. |
| Final chat regression | Java API / Frontend-facing backend | Python AI service | Browser and scripts must call Java; Java calls Python internally. |
| RAGAS final eval | Python eval tooling | Local Docker stack | Existing RAGAS runner owns production `/v1/query` eval evidence. |
| Demo documentation and diagram | Docs | Frontend/browser evidence | The deliverable is review-ready assets, not a new product feature. |
| Raw UTF-8 document polish | Java storage/raw URL | Frontend admin UI | The source issue is MinIO text content type for raw browser rendering. |
| Requirements traceability cleanup | Planning docs | Phase evidence | Implemented retrieval/router requirements need metadata correction without hot-path changes. |

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEL-01 | Production-like Docker Compose, seed corpus script, final regression, README/demo assets, and short video demo are ready. | Covered by the five-plan split: compose readiness, seed reset, final regression, docs/assets, and polish/known-limitation closure. |

## Local Findings

- `infra/docker-compose.yml` defines PostgreSQL, MinIO, RabbitMQ, Qdrant, Neo4j, Langfuse, Java backend, Python AI service, and frontend with healthchecks and named volumes. [VERIFIED: local code]
- `docker compose --env-file infra/.env -f infra/docker-compose.yml ps` currently reports all nine services up and healthy. [VERIFIED: local command]
- Docker Desktop is available with server version 28.5.2, Compose v2.40.3, and about 11.68 GiB total memory. The local ignored `infra/.env` already uses a higher Python AI memory contour than the committed default, so docs should explain memory without blindly changing committed compose defaults. [VERIFIED: local command]
- `DocumentController` exposes cookie-authenticated list, upload, delete, and raw-url endpoints under `/api/v1/documents`. Upload metadata fields match the corpus manifest: title, accessLevel, department, docType, language, and description. [VERIFIED: local code]
- `DocumentDeletionService` publishes `document.deleted` through the normal Java outbox path. This is the correct cleanup trigger for Qdrant and Neo4j. [VERIFIED: local code]
- `DocumentUploadService` rejects active duplicates by content hash within the same department. The seed reset must delete previous seed documents before reuploading to avoid duplicate conflicts. [VERIFIED: local code]
- `DocumentRawUrlService` delegates to MinIO presigned URLs and Java never proxies bytes. BL-UAT-01 should therefore be fixed by storing or requesting UTF-8 text content type, not by adding a Java byte proxy. [VERIFIED: local code]
- `ai-service/eval/graph_corpus_state.py` already compares expected document ids with Neo4j and Java state. Seed verification should reuse its comparison logic rather than duplicating the mismatch rules. [VERIFIED: local code]
- `ai-service/eval/ragas_runner.py` already supports production `/v1/query`, `top_k`, score-only, local bge-m3 embeddings, `concurrency=1`, and limited RAGAS retries/wait. Final regression should wrap this runner rather than add a second eval path. [VERIFIED: local code]
- `/diagnostics` currently reports query readiness, Langfuse reachability, query counters, and `reranker_degraded_count=0`. It is a useful before/after evidence source for final regression. [VERIFIED: local command]

## Standard Stack

| Tool / Library | Version / Surface | Purpose | Why Standard Here |
|----------------|-------------------|---------|-------------------|
| Docker Compose | Compose v2.40.3 local | Start and inspect local MVP stack | Existing project runtime and healthcheck source. |
| Java document API | `/api/v1/documents` | Seed reset upload/delete/list/status | Enforces auth, audit, outbox, and lifecycle contracts. |
| Python `httpx` | ai-service dependency | Scripted Java/Python HTTP calls | Already used by eval query tooling. |
| Python `neo4j` and `qdrant-client` | ai-service dependencies | Store cleanliness verification | Existing AI-service store clients. |
| Existing RAGAS runner | `ai-service/eval/ragas_runner.py` | Final production-path eval | Already carries Phase 7/7.1 retry and report semantics. |
| Existing graph state helper | `ai-service/eval/graph_corpus_state.py` | Corpus state comparison | Avoids duplicated mismatch and count logic. |

## Architecture Patterns

### Pattern 1: Product Operations Go Through Java

Seed reset must authenticate as an admin user, list documents through Java, delete matching seed documents through Java, and upload manifest documents through Java multipart upload. Python store cleanup is then observed as a downstream effect.

### Pattern 2: Eval Tooling Can Read Internal Stores

It is acceptable for eval/demo tooling to inspect Qdrant, Neo4j, and AI Postgres for evidence. It is not acceptable for the seed mechanism itself to mutate those stores directly.

### Pattern 3: Evidence Before Narrative

Final README/demo claims should be written after the final regression produces evidence: compose health, seed summary, chat/citation transcript, diagnostics, eval summary, and known limitations.

### Anti-Patterns to Avoid

- Creating `docker-compose.prod.yml` for Phase 8.
- Running `docker compose down -v` as a normal reset step.
- Updating golden question text, reference answers, or corpus documents to make final metrics look better.
- Weakening guards, access filters, citations, or refusal thresholds.
- Hiding the multi-hop graph limitation in demo docs.
- Committing stochastic generated eval reports before review.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Document lifecycle reset | Direct Qdrant/Neo4j/volume cleanup | Java document delete/upload APIs | Exercises the product lifecycle and event cleanup. |
| RAGAS evaluation | New ad hoc metric runner | `ai-service/eval/ragas_runner.py` | Preserves Phase 7/7.1 semantics and retry controls. |
| Graph corpus comparison | New count logic | `graph_corpus_state.py` | Existing helper already understands missing/extra/zero entity cases. |
| Demo stack health | Freeform manual notes | Compose healthchecks plus scripted summary | Health evidence should be reproducible. |

## Common Pitfalls

### Pitfall 1: Duplicate Seed Uploads

**What goes wrong:** Java rejects uploads with `DUPLICATE_DOCUMENT` because previous seed documents remain active.
**How to avoid:** marker-based list/delete through Java before uploading, then poll deletion cleanup.

### Pitfall 2: Eval Metadata Uses Stale Document IDs

**What goes wrong:** reuploaded corpus receives new Java document ids, but RAGAS expected document ids still point to old local ids.
**How to avoid:** write a fresh seed metadata/evidence file after upload and pass it explicitly to final eval.

### Pitfall 3: Healthy Containers Do Not Prove Demo Readiness

**What goes wrong:** compose is healthy but corpus is stale, Qdrant/Neo4j are dirty, or chat citations are broken.
**How to avoid:** final gate must chain compose health -> seed reset -> chat/citation -> RAGAS/eval.

### Pitfall 4: Demo Polish Accidentally Changes Product Semantics

**What goes wrong:** metrics improve by relaxing guard/refusal/access behavior.
**How to avoid:** keep polish limited to docs, seed metadata, UTF-8 raw rendering, and traceability unless a separate fix loop is explicitly opened.

## Environment Availability

| Dependency | Required By | Available | Version / Evidence | Fallback |
|------------|-------------|-----------|--------------------|----------|
| Docker Desktop | Compose readiness, live regression | yes | Docker 28.5.2, Compose v2.40.3 | None for live demo. |
| Local compose stack | Research verification | yes | 9/9 services healthy from `docker compose ps` | Start with documented compose command. |
| OpenRouter key | Final RAGAS judge and synthesis | yes locally | Present in ignored env file; value not documented | Score-only or record blocker. |
| Langfuse keys | Demo traces | yes locally | `/diagnostics` reports configured/reachable | Document trace unavailable if not configured. |
| Admin credentials | Seed reset | yes locally | Present in ignored env file; value not documented | User supplies env vars. |

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Maven/JUnit for Java, pytest for ai-service eval tooling, node syntax checks for frontend JS, Docker Compose live evidence |
| Config file | `backend/pom.xml`, `ai-service/pyproject.toml`, `infra/docker-compose.yml` |
| Quick run command | `uv run --project ai-service --group dev pytest ai-service/tests/test_eval_seed_corpus.py ai-service/tests/test_eval_final_regression.py` |
| Full suite command | focused Java tests, ai-service eval tests, compose health, seed reset, chat/citation proof, and one RAGAS/eval run |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| DEL-01 | Seed reset talks to Java, uploads 16 docs, and records clean corpus state | unit + live | `uv run --project ai-service --group dev pytest ai-service/tests/test_eval_seed_corpus.py` plus live seed command | planned |
| DEL-01 | Compose stack is 9/9 healthy and documented | live smoke | `docker compose --env-file infra/.env -f infra/docker-compose.yml ps` | existing |
| DEL-01 | Final chat/citation/eval path works | unit + live | `uv run --project ai-service --group dev pytest ai-service/tests/test_eval_final_regression.py` plus live runner | planned |
| DEL-01 | README, diagram, demo script, and video checklist exist | docs/static | markdown/link checks in Plan 04 | planned |
| DEL-01 | Multi-hop debt is explicitly waived and documented | docs/static | grep for known limitation and D-418/D-420 refs | planned |

### Sampling Rate

- **Per task commit:** run the focused command listed in the task.
- **Per wave merge:** run all focused tests for files touched in that wave.
- **Phase gate:** run compose health, seed reset, chat/citation regression, and final eval evidence before verify-work.

### Wave 0 Gaps

- `ai-service/tests/test_eval_seed_corpus.py` - planned in 08-01.
- `ai-service/tests/test_eval_final_regression.py` - planned in 08-03.
- `scripts/check_demo_stack.py` - planned in 08-02.

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | yes | Java cookie-auth login, admin credentials via ignored env vars. |
| V3 Session Management | yes | Existing httpOnly SameSite cookies; seed tooling uses a session jar. |
| V4 Access Control | yes | Java document API and resolved access filters remain authoritative. |
| V5 Input Validation | yes | Existing Java boundary validation and Python script manifest validation. |
| V6 Cryptography | no new crypto | Do not introduce custom token or crypto logic. |

Known threat patterns:

| Pattern | Mitigation |
|---------|------------|
| Seed script bypasses access controls | Authenticate and use Java APIs only. |
| Secret leakage in docs/evidence | Read secret values from env and never write them into reports. |
| Eval report manipulation | Do not mutate corpus/golden answers and require user review before committing stochastic reports. |
| Access-filter regression | Keep retrieval access filters untouched and verify returned citations remain document-backed. |

## Open Questions (RESOLVED)

1. **Should Phase 8 implement multi-hop graph redesign?** RESOLVED: no. The context locks an explicit waiver and known limitation for this phase.
2. **Should seed reset wipe volumes?** RESOLVED: no. It must use Java delete/upload APIs.
3. **Should compose defaults change to 10 GiB Python memory?** RESOLVED: only if live verification proves 8 GiB insufficient; otherwise document memory guidance and local override.

## Sources

### Primary (HIGH confidence)

- `.planning/phases/08-delivery-polish-demo-readiness/08-CONTEXT.md` - locked Phase 8 scope and decisions.
- `infra/docker-compose.yml` - nine-service local runtime and healthchecks.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/DocumentController.java` - Java document API.
- `backend/corp-rag-app/src/main/java/com/corprag/service/document/DocumentUploadService.java` - upload duplicate and outbox behavior.
- `backend/corp-rag-app/src/main/java/com/corprag/service/document/DocumentDeletionService.java` - delete/outbox behavior.
- `ai-service/eval/corpus/manifest.json`, `ai-service/eval/ragas_runner.py`, `ai-service/eval/graph_corpus_state.py` - corpus/eval evidence surfaces.
- Local Docker and `/diagnostics` command outputs from 2026-06-01.

### Secondary (MEDIUM confidence)

- `.planning/STATE.md`, `.planning/BACKLOG.md`, Phase 7/7.1 summaries - handoff and residual risks.
- `README.md`, `infra/README.md`, `docs/ARCHITECTURE.md`, ADR-003/006/007/008 - documentation and architecture constraints.

### Tertiary (LOW confidence)

- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all tools already exist in repo or local runtime.
- Architecture: HIGH - phase mostly packages existing boundaries.
- Pitfalls: HIGH - derived from Java duplicate/delete behavior and Phase 7/7.1 evidence.

**Research date:** 2026-06-01
**Valid until:** 2026-07-01 for local project facts; recheck Docker/env state before live execution.
