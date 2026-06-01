# Phase 7: Evaluation & Observability - Context

**Gathered:** 2026-06-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 7 delivers measurable evidence for the Corporate RAG System: a frozen Russian demo corpus, a Russian-first golden dataset, repeatable quality and retrieval metric runners, injection-probe reporting, vector retrieval ablations, graph-route reporting, Langfuse traces, and lightweight runtime diagnostics.

This phase turns the working Phase 6 application into a defensible diploma/demo system. It does not add new user-facing frontend observability screens, production monitoring infrastructure, backup automation, streaming answers, or delivery polish assets reserved for Phase 8.

</domain>

<decisions>
## Implementation Decisions

### Golden Dataset And Corpus Binding
- **D-331:** The scored golden dataset is Russian-first and monolingual. Golden questions, reference answers, and expected-citation reasoning are in Russian because the demo corpus is Russian aviation/logistics material.
- **D-332:** Do not build a bilingual scored dataset. Existing English Phase 5 test documents are not part of the demo story. If English sanity coverage is useful, keep it in a separate smoke file that is not counted in scored reports.
- **D-333:** The scored dataset contains 40 questions: 10 factual, 10 aggregation, 10 multi-hop, and 10 out-of-scope.
- **D-334:** The out-of-scope bucket is split approximately 6 genuinely absent/no-evidence cases and 4 guard-refusal cases, so evaluation exercises both `refused_no_evidence` and `refused_guard`.
- **D-335:** Golden records require authoritative document-level expectations, not exact chunk IDs. `expected_doc_ids[]` is the hard retrieval target for recall@k and MRR.
- **D-336:** Chunk-level expectations are advisory only. `expected_chunk_hint` may store a free-text span or section path, but it is never a hard assertion because chunk IDs and boundaries can shift after re-indexing.
- **D-337:** The scored dataset lives at `ai-service/eval/golden/golden_ru.jsonl`, one JSON object per line.
- **D-338:** Each JSONL record uses this schema: `{id, type, question, reference_answer, expected_doc_ids[], expected_chunk_hint?, expected_outcome, notes}`. `expected_outcome` is one of `answered`, `refused_no_evidence`, or `refused_guard`.
- **D-339:** Use JSONL, not CSV, because Russian reference answers may contain multi-line prose, commas, and quotes.
- **D-340:** Corpus binding is critical and non-negotiable: regenerate 16 synthetic aviation/logistics documents, commit the frozen corpus snapshot, index that snapshot, then author golden answers. If the corpus regenerates after authoring, document bindings can break silently.
- **D-341:** Store corpus version/hash metadata next to the dataset in `ai-service/eval/golden/golden_ru.meta.json`. Runners and reports must surface this metadata.

### Metric And Report Contract
- **D-342:** Phase 7 reports are demo artifacts and regression baselines, not hard CI gates.
- **D-343:** RAGAS uses an LLM judge through DeepSeek/OpenRouter and is non-deterministic, paid/network-dependent, and unsuitable as a hard CI gate.
- **D-344:** RAGAS thresholds are recorded as expected ranges and deviations are flagged in the report instead of failing CI.
- **D-345:** Deterministic evaluation pieces such as retrieval recall@k/MRR and injection block-rate may be asserted by non-LLM tests if planning wants a lightweight gate.
- **D-346:** Initial diploma narrative targets are faithfulness >= 0.85 and answer relevancy >= 0.80. Tune only after the first honest baseline is recorded.
- **D-347:** Context precision and context recall are reported without a hard floor. These metrics expose the retrieval ceiling honestly rather than becoming a brittle pass/fail gate.
- **D-348:** Retrieval metrics report recall@5, recall@10, and MRR over `expected_doc_ids[]`.
- **D-349:** Injection probes report blocked/total per attack category. Prompt-injection and exfiltration target >= 95% block rate; citation-bypass target is 100%.
- **D-350:** Never tune or weaken the guard solely to hit an injection metric. Probe results measure guard behavior; they do not drive unsafe guard changes.
- **D-351:** Runnable eval code, datasets, and harness helpers live under `ai-service/eval/`.
- **D-352:** Generated report artifacts are committed under `ai-service/eval/reports/` as both human-readable Markdown and machine-readable JSON/CSV where useful.
- **D-353:** The phase narrative summary belongs at `.planning/phases/07-evaluation-observability/07-EVAL-SUMMARY.md` and links to committed eval reports. Do not put Python runners under `.planning/`.

### Ablation Variants
- **D-354:** Run five vector retrieval variants for ablation: `bm25`, `dense`, `sparse`, `hybrid`, and `hybrid+reranker`.
- **D-355:** Current query retrieval is hardcoded around dense+sparse RRF. Phase 7 must build an eval-only retrieval-mode parameter before the five-way ablation can run.
- **D-356:** Retrieval-mode selection belongs in an internal eval entry point under `ai-service/eval/` that calls retrieval components directly. Do not expose a new production `/v1/query` mode.
- **D-357:** If an environment knob is used, it must be eval-guarded and default-off so it cannot accidentally alter production/demo query behavior.
- **D-358:** BM25 is evaluation-only. It may use a local BM25 harness such as `rank_bm25` over the same chunk corpus, or another explicitly eval-only baseline, but it must not become a production retriever or route.
- **D-359:** Keep `sparse` and `bm25` distinct. `sparse` means bge-m3 learned sparse vectors through Qdrant sparse retrieval; `bm25` means classical lexical retrieval in the eval harness.
- **D-360:** `dense` means Qdrant dense vector retrieval only; `hybrid` means dense+sparse RRF; `hybrid+reranker` means production-style hybrid retrieval followed by the local reranker.
- **D-361:** Ablation scope is retrieval metrics only: recall@k, MRR, and optionally nDCG. Do not run full RAGAS across all five variants because the LLM judge cost adds little narrative value.
- **D-362:** Run RAGAS once on the production configuration, `hybrid+reranker`.
- **D-363:** Graph routes are evaluated separately from the five-way vector matrix. Aggregation/comparison graph retrieval uses lexical `queryMatchScore` and is not comparable to vector variants.
- **D-364:** Do not average graph-route questions into the vector ablation score. Report graph-route quality in its own section: citeable evidence found, no-evidence behavior, and guard/refusal behavior where applicable.

### Observability Surface
- **D-365:** Add Langfuse instrumentation as a build task. The repository currently has Langfuse container/config values, but no Python Langfuse dependency or client wiring.
- **D-366:** Use one root Langfuse trace per Python `/v1/query`.
- **D-367:** Add child spans matching the real query graph: `input_guard`, `route`, `hybrid_retrieval` or `graph_retrieval`, `parent_resolve`, `rerank`, `pack_context`, `synthesize`, `output_guard`, and `finalize`.
- **D-368:** Span attributes must include existing `retrievalMeta` fields: route, retrievers used, reranker used, degradation warnings, chunks considered/returned, latency, and model id.
- **D-369:** Span attributes also include guard verdicts where applicable. Do not include secrets.
- **D-370:** Synthesis LLM calls must be traced as Langfuse generations with input prompt, output, token usage where available, and model id so DeepSeek/OpenRouter cost and latency are visible.
- **D-371:** Prefer explicit async span context managers in node methods over magic decorators if decorators do not cooperate with LangGraph async nodes. Verify tracing in Docker, not only in local unit tests.
- **D-372:** Service metrics stay minimal and demo-honest. Do not add Prometheus or Grafana in Phase 7.
- **D-373:** Expand `/diagnostics` lightly with aggregate counters: total queries, answered count/rate, refused/no-evidence count, guard-blocked count, reranker-degraded count, mean latency, and a Langfuse reachable/configured flag.
- **D-374:** Keep `/diagnostics` read-only and unauthenticated-internal, consistent with the existing endpoint. Do not turn it into an admin feature.
- **D-375:** Do not build a new frontend observability screen. Langfuse already provides the demo UI at `:3000`, and frontend/admin feature work belongs outside Phase 7.

### Sequencing And Stability
- **D-376:** Phase 7 planning must start with a stability wave before eval execution: increase local model memory contour to roughly 8-9 GiB if needed, diagnose first-turn cold start, and add model pre-warm where useful.
- **D-377:** The code wave must land before eval execution: Langfuse instrumentation, eval-only ablation modes, BM25 harness, corpus regeneration/freeze, and indexing path.
- **D-378:** Do not schedule RAGAS or ablation execution before the corpus is frozen and indexed, and before judge/model wiring is in place.
- **D-379:** Eval execution waves follow the code wave: golden authoring, production-config RAGAS run, retrieval ablation run, injection probe run, and report assembly.
- **D-380:** Generated reports must name the corpus hash/version, model id, eval timestamp, runner configuration, and whether external LLM judge calls were used.

### Do-Not-Break Gates
- **D-381:** Access filters must never be broadened to improve recall or ablation scores.
- **D-382:** Citation validation remains strict: answered responses must only contain `[N]` references that map to returned citations.
- **D-383:** BM25 and retrieval-mode switches must remain eval-only and must not leak into normal `/v1/query`.
- **D-384:** Existing Phase 6 frontend behavior remains closed; do not add a metrics/traces view.
- **D-385:** Existing guard behavior is measured, not weakened, by injection probes.

### the agent's Discretion
- Choose exact eval runner CLI names, module boundaries, JSON summary shape, and report filenames if they stay under `ai-service/eval/` and `ai-service/eval/reports/`.
- Choose exact BM25 library or implementation if it remains eval-only and indexes the same frozen chunk corpus.
- Choose exact Langfuse helper/client abstraction if spans match the required node names and Docker verification proves traces appear.
- Choose exact memory contour between 8 and 9 GiB and pre-warm mechanics based on observed Docker behavior.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning State
- `.planning/PROJECT.md` - project value, architecture constraints, Russian/diploma context, and requirement that evaluation makes the system defensible.
- `.planning/REQUIREMENTS.md` - Phase 7 requirements `EVAL-01`, `EVAL-02`, `EVAL-03`, `EVAL-04`, and `OPS-01`.
- `.planning/ROADMAP.md` - Phase 7 goal, success criteria, dependency on Phase 6, and Phase 8 boundary.
- `.planning/STATE.md` - current readiness, Phase 6 UAT status, residual backlog notes, and Phase 7 focus.
- `.planning/BACKLOG.md` - Phase 5/5.1 and Phase 6 residual observations that may inform stability diagnostics, but do not automatically expand Phase 7.

### Prior Phase Decisions
- `.planning/phases/05-retrieval-guards-query-api/05-CONTEXT.md` - access-filter invariants, retrieval metadata, guard behavior, citation/refusal policy, BM25 as evaluation-only baseline, and Phase 7 deferrals.
- `.planning/phases/05.1-phase-5-uat-fix-wave/05.1-CONTEXT.md` - reranker degradation, graph citation fixes, live re-UAT expectations, and graph text safety.
- `.planning/phases/06-chat-frontend-experience/06-CONTEXT.md` - Java chat persistence, query audit, frontend diagnostics display, source viewer constraints, and no-new-frontend-observability boundary.
- `.planning/phases/06-chat-frontend-experience/06-HUMAN-UAT.md` - latest human UAT evidence for the live browser/chat path that Phase 7 evaluates.
- `.planning/phases/06-chat-frontend-experience/06-UAT-EVIDENCE.md` - Phase 6 UAT evidence and residual Low/OBS notes.

### Architecture And ADRs
- `docs/CONTEXT.md` - original diploma framing: Russian corporate RAG, evaluation methodology, ablation table, injection probes, and Langfuse traces.
- `docs/ARCHITECTURE.md` - target eval directory shape, RAGAS/retrieval metrics, BM25 ablation baseline, query pipeline, and observability notes.
- `docs/PATTERNS.md` - code organization, timeout, retrieval, and testability patterns.
- `docs/decisions/ADR-001-embedding-model.md` - bge-m3 dense+sparse decision and BM25 as ablation baseline context.
- `docs/decisions/ADR-002-vector-database.md` - Qdrant dense+sparse vector storage and payload-filtered retrieval decision.
- `docs/decisions/ADR-004-llm-provider-deepseek-openrouter.md` - DeepSeek/OpenRouter provider context relevant to RAGAS judge and synthesis tracing.
- `docs/decisions/ADR-006-degraded-mode-policy.md` - fail-loud degraded behavior and diagnostics expectations.
- `docs/decisions/ADR-007-citation-contract-and-refusal-rules.md` - strict citation/refusal behavior that eval must measure without weakening.
- `docs/decisions/ADR-008-guard-architecture.md` - guard architecture and probe categories.

### Contracts
- `contracts/openapi/ai-service-v1.yaml` - internal Python query contract, `RetrievalOptions`, `RetrievalMeta`, guard verdict, citations, and ablation/debug-related fields.
- `contracts/openapi/api-v1.yaml` - Java/frontend-facing chat response and persisted `Message.retrievalMeta` contract.
- `contracts/constants.yaml` - shared error/reason codes for query, retrieval, and guard outcomes.

### Python Query And Eval Integration Points
- `ai-service/pyproject.toml` - add eval and Langfuse dependencies here, respecting existing dev-group pattern.
- `ai-service/src/corp_rag_ai/main.py` - FastAPI app, lifespan wiring, `/diagnostics`, and the place where Langfuse client/counters may attach.
- `ai-service/src/corp_rag_ai/config.py` - existing Langfuse host/public/secret settings, query/reranker timeout settings, and eval-relevant knobs.
- `ai-service/src/corp_rag_ai/adapters/rest/query.py` - `/v1/query` adapter, timeout behavior, contract mapping, and response metadata.
- `ai-service/src/corp_rag_ai/domain/retrieval.py` - retrieval candidate, citation draft, retrieval metadata, and failure reason domain records.
- `ai-service/src/corp_rag_ai/agent/graph.py` - LangGraph node flow that should receive explicit trace spans.
- `ai-service/src/corp_rag_ai/pipeline/retrieval/hybrid.py` - current hardcoded hybrid retrieval path that needs eval-only mode support.
- `ai-service/src/corp_rag_ai/pipeline/retrieval/graph.py` - graph retrieval behavior to report separately from vector ablation.
- `ai-service/src/corp_rag_ai/pipeline/retrieval/graph_query_helpers.py` - graph lexical `queryMatchScore` and access-filter Cypher helpers.
- `ai-service/src/corp_rag_ai/pipeline/retrieval/reranker.py` - hybrid+reranker ablation and reranker-degraded diagnostics.
- `ai-service/src/corp_rag_ai/pipeline/guards/input_guard.py` - guard-block behavior for injection probes.
- `ai-service/src/corp_rag_ai/pipeline/guards/output_guard.py` - citation and unsafe-evidence validation that eval must preserve.
- `ai-service/tests/test_query_pipeline.py` - existing mocked query-path coverage to extend or protect while adding tracing/eval hooks.
- `ai-service/tests/test_diagnostics.py` - current diagnostics expectations to extend for counters/Langfuse status.

### Java, Frontend, And Infrastructure Context
- `backend/corp-rag-app/src/main/java/com/corprag/service/chat/ChatQueryAuditService.java` - Java audit metadata already captures retrieval and outcome details.
- `backend/corp-rag-app/src/main/java/com/corprag/service/chat/ChatQueryService.java` - Java orchestration/persistence surface for query outcomes that Phase 7 reports may correlate with.
- `frontend/js/components/chat/diagnostics-panel.js` - existing user-facing collapsed retrieval diagnostics; do not expand into a new observability screen.
- `infra/docker-compose.yml` - Langfuse service, Python memory contour, existing env wiring, and Docker verification target.
- `infra/README.md` - local stack and diagnostics usage.

### Planned Phase 7 Artifacts
- `ai-service/eval/golden/golden_ru.jsonl` - scored Russian golden dataset to create after the corpus is frozen.
- `ai-service/eval/golden/golden_ru.meta.json` - corpus hash/version metadata required by runners and reports.
- `ai-service/eval/reports/` - committed generated Markdown, JSON, and CSV evaluation reports.
- `.planning/phases/07-evaluation-observability/07-EVAL-SUMMARY.md` - final narrative summary linking to reports and roadmap/state evidence.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Python `/v1/query` already returns `RetrievalMeta` with route, retrievers attempted/used, latency, chunks considered/returned, reranker usage, model id, and degradation warnings.
- Java chat persistence and audit already store query outcome, retrieval metadata, correlation ids, citation counts, upstream errors, and assistant status.
- Frontend already renders collapsed retrieval diagnostics from `retrievalMeta`, but Phase 7 should not add more frontend surface.
- `config.py` already has Langfuse host/public/secret settings, but no Langfuse dependency or client is implemented.
- `infra/docker-compose.yml` already runs Langfuse and wires Python `LANGFUSE_*` values.
- Hybrid and graph retrievers already exist as direct Python components suitable for eval harness calls.
- Existing tests cover diagnostics, query pipeline, reranker degradation, hybrid retrieval, graph retrieval, output guard, and query API mapping.

### Established Patterns
- Runtime contracts live under root `contracts/`, but eval-only harnesses can call Python internals directly when the behavior must not become a production API surface.
- Java remains browser-facing; Python owns RAG/eval code and applies Java-provided access filters.
- Generated contract code remains build output. Do not commit generated contract artifacts for eval changes.
- Metrics and reports should be explicit, reproducible artifacts, not implicit console output.
- External API and live-model tests are skipped or opt-in by default; deterministic tests can run without paid/network dependencies.

### Integration Points
- Add `ai-service/eval/` with golden data, BM25/vector ablation runners, RAGAS runner, injection probe runner, shared report writer, and report outputs.
- Add eval-only retrieval mode support near `HybridRetriever` and `QdrantVectorIndex` helpers while keeping `/v1/query` production behavior unchanged.
- Add Langfuse client/helper wiring around `QueryGraphNodes` or equivalent graph-node methods, then verify root/child spans in Docker.
- Extend `/diagnostics` and diagnostics tests with cheap aggregate counters and Langfuse status.
- Add corpus freeze/index workflow or scripts before golden authoring and require reports to record corpus hash/version.

</code_context>

<specifics>
## Specific Ideas

- Golden dataset path: `ai-service/eval/golden/golden_ru.jsonl`.
- Golden metadata path: `ai-service/eval/golden/golden_ru.meta.json`.
- Golden schema: `{id, type, question, reference_answer, expected_doc_ids[], expected_chunk_hint?, expected_outcome, notes}`.
- Dataset size: 40 scored Russian questions, 10 per type.
- Demo corpus: 16 frozen synthetic Russian aviation/logistics documents.
- Required sequence: regenerate corpus, commit corpus, index corpus, then write golden answers.
- RAGAS runs once on production `hybrid+reranker`, while ablation runs cheap retrieval metrics across five variants.
- Langfuse trace node names should mirror the actual query graph, not generic "query" spans.
- Wave order should be stability first, then code/instrumentation/harness, then eval execution and report assembly.

</specifics>

<deferred>
## Deferred Ideas

- Bilingual or English scored evaluation dataset.
- Hard CI gates for stochastic RAGAS judge metrics.
- Exact chunk-id assertions as hard golden dataset requirements.
- Production `/v1/query` retrieval-mode API or global runtime retrieval-mode env toggle.
- Full RAGAS execution across all five ablation variants.
- Prometheus/Grafana stack.
- New frontend/admin observability screen.
- Guard tuning solely to satisfy injection probe percentages.

</deferred>

---

*Phase: 7-Evaluation & Observability*
*Context gathered: 2026-06-01*
