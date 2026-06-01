# Phase 8: Delivery Polish & Demo Readiness - Context

**Gathered:** 2026-06-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 8 packages the already-working MVP for a reproducible local demo from a laptop. It makes the single existing Docker Compose stack demonstrably start all nine services, provides an idempotent seed/reset path for the frozen 16-document Russian corpus through the real Java document API, captures one final core regression path, and prepares demo-facing assets: README updates, architecture diagram, and short video.

This phase does not add deployment, does not create a production compose file, does not redesign graph retrieval, and does not reopen Phase 7 quality work. It is delivery polish and demo readiness around the existing local MVP.

Success criterion 1 is locked as: the single `infra/docker-compose.yml` reproducibly brings up the full stack 9/9 healthy from a normal clean start. No new prod-compose file is in scope. Data reset for demo corpus must happen through Java delete/upload APIs, not by wiping Docker volumes or running `docker compose down -v`.

</domain>

<decisions>
## Implementation Decisions

### Locked Scope From Phase 7 Handoff
- **D-418:** Multi-hop graph retrieval for `ru-multihop-002`, `ru-multihop-003`, `ru-multihop-005`, and `ru-multihop-006` is waived for Phase 8. It must be documented as a known limitation: the router now reaches `MULTI_HOP`, but the graph retriever safely refuses with `refused_no_evidence` when evidence is insufficient.
- **D-419:** Phase 8 must not implement text-conditioned multi-document graph retrieval, semantic path ranking, entity-linking redesign, or broad Cypher/path-ranking changes. Those belong to future work if the project continues after demo.
- **D-420:** The waiver is acceptable because the system fails safely: it refuses rather than fabricating unsupported multi-hop answers.
- **D-421:** Do not weaken access filters, output guard, citation validation, weak-evidence thresholds, or refusal behavior to make final metrics look better.
- **D-422:** Do not mutate the frozen corpus files, golden questions, reference answers, or expected document UUID assumptions except where a new seed run necessarily creates a fresh local Java document id map and records it as evidence.

### Local Compose Readiness
- **D-423:** Do not create `prod-compose`, `docker-compose.prod.yml`, or another deployment file. The deliverable is the existing `infra/docker-compose.yml`.
- **D-424:** The compose success criterion is 9/9 healthy for PostgreSQL, MinIO, RabbitMQ, Qdrant, Neo4j, Langfuse, Java backend, Python AI service, and frontend.
- **D-425:** The demo run is local laptop delivery, not deployment. README copy may call it production-like only in the sense of a full local stack with real services, healthchecks, and persisted volumes.
- **D-426:** `python-ai` memory guidance must be explicit: Docker Desktop/WSL should have about 12 GiB available and `python-ai` should use the demo contour that leaves room for bge-m3 plus reranker. Planning should consider raising `PYTHON_AI_MEMORY_LIMIT` to `10g` only if current 8 GiB is insufficient in live verification; do not blindly overfit the compose file.
- **D-427:** Keep the Hugging Face cache volume. Do not instruct users to clear model/cache volumes as part of normal demo preparation.

### Seed Corpus Reset
- **D-428:** The seed script must be idempotent reset, not append-only and not verify-only.
- **D-429:** Reset means the local demo corpus is brought to exactly the 16 documents from `ai-service/eval/corpus/documents/` and `ai-service/eval/corpus/manifest.json`.
- **D-430:** The reset must use the normal Java browser-facing document APIs under an admin user: authenticate as admin, list existing matching seed documents, delete them through Java, upload all 16 files through Java multipart upload, then wait for indexing completion.
- **D-431:** Do not manually clean Qdrant, Neo4j, MinIO, Java Postgres, AI Postgres, RabbitMQ, or Docker volumes as the seed mechanism. In particular, do not use `docker compose down -v` for repeatable demo reset.
- **D-432:** Deleting through Java is required so the ordinary document delete event path can clean Qdrant and Neo4j.
- **D-433:** Because backlog F-08 observed orphan Qdrant points and Neo4j `Document` nodes after delete/reupload, seed verification must check backend document count/status plus Qdrant and Neo4j corpus cleanliness. It is not enough to see 16 rows in the Java document list.
- **D-434:** The seed script must use stable corpus identity from existing metadata fields. Since Java upload has no dedicated corpus `doc_id` field, planning should choose a stable marker using current fields such as title, original filename, description, access level, department, doc type, and language. Prefer writing a seed marker in `description` for future resets if it fits the existing API.
- **D-435:** The seed must preserve user-facing titles from the manifest so citation `documentTitle` values are polished. This should partially close BL-UAT-04 without adding a new title-extraction subsystem.
- **D-436:** The script must wait for all 16 documents to reach terminal successful indexing and must surface failed documents, failure reasons, chunk counts, and indexed timestamps in its output.
- **D-437:** Seed documentation must explain required admin credentials and environment values without committing secrets. Use ignored `infra/.env` or explicit local environment variables.

### Final Regression
- **D-438:** The mandatory final regression gate is "Core path + eval": 9/9 compose healthy, seed/index reset, one live chat-to-citation path through frontend or Java chat API, and one production-path RAGAS/eval run.
- **D-439:** Smoke-only is insufficient because Phase 8 must prove the chat/citation/evaluation path still works.
- **D-440:** Full replay of RAGAS + ablation + injection + Langfuse is out of scope for the required gate. Phase 7 artifacts already contain ablation, injection, diagnostics, and Langfuse evidence.
- **D-441:** The single final RAGAS/eval run remains report-only evidence, not a hard CI gate. Judge instability must be documented rather than hidden.
- **D-442:** The final eval run uses the known Phase 7/7.1 constraints: production `/v1/query`, topK 10 where applicable, `concurrency=1`, RAGAS judge retries set to `--ragas-max-retries 1 --ragas-max-wait 5`, and local bge-m3 embeddings unless planning discovers a concrete incompatibility.
- **D-443:** Track `reranker_degraded_count=0` as a key regression signal. If reranker degradation appears, record it and diagnose before treating the run as demo-ready.
- **D-444:** Final regression should capture enough evidence for review: compose health, seed summary, corpus/index counts, chat question/answer/citation screenshot or transcript, RAGAS/eval output summary, and any known limitations.
- **D-445:** Do not commit stochastic generated eval reports until the user has reviewed that the run is clean and comparable.

### Demo Story And Assets
- **D-446:** Demo assets are not optional. The phase delivers README updates, an architecture diagram, and a short video.
- **D-447:** The demo scenario should be concrete and Russian-corpus-first: factual questions with citations, a live Langfuse trace showing node/span breakdown, latency explanation including rerank around 16 seconds when observed, and an injection-block/refusal demonstration.
- **D-448:** The demo narrative should explicitly explain that multi-hop graph retrieval has a known limitation and safely refuses when evidence is weak. Do not present that as a hidden failure.
- **D-449:** The architecture diagram must show the real service boundary: frontend calls Java only; Java owns auth, documents, chat, audit, and API; Python owns ingestion, retrieval, graph, guards, synthesis, eval; Qdrant/Neo4j/Langfuse are supporting services.
- **D-450:** The README must include the exact local runbook: prerequisites, memory expectations, compose startup, admin credentials setup, seed reset, health checks, core demo path, eval command, troubleshooting, and known limitations.

### Opportunistic Polish Priority
- **D-451:** First opportunistic priority is low-risk UI/documentation polish: BL-UAT-01 charset mojibake, BL-UAT-04 document title polish if not fully solved by seed metadata, and REQUIREMENTS traceability.
- **D-452:** REQUIREMENTS traceability should be corrected because `RET-01`, `RET-02`, `RET-03`, `AGT-01`, and `AGT-02` are still shown as Pending even though implemented behavior exists. This is a documentation/metadata fix and should not require hot-path code changes.
- **D-453:** BL-UAT-01 is acceptable Phase 8 polish if it is a narrow UTF-8 content-type/browser raw-view fix. It must not restructure document storage.
- **D-454:** Data-exfiltration explicit guard classification is stretch work after C-priority polish, not a blocker. It may be implemented only as a narrow path-limited change with Docker verification.
- **D-455:** If data-exfiltration guard classification is attempted, it must not weaken current protections. All 12 injection probes must still resist attacks; if any probe regresses or behavior changes beyond the intended explicit `refused_guard`, back it out.
- **D-456:** `ru-factual-009` false-UNSUPPORTED/router work is lowest priority. It may be attempted only if the fix is obviously general Russian/localization routing behavior, not a golden-record-specific patch.
- **D-457:** Do not train a classifier, retune against the golden set, or add special-case strings solely to improve one eval row.

### the agent's Discretion
- Choose exact seed script language and location, but it should be easy to run on the user's Windows/PowerShell setup and documented from README. If a POSIX script is added too, keep both thin and behavior-equivalent.
- Choose exact polling intervals and timeout budgets for seed/index wait if failures are clear and the defaults work on the local Docker stack.
- Choose exact demo factual questions from the existing golden/corpus set, prioritizing reliable citation behavior and clear story value.
- Choose exact architecture diagram format if it is reviewable in-repo and renders cleanly in the README or linked docs.
- Choose exact evidence filenames under the Phase 8 directory and/or docs, provided generated reports remain reviewed before commit.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning State And Requirements
- `.planning/PROJECT.md` - project value, local MVP framing, Java/Python/frontend service boundaries, and budget/on-premise constraints.
- `.planning/REQUIREMENTS.md` - `DEL-01` and traceability status for `RET-01`, `RET-02`, `RET-03`, `AGT-01`, and `AGT-02`.
- `.planning/ROADMAP.md` - Phase 8 goal and success criteria; criterion 1 is superseded by this CONTEXT wording to use the single existing compose file.
- `.planning/STATE.md` - Phase 7/7.1 handoff, pending multi-hop waiver decision, data-exfiltration note, and current delivery focus.
- `.planning/BACKLOG.md` - BL-UAT-01, BL-UAT-04, F-08, reranker/memory notes, and non-blocking Phase 8 polish candidates.

### Prior Phase Context And Evidence
- `.planning/phases/07-evaluation-observability/07-CONTEXT.md` - RAGAS/report invariants, report-only stance, Langfuse trace expectations, and do-not-break gates.
- `.planning/phases/07-evaluation-observability/07-EVAL-SUMMARY.md` - final Phase 7 evidence narrative and links to reports/traces.
- `.planning/phases/07.1-fix-russian-router-and-graph-retrieval-quality-for-ragas-bas/07.1-CONTEXT.md` - router fixes, graph corpus repair, remaining multi-hop debt, and no graph redesign boundary.
- `.planning/phases/07.1-fix-russian-router-and-graph-retrieval-quality-for-ragas-bas/07.1-03-SUMMARY.md` - post-fix RAGAS comparison and remaining multi-hop refusals.
- `.planning/phases/06-chat-frontend-experience/06-CONTEXT.md` - Java chat persistence, source viewer, frontend admin documents UI, and no frontend-to-Python boundary.
- `.planning/phases/06-chat-frontend-experience/06-HUMAN-UAT.md` - human UAT evidence and residual UI/document polish.
- `.planning/phases/06-chat-frontend-experience/06-UAT-EVIDENCE.md` - Phase 6 browser/chat evidence and residual observations.

### Runtime And Documentation
- `README.md` - top-level local run instructions to update for final demo readiness.
- `infra/README.md` - local stack instructions, service URLs, memory notes, health checks, and Langfuse notes.
- `infra/docker-compose.yml` - the single compose file that must bring 9/9 services healthy.
- `infra/.env.example` - non-secret environment template for local demo configuration.
- `docs/CONTEXT.md` - diploma framing, 9-container local stack, evaluation narrative, and Langfuse demo story.
- `docs/ARCHITECTURE.md` - architecture diagram/source material and RAG/eval component descriptions.
- `docs/decisions/ADR-003-java-python-split.md` - Java as browser-facing authority and Python as internal AI service.
- `docs/decisions/ADR-006-degraded-mode-policy.md` - fail-loud degraded-mode and diagnostics expectations.
- `docs/decisions/ADR-007-citation-contract-and-refusal-rules.md` - strict citation/refusal contract.
- `docs/decisions/ADR-008-guard-architecture.md` - guard architecture, injection probe semantics, and no-weakening constraint.

### Seed Corpus And Evaluation Artifacts
- `ai-service/eval/corpus/manifest.json` - canonical 16-document Russian corpus manifest with title, path, department, doc type, access level, language, and summaries.
- `ai-service/eval/corpus/documents/` - the 16 frozen Russian Markdown documents to upload through Java.
- `ai-service/eval/golden/golden_ru.jsonl` - 40-record Russian golden dataset used by the final eval evidence.
- `ai-service/eval/golden/golden_ru.meta.json` - corpus hash, version, document count, and prior indexed-document mapping.
- `ai-service/eval/validate_corpus.py` - validates frozen corpus count/hash and metadata consistency.
- `ai-service/eval/graph_corpus_state.py` - compares expected golden documents to Neo4j and Java document state; useful for F-08/orphan verification.
- `ai-service/eval/ragas_runner.py` - production `/v1/query` RAGAS runner with concurrency=1, score-only path, and retry knobs.
- `ai-service/eval/query_client.py` - production query collection and retrieved context extraction for reports.
- `ai-service/eval/injection_runner.py` - injection/data-exfiltration probe definitions and report semantics.
- `ai-service/eval/reports/ragas_ru.md` - current post-fix RAGAS human report, including remaining false outcomes and route mix.
- `ai-service/eval/reports/ragas_ru.json` - machine-readable post-fix RAGAS details, route source/reason, outcomes, and citations.
- `ai-service/eval/reports/injection_ru.md` - current injection report showing data-exfiltration resisted but not guard-classified.

### Java, Frontend, And Contracts
- `contracts/openapi/api-v1.yaml` - Java/frontend document upload/delete/list/raw API, chat query contract, citation `documentTitle`, and Problem Details shape.
- `contracts/openapi/ai-service-v1.yaml` - internal Python query contract, retrieval metadata, citations, guard verdict, and health/readiness.
- `contracts/constants.yaml` - shared error/reason codes for document, query, and guard outcomes.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/DocumentController.java` - Java document list/upload/delete/raw API used by seed reset.
- `backend/corp-rag-app/src/main/java/com/corprag/service/document/DocumentUploadCommand.java` - upload metadata fields available for seed identity.
- `backend/corp-rag-app/src/main/java/com/corprag/service/document/DocumentUploadService.java` - Java upload behavior, duplicate detection, metadata persistence, and outbox publication.
- `backend/corp-rag-app/src/main/java/com/corprag/service/document/DocumentDeletionService.java` - Java delete behavior and outbox publication required for normal index cleanup.
- `backend/corp-rag-app/src/main/java/com/corprag/repository/DocumentRepository.java` - document list/status fields and visibility filtering.
- `backend/corp-rag-app/src/main/java/com/corprag/service/chat/ChatQueryService.java` - Java chat-to-Python orchestration used by final core regression.
- `frontend/js/pages/admin/documents-page.js` - current admin document upload/open raw UI and BL-UAT polish surface.
- `frontend/js/api/admin-api.js` - frontend document API client used by admin document flows.
- `frontend/js/components/chat/diagnostics-panel.js` - user-facing retrieval diagnostics surface for demo, not a new observability product.
- `ai-service/src/corp_rag_ai/pipeline/guards/input_guard.py` - input guard classification surface if data-exfiltration stretch work is attempted.
- `ai-service/src/corp_rag_ai/pipeline/routing/query_router.py` - router surface if `ru-factual-009` stretch work is attempted.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `infra/docker-compose.yml` already defines the full local stack and service healthchecks. Phase 8 should verify and document it, not replace it.
- `infra/README.md` already documents service URLs, memory contours, core live checks, model cache volume, and Langfuse notes; final README work should build on this.
- Java `DocumentController` exposes multipart upload and delete under `/api/v1/documents`, which is the required seed path.
- Java document metadata includes `title`, `description`, `originalFilename`, `accessLevel`, `department`, `docType`, `language`, status, chunk count, and indexed timestamps.
- `ai-service/eval/corpus/manifest.json` already has the 16-document metadata needed to drive upload fields.
- `ai-service/eval/graph_corpus_state.py` already contains comparison logic for Java/Neo4j corpus state and should be reused or wrapped rather than duplicated.
- `ai-service/eval/ragas_runner.py` already supports production query collection, score-only scoring, `concurrency=1`, and RAGAS retry knobs.
- `ai-service/eval/injection_runner.py` already treats data-exfiltration as a finding when the system resists via no-evidence/unsupported instead of explicit guard refusal.

### Established Patterns
- Browser and demo scripts should talk to Java for product operations. Python remains internal except for eval/diagnostics tooling.
- Document lifecycle cleanup is event-driven through Java delete -> outbox/RabbitMQ -> Python cleanup. Volume wiping bypasses the behavior Phase 8 needs to prove.
- RAGAS is stochastic and external-judge-dependent; it is evidence, not a deterministic pass/fail CI gate.
- Eval and demo scripts should be explicit and opt-in. Do not add paid/network-dependent work to normal unit test suites.
- Generated report artifacts are useful, but stochastic report commits require user validation.

### Integration Points
- Create or update a seed/reset script that logs in as admin, lists/deletes prior seed docs, uploads all 16 manifest documents, waits for indexing, and verifies Java/Qdrant/Neo4j state.
- Extend README/runbook docs with prerequisites, env setup, compose startup, health checks, seed reset, demo script, final regression commands, and known limitations.
- Add final evidence files under the Phase 8 planning directory or a documented reports location, including compose health, seed/index summary, chat/citation proof, and eval summary.
- If BL-UAT-01 is handled, inspect Java/MinIO raw content-type behavior and frontend raw-open behavior narrowly.
- If data-exfiltration guard stretch work is handled, add targeted guard tests plus injection runner verification.
- If router stretch work is handled, add general Russian/localization router tests and avoid golden-record-specific matching.

</code_context>

<specifics>
## Specific Ideas

- Phase 7 docs commit referenced by the user: `e28dab3`.
- User-selected discussion outcome: `1A` idempotent reset, `2A` core path + eval, `3C` first, then `3A` stretch, with `3B` lowest priority.
- Required seed outcome: exactly 16 seeded documents, no duplicates, all indexed, clean Qdrant/Neo4j counts, and no `down -v`.
- Required final regression chain: 9/9 healthy -> seed/index -> chat -> citation -> one RAGAS/eval run.
- RAGAS run safeguards: `--ragas-max-retries 1`, `--ragas-max-wait 5`, `concurrency=1`, monitor `reranker_degraded_count=0`.
- Demo story should include factual Russian questions, citation chips/source evidence, Langfuse trace latency breakdown with rerank around 16 seconds if observed, and an injection/refusal example.
- Known limitation wording should be explicit: multi-hop graph retrieval can refuse safely when current graph evidence is too weak; this is a product limitation, not a hidden crash.
- Traceability cleanup should mark implemented Phase 5 requirements accurately while preserving the known limitation for full multi-hop graph quality.

</specifics>

<deferred>
## Deferred Ideas

- Full text-conditioned multi-hop graph retrieval for `ru-multihop-002/003/005/006`, including semantic path ranking, better entity linking, and duplicate path suppression.
- New deployment or production compose topology.
- Full replay of Phase 7 ablation and injection reports as a mandatory Phase 8 gate.
- Training or broad retuning of the query router against the golden dataset.
- A new frontend observability product surface beyond existing diagnostics and Langfuse UI.

</deferred>

---

*Phase: 8-Delivery Polish & Demo Readiness*
*Context gathered: 2026-06-01*
