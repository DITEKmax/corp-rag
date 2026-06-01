---
status: active
updated: 2026-06-02
source:
  - ".planning/phases/05-retrieval-guards-query-api/05-UAT-EVIDENCE.md"
  - ".planning/phases/05-retrieval-guards-query-api/PHASE5-UAT-FIX-REPORT.md"
  - ".planning/phases/05.1-phase-5-uat-fix-wave/05.1-UAT-EVIDENCE.md"
  - ".planning/phases/05.1-phase-5-uat-fix-wave/05.1-05-SUMMARY.md"
  - ".planning/phases/06-chat-frontend-experience/06-HUMAN-UAT.md"
  - ".planning/phases/06-chat-frontend-experience/06-UAT-EVIDENCE.md"
  - ".planning/phases/08-delivery-polish-demo-readiness/08-KNOWN-LIMITATIONS.md"
---

# Project Backlog

These items are deferred follow-ups. They do not block Phase 7. Phase 5.1 is closed: PH5-UAT-DEF-02/03/04, PH5.1-DEF-A, PH5-UAT-DEF-06, and P4 are closed by the 05.1 evidence. Phase 6 is closed by live human UAT on 2026-06-01; its remaining items are Low/OBS unless noted otherwise.

## BL-01 - PH5.1-DEF-B: uv Base Image Unpinned and Dockerfile Workaround Uncommitted

Priority: High-ish
Area: infra reproducibility
Status: Open

Current state:
- `ai-service/Dockerfile` is modified in the local worktree from `ghcr.io/astral-sh/uv:0.5.26-python3.12-bookworm` to `astral/uv:python3.12-bookworm` because the Docker daemon cannot reach ghcr.io.
- `ai-service/Dockerfile.bak` exists locally and contains the pinned ghcr.io base image.
- Both files are intentionally uncommitted at the time this backlog item is recorded.
- Python package versions remain pinned through `ai-service/uv.lock`; only the uv tool image tag/source is unpinned.

Risk:
- `git checkout`, `git clean`, or a fresh clone will lose the local Docker Hub workaround and the next clean `python-ai` build may fail if the Docker daemon still cannot reach ghcr.io.
- The uv tool version is not pinned while using `astral/uv:python3.12-bookworm`.

Action options:
- Restore `ghcr.io/astral-sh/uv:0.5.26-python3.12-bookworm` once the Docker daemon can reach ghcr.io, or configure a registry mirror.
- Or commit the Docker Hub base-image change explicitly with an inline comment such as: `TEMP workaround: ghcr.io unreachable from daemon; revert to pinned uv when available`.

Acceptance:
- A clean checkout can build `python-ai` without undocumented local edits.
- The final chosen base-image policy is documented.

## BL-02 - Single-Citation Aggregation Synthesis Variance

Priority: Medium
Area: synthesis quality
Status: Closed in Phase 6 UAT

Symptom:
- For single-citation graph `AGGREGATION` answers, the LLM occasionally omits a valid inline `[N]` ref.
- The output guard correctly blocks these responses with `guardVerdict.reason=missing_citations`.
- A rerun can produce `[1]` and pass. This is synthesis variance, not a citation-pipeline bug: the pipeline supplies document-backed citations and the guard enforces inline-ref validity.

Closure:
- Phase 6 UAT `DEFECT-08` hardened citation-critical synthesis without weakening the output guard.
- Live retest produced 10/10 answered runs.

Action:
- Done in Phase 6 UAT fix wave: harden citation-critical synthesis so single-citation answers reliably include an inline citation reference.
- Preserve the strict output guard; do not weaken `missing_citations` or evidence gates.

Acceptance:
- Met in Phase 6 UAT: repeated graph aggregation probes produced cited answers in 10/10 runs.
- Output guard remains strict for `missing_citations` and out-of-range refs.

## BL-03 - Aggregation Graph Match Is Lexical, Not Semantic

Priority: Low
Area: retrieval heuristic
Status: Open / known limitation

Current behavior:
- Aggregation graph retrieval uses `queryMatchScore`, a lexical term-overlap score with light stemming.
- It filters graph rows to terms matching document title, entity name/type, or document department.

Risk:
- Questions whose wording diverges lexically from document terms, such as synonyms or paraphrases, may under-match and under-score.

Action:
- Revisit if aggregation recall becomes a problem.
- Candidate improvements include semantic expansion, graph-specific synonyms, or hybrid graph/vector fallback for aggregation.

Acceptance:
- Any future semantic expansion preserves the no-evidence safety proven by the aviation graph probe.

## BL-04 - Reranker `compute_score` Score Stability Investigation

Priority: Low
Area: retrieval confidence
Status: Open

Symptom:
- During PH5.1-DEF-A debugging, manual `FlagReranker.compute_score(...)` checks on near-identical candidate sets produced materially different top scores, including roughly `0.806`, `0.462`, and `0.334`.
- A cross-encoder should be deterministic for identical inputs, so this needs explanation.

Action:
- Verify whether `compute_score(..., normalize=True)` is deterministic for identical query/passage pairs.
- Check whether candidate set size, batching, ordering, text prefixes, or normalization explain the observed variation.

Acceptance:
- Either deterministic behavior is proven for identical inputs, or the confidence model is documented as sensitive to candidate set/order and handled accordingly.

## BL-07 - Phase 8 Multi-Hop Graph Retrieval Debt From Phase 07.1

Priority: High for Phase 8
Area: graph retrieval / Russian golden regression
Status: Waived for Phase 8 demo / Future work

Source:
- `.planning/phases/07.1-fix-russian-router-and-graph-retrieval-quality-for-ragas-bas/07.1-03-SUMMARY.md`
- `ai-service/eval/reports/ragas_ru.json`

Current behavior:
- Phase 07.1 fixed false `UNSUPPORTED` routing for the five target records.
- `ru-aggregation-003` now answers through `AGGREGATION`.
- `ru-multihop-002`, `ru-multihop-003`, `ru-multihop-005`, and `ru-multihop-006` now route correctly to `MULTI_HOP`, but still return `refused_no_evidence`.

Finding:
- These four records are no longer router/localization failures.
- They expose graph multi-hop retrieval weakness: current graph retrieval does not reliably gather text-conditioned multi-document evidence for Russian multi-hop questions.

Action:
- Phase 8 Plan 08-05 explicitly waives text-conditioned graph multi-hop retrieval for the demo scope.
- Future work candidates include Russian entity linking, semantic path ranking, duplicate path suppression, and hybrid graph/vector fallback for multi-document evidence.

Acceptance:
- Met for Phase 8 demo readiness by documented waiver in `.planning/phases/08-delivery-polish-demo-readiness/08-KNOWN-LIMITATIONS.md`.
- Future retrieval work must make the four records answer with valid document-backed citations without weakening citation validation, weak-evidence thresholds, or access filters.

## BL-06 - Phase 6 UAT Low/OBS Follow-Ups

Priority: Low / Info
Area: Phase 6 UAT follow-ups
Status: Open

Source:
- `.planning/phases/06-chat-frontend-experience/06-HUMAN-UAT.md`
- `.planning/phases/06-chat-frontend-experience/06-UAT-EVIDENCE.md`

These items came from the final Phase 6 live UAT on 2026-06-01. They do not block Phase 6 or Phase 7. Good candidates are Phase 8 Delivery Polish, or earlier opportunistic fixes.

### BL-UAT-01 - Raw Russian `.txt`/`.md` Browser View Uses Wrong Charset

Severity: Low
Status: Closed in Phase 8 Plan 08-05

Symptom:
- Admin Documents "Open raw" for Russian text shows mojibake such as `РџРѕР»РёС‚РёРєР°` instead of `Политика`.

Known-good evidence:
- Stored file is clean UTF-8 without BOM.
- Qdrant text is readable Russian.
- Source modal displays clean Russian.
- Only direct browser rendering of the MinIO object is affected.

Root cause:
- MinIO returns text objects as `Content-Type: text/plain` without `charset=utf-8`; browsers can guess Windows-1251 for Cyrillic.

Fix options:
- Save text uploads with `Content-Type: text/plain; charset=utf-8`.
- Or add a presigned URL `response-content-type` override for text types so existing objects render correctly.

Closure:
- Phase 8 Plan 08-05 adds a narrow MinIO presigned URL `response-content-type` override for `.txt`, `.md`, `text/plain`, and `text/markdown` raw views.
- Access control remains in Java before URL issuance; raw bytes are not proxied through Java and storage metadata/schema are unchanged.

Acceptance:
- Met by the UTF-8 raw-view content-type path and unit coverage for text and non-text documents.

### BL-UAT-05 - Explicit Data-Exfiltration Guard Classification

Severity: Low / stretch
Status: Future work / not attempted in Phase 8 Plan 08-05

Source:
- `ai-service/eval/reports/injection_ru.md`
- `.planning/phases/08-delivery-polish-demo-readiness/08-KNOWN-LIMITATIONS.md`

Current behavior:
- Data-exfiltration probes are blocked from succeeding, but they currently fall through as `refused_no_evidence` / `UNSUPPORTED` rather than an explicit `refused_guard` verdict.

Action:
- If attempted later, add explicit data-exfiltration guard classification without weakening current prompt-injection, jailbreak, citation, output guard, access-filter, or refusal behavior.

Acceptance:
- Injection probes continue to block attacks and data-exfiltration cases gain an explicit guard verdict.

### BL-UAT-06 - `ru-factual-009` Router False-Unsupported Stretch

Severity: Low / eval stretch
Status: Future work / not attempted in Phase 8 Plan 08-05

Source:
- `ai-service/eval/reports/ragas_ru.md`
- `.planning/phases/08-delivery-polish-demo-readiness/08-KNOWN-LIMITATIONS.md`

Current behavior:
- `ru-factual-009` is expected `answered` but currently returns `refused_no_evidence` with route `UNSUPPORTED`.

Action:
- Investigate as future router/retrieval quality work only. Do not train a classifier, retune against the golden set, or add golden-specific strings solely to improve one eval row.

Acceptance:
- Future changes improve general routing/retrieval behavior and preserve guard, citation, and access-filter contracts.

### BL-UAT-02 - Verify User Message Bubble Visibility In Chat Thread

Severity: TBD after reproduction

Symptom:
- User reported that sent user messages may not be visible in the chat thread while assistant bubbles are visible.

Current evidence:
- The issue was not directly reproduced in the final UAT screenshots.
- Conversation title derivation and `messageCount` imply the user message reaches persistence.

Checks:
- Confirm `chat_messages` contains `role=USER` for sent turns.
- Inspect `frontend/js/pages/chat-page.js` message-list rendering for role filtering or invisible user styling.

Acceptance:
- Each sent user question is visibly rendered as a user bubble in chat history and after reload.

### BL-UAT-03 - Monitor Occasional First-Turn `Response unavailable`

Severity: Low / OBS

Symptom:
- A few conversations started with an assistant turn rendered as `Response unavailable`; retry then returned `ANSWERED`.

Hypothesis:
- Cold reranker latency or first-request timeout after `python-ai` restart.

Action:
- Monitor reproducibility.
- If reproducible, inspect first-query latency, timeout budget, and reranker warm-up behavior.

### BL-UAT-04 - Improve Document Title Extraction For Markdown/YAML

Severity: Low

Symptom:
- Uploaded Markdown may show document titles such as `Title` or transliterated fallback `Politica` instead of YAML/frontmatter or first heading text, for example `Политика отпусков компании ТехКорп`.

Action:
- Improve title extraction in ingestion/upload metadata handling.

Acceptance:
- Source cards and modals show readable document titles from YAML metadata or the first content heading.

### Phase 6 OBS Items

- HATEOAS `_links.*.method` and `_links.*.title` are always null; fill them or remove them from the contract.
- Qdrant client `1.17.1` vs server `1.12.6` logs a version mismatch warning; align versions.
- `GET /favicon.ico` returns 404; add a favicon.
- `aio_pika.tools ChannelInvalidStateError: No active transport in channel` appears in `python-ai`; inspect AMQP channel resilience.
- `python-ai` memory limit around 6 GiB is tight for bge-m3 plus reranker after restart; consider 8-9 GiB for demo/runtime.
- `ai-service` Dockerfile still has the existing BL-01 production-like cleanup concern: ghcr.io reachability workaround and large CUDA-heavy image.

## BL-05 - Phase 5 Deferred Carry-Over Items

Priority: Mixed
Area: Phase 5 UAT follow-ups
Status: Open

These remain tracked from Phase 5 UAT evidence and the Phase 5 fix report.

### PH5-UAT-DEF-01 / F-04 - Entity Extraction Flaky on Relation-Dense Documents

Source:
- `.planning/phases/05-retrieval-guards-query-api/05-UAT-EVIDENCE.md`
- `.planning/phases/05-retrieval-guards-query-api/PHASE5-UAT-FIX-REPORT.md`

Symptom:
- Relation-dense incident report indexing followed a fail/fail/success pattern.
- Atomic rollback worked, but ingestion reliability is poor.

Action:
- Improve extraction validation/healing and internal diagnostic logging.
- Consider tolerant handling for malformed relation entries instead of failing the whole document.

### PH5-UAT-DEF-05 / F-05 - Local Query Timeout Default Too Small

Source:
- `.planning/phases/05-retrieval-guards-query-api/05-UAT-EVIDENCE.md`
- `.planning/phases/05-retrieval-guards-query-api/PHASE5-UAT-FIX-REPORT.md`

Symptom:
- `AI_QUERY_TIMEOUT_SECONDS=30` was too small for local CPU reranker plus DeepSeek synthesis; UAT used `120`.

Action:
- Decide and document local default timeout policy.
- Keep production/local distinction explicit if `30` remains a production-grade target.

### PH5-UAT-DEF-07 / F-07 - Qdrant-Off Aggregation Does Not Emit Vector-Degraded Metadata

Source:
- `.planning/phases/05-retrieval-guards-query-api/05-UAT-EVIDENCE.md`
- `.planning/phases/05-retrieval-guards-query-api/PHASE5-UAT-FIX-REPORT.md`
- Existing decision reference verified in `.planning/phases/05-retrieval-guards-query-api/05-CONTEXT.md`: D-209.

Symptom:
- AGGREGATION can answer through GRAPH while Qdrant is down, but does not emit `vector_retrieval_unavailable`.

Action:
- Choose between emitting vector-degraded metadata for down Qdrant regardless of route, or documenting route-scoped reporting and updating D-209 wording/tests accordingly.

### F-08 - Orphan Qdrant Point and Neo4j Document Node After Delete/Reupload

Source:
- `.planning/phases/05-retrieval-guards-query-api/PHASE5-UAT-FIX-REPORT.md`
- `.planning/phases/05-retrieval-guards-query-api/05-UAT-EVIDENCE.md`

Symptom:
- Delete/reupload cycles left one extra Qdrant point and one extra Neo4j `Document` node in UAT counts.

Action:
- Verify delete cleanup always removes Qdrant points by `documentId` and detaches/deletes Neo4j `Document` nodes, including failed or partial indexing cases.

### F-10 - Qdrant Client/Server Version Mismatch Warning

Source:
- `.planning/phases/05-retrieval-guards-query-api/PHASE5-UAT-FIX-REPORT.md`
- `.planning/phases/05-retrieval-guards-query-api/05-UAT-EVIDENCE.md`

Symptom:
- `qdrant-client==1.17.1` warns against server `qdrant/qdrant:v1.12.6`.

Action:
- Align client and server versions, then verify query/upsert/delete behavior.

### F-11 - Hugging Face Anonymous Download Throttling and Model Pre-Warm

Source:
- `.planning/phases/05-retrieval-guards-query-api/PHASE5-UAT-FIX-REPORT.md`
- `.planning/phases/05.1-phase-5-uat-fix-wave/05.1-CONTEXT.md`

Symptom:
- Anonymous Hugging Face downloads made first reranker setup slow and fragile.

Action:
- Document optional `HF_TOKEN`.
- Add a reproducible model pre-warm step for `BAAI/bge-m3` and `BAAI/bge-reranker-v2-m3`.
