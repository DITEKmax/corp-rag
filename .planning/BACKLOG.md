---
status: active
updated: 2026-05-26
source:
  - ".planning/phases/05-retrieval-guards-query-api/05-UAT-EVIDENCE.md"
  - ".planning/phases/05-retrieval-guards-query-api/PHASE5-UAT-FIX-REPORT.md"
  - ".planning/phases/05.1-phase-5-uat-fix-wave/05.1-UAT-EVIDENCE.md"
  - ".planning/phases/05.1-phase-5-uat-fix-wave/05.1-05-SUMMARY.md"
---

# Project Backlog

These items are deferred follow-ups. They do not block Phase 6. Phase 5.1 is closed: PH5-UAT-DEF-02/03/04, PH5.1-DEF-A, PH5-UAT-DEF-06, and P4 are closed by the 05.1 evidence.

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
Status: Open

Symptom:
- For single-citation graph `AGGREGATION` answers, the LLM occasionally omits a valid inline `[N]` ref.
- The output guard correctly blocks these responses with `guardVerdict.reason=missing_citations`.
- A rerun can produce `[1]` and pass. This is synthesis variance, not a citation-pipeline bug: the pipeline supplies document-backed citations and the guard enforces inline-ref validity.

Action:
- In Phase 6 chat work, harden the synthesis prompt so single-citation answers reliably include an inline citation reference.
- Do not weaken the output guard or evidence gate to mask this.

Acceptance:
- Repeated single-citation graph aggregation probes produce cited answers, or deterministic refusals only when evidence is genuinely missing.
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

