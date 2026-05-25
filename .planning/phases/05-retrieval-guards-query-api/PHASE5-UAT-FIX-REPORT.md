# Phase 5 UAT — Fix Report for Codex

**Source:** Live UAT session 2026-05-25 (full Docker stack, fresh 3-doc corpus, paid `deepseek/deepseek-v4-flash`).
**Evidence file:** `.planning/phases/05-retrieval-guards-query-api/05-UAT-EVIDENCE.md`.
**Status going in:** Phase 5 query path passed all 6 functional scenarios in degraded (no-reranker) mode. The fixes below restore the originally planned behavior (working reranker, honest answers, correct citations, complete degraded-mode signaling) and clean up smaller issues observed during the session.

This report is intended as the input to a Phase 5 fix wave (e.g. `$gsd-plan-phase 5.1` or a hotfix plan set). Codex should verify each item against the actual repo files before implementing, and should NOT invent decision numbers — confirm against `05-CONTEXT.md` and `docs/decisions/`.

---

## Priority ordering

1. **F-01 (High)** — Reranker version incompatibility (reranker is completely non-functional).
2. **F-02 (High)** — Reranker runtime exception must degrade gracefully, not time out.
3. **F-03 (High)** — Graph-route citation mapping: model cites indexes that do not exist / answers blocked by missing_citations. This is the "model lies / unciteable" class.
4. **F-04 (Medium)** — Entity extraction flaky on relation-dense text.
5. **F-05 (Medium)** — Default query timeout too small for local hardware.
6. **F-06 (Medium)** — Graph citation snippet shows `entity:X` instead of document text.
7. **F-07 (Low)** — Degraded Qdrant-off does not emit `vector_retrieval_unavailable`.
8. **F-08 (Low)** — Delete/reupload leaves orphan Qdrant point + Neo4j Document node.
9. **F-09 (Low/Doc)** — ADR-004 + docs still say `:free`; record paid-tier reality and free-tier limits.
10. **F-10 (Low)** — Qdrant client/server version mismatch warning.
11. **F-11 (Info/Hardening)** — HF anonymous download throttling; optional HF_TOKEN + model pre-bake.
12. **F-12 (Info)** — Misc cleanups discovered while testing.

---

## F-01 (High) — Reranker `bge-reranker-v2-m3` is non-functional (transformers/FlagEmbedding incompatibility)

**Symptom.** `FlagReranker.compute_score(...)` raises:
```
AttributeError: XLMRobertaTokenizer has no attribute prepare_for_model
```
Traceback path:
```
FlagEmbedding/inference/reranker/encoder_only/base.py:147  -> self.tokenizer.prepare_for_model(...)
transformers/tokenization_utils_base.py:1315               -> raise AttributeError
```
The model weights load fine (`Loading weights 100%`, `RERANKER LOADED OK`); the failure is purely at tokenization/scoring time. The installed `transformers` version removed/renamed `prepare_for_model` on `XLMRobertaTokenizer`, but the installed `FlagEmbedding` still calls it.

**Impact.** With `AI_RERANKER_ENABLED=true`, every query that reaches reranking fails (manifested as query timeouts during UAT — see F-02). The reranker (D-148 / D-190, the planned final ranking step) is effectively unusable. UAT had to set `AI_RERANKER_ENABLED=false` to proceed.

**Root cause hypothesis.** Version drift in `ai-service/pyproject.toml` / `uv.lock`: `transformers` resolved to a newer major/minor than `FlagEmbedding` supports.

**Required fix.**
- Determine the compatible version window. Either:
  - (a) Pin `transformers` to the last version where `XLMRobertaTokenizer.prepare_for_model` exists and `FlagEmbedding`'s reranker path works, OR
  - (b) Upgrade `FlagEmbedding` to a version whose reranker uses the current tokenizer API (preferred if it exists and keeps bge-m3 embedding behavior intact).
- Update `ai-service/pyproject.toml` and regenerate `uv.lock`.
- Rebuild the `python-ai` image.
- Verify embeddings (bge-m3 dense+sparse) STILL work after the version change — the embedder and reranker share the FlagEmbedding/transformers stack, so do not regress Phase 4 embedding.

**Acceptance criteria.**
- A unit/integration test loads `FlagReranker('BAAI/bge-reranker-v2-m3')` and calls `compute_score([['q','passage']], normalize=True)` returning a float in `[0,1]` with no exception. Gate it so it self-skips if the model is not cached / no network, like existing live smokes.
- `bge-m3` embedding tests still pass (dense 1024 + non-empty sparse).
- With `AI_RERANKER_ENABLED=true`, Scenario 3 ("What is the vacation policy?") returns `answered=true`, `rerankerUsed=true`, no `reranker_disabled` warning, within the configured timeout.
- Full `uv run --group dev pytest tests` stays green (was 202 passed / 11 skipped).

**Notes for Codex.** Do not silently bump unrelated packages. Keep the change minimal and document the exact versions chosen in the plan/summary and in ADR-004 or a short follow-up ADR if the pin is architecturally meaningful.

---

## F-02 (High) — Reranker runtime exception must soft-degrade, not hang to timeout

**Symptom.** When the reranker was enabled but failing (F-01) or still downloading, queries did not degrade — they ran until the internal `AI_QUERY_TIMEOUT_SECONDS` elapsed and returned:
```json
{ "answered": false, "answer": "Query processing timed out...",
  "retrievalMeta": { "route": "UNSUPPORTED", "degradationWarnings": ["query_timeout"], "latencyMs": 30000, ... } }
```
By contrast, when the reranker was explicitly disabled (`AI_RERANKER_ENABLED=false`), the pipeline degraded cleanly: `rerankerUsed=false`, `degradationWarnings=["reranker_disabled"]`, `answered=true`.

**Impact.** D-193 (reranker unavailable -> raw retrieval order) is only honored for the "disabled" path, not for a runtime exception or a slow/hanging model load. A production reranker crash would take down query answering instead of degrading.

**Required fix.**
- Wrap the reranker scoring call (in `ai-service/src/corp_rag_ai/pipeline/retrieval/reranker.py`) so that ANY exception (tokenizer error, model load error, scoring error) and any timeout of the scoring step is caught and converted into the same soft-degrade path used by the disabled case: keep candidates in raw Qdrant order, slice to top-N, set `rerankerUsed=false`, and add a distinct warning (e.g. `reranker_failed` vs `reranker_disabled` so they are distinguishable in metadata).
- Consider a bounded internal timeout on the reranker scoring step itself (shorter than the overall query timeout) so a hanging model load cannot consume the whole budget.

**Acceptance criteria.**
- A test injects a reranker that raises on `compute_score`; the query still returns `answered=true` (given evidence), `rerankerUsed=false`, and `degradationWarnings` contains `reranker_failed`.
- A test injects a reranker that sleeps beyond the reranker-step timeout; same soft-degrade result.
- The overall query no longer returns `route=UNSUPPORTED` + `query_timeout` purely because of reranker problems.

---

## F-03 (High) — Graph-route citations: model references nonexistent indexes / answers blocked by missing_citations

This is the "the model must not lie / must cite correctly" item.

**Symptoms (Scenario 4, three probes).**
- Probe B "How many vendors are approved in total?": `route=AGGREGATION`, `retrieversUsed=[GRAPH]`, but `answered=false`, `guardVerdict.reason=missing_citations`, `tier=OUTPUT_CHECK`. The output guard correctly refused, but a valid aggregation question produced no answer.
- Probe C "How many vendors does the Compliance department approve?": `answered=true`, but `answer` ended with `[4]` while the `citations` array had exactly ONE element (index would be `[1]`). The output guard let `[4]` through even though it does not map to a returned citation.

So on the GRAPH route the model's inline `[N]` references do not reliably correspond to the returned citations: sometimes none are produced (guard blocks), sometimes a wrong index is produced (guard passes incorrectly).

**Impact.** Two opposite failure modes:
1. False refusal of answerable graph questions (missing_citations).
2. An answer that cites `[4]` with no `[4]` in the citation list — i.e. an unverifiable/"hallucinated" citation reference passing the guard. This is exactly the "model lies in the answer" risk we wanted to prevent.

**Root cause hypotheses (verify in code).**
- The synthesizer prompt for the graph route packs evidence differently than the hybrid route, so the model is told about more evidence items (e.g. up to 5) than end up in the final `citations` array (1), causing `[4]`/`[5]` references that the post-generation citation mapping cannot resolve.
- The output guard citation-coverage check (`ai-service/src/corp_rag_ai/pipeline/guards/output_guard.py`, per D-198) is applied inconsistently: it blocks when there are zero valid refs (Probe B) but does NOT reject an out-of-range ref `[4]` against a 1-element citation array (Probe C).

**Required fix.**
- Make the citation index space consistent: the `[N]` indexes the model is instructed to use MUST be exactly the indexes of the citations that will be returned to the client. If graph evidence yields N citeable items, the prompt must number evidence 1..N and the returned `citations` array must contain those same N items in the same order.
- Strengthen the output guard to reject ANY `[N]` whose `N` is not a valid 1-based index into the returned `citations` array (this should already be the intent of D-198 — make it actually fire for out-of-range indexes, not only for zero-citation answers).
- For the AGGREGATION route, ensure the citations array is populated with the graph evidence actually used so that legitimate aggregation answers (Probe B-type) are NOT falsely blocked.

**Acceptance criteria.**
- Probe B-type query ("how many vendors in total") returns `answered=true` with a non-empty `citations` array and every `[N]` in the answer maps to an existing citation index. (If genuinely no citeable evidence, then `answered=false` is correct — but with the current corpus there IS citeable evidence.)
- Probe C-type query never returns an answer whose `[N]` exceeds the citations array length; an out-of-range ref must force `answered=false` (or be repaired) by the output guard.
- Add unit tests: (1) answer with `[2]` but only 1 citation -> blocked; (2) graph aggregation with N evidence items -> answer cites only `[1..N]` and citations array length == N.

---

## F-04 (Medium) — Entity extraction flaky on relation-dense documents

**Symptom.** The incident report (`phase5-incident-report.md`, dense with relations: incident -> handled by -> team; -> targeting -> department; -> escalated to -> department; -> reviewed by -> CISO) failed ENTITY_EXTRACTION twice, succeeded on the third upload — all on the paid model. DeepSeek returned HTTP 200 each time, but the result failed downstream processing, triggering retry + atomic Qdrant rollback (which worked correctly), ending in `INDEXING_FAILED / ENTITY_EXTRACTION / INDEXING_PIPELINE_ERROR`. A later identical upload succeeded with 10 entities.

**Impact.** Non-deterministic indexing failures on legitimate content. The atomic rollback (D-94/D-95) is solid, but ingestion reliability is poor for relation-heavy text.

**Root cause hypotheses (verify).**
- DeepSeek occasionally returns entities/relations that fail Pydantic schema validation (e.g. a relation `type` outside the allowed enum, or an entity missing a required field), and the single malformed-output retry / response-healing does not always recover.
- The generic wrapper `INDEXING_PIPELINE_ERROR` hides the real exception, so this needs better diagnostic logging to confirm.

**Required fix.**
- Add explicit (non-leaking) logging at the extraction failure point that records the validation error class and which field/enum failed, while still keeping the AMQP failed-event template safe (no raw tracebacks in the event — keep D-02 / StageFailure behavior, but log internally at WARNING/ERROR with enough detail to diagnose).
- Make the extraction schema/healing more tolerant: e.g. drop or coerce out-of-enum relation types instead of failing the whole document; tolerate missing optional fields.
- Optionally add a bounded automatic reindex for `INDEXING_FAILED / ENTITY_EXTRACTION` transient failures (separate from the malformed-output retry).

**Acceptance criteria.**
- Re-uploading the incident report indexes successfully on the first attempt across several runs (no fail-fail-success pattern).
- A unit test feeds a synthesized DeepSeek response with one out-of-enum relation type and asserts the extractor drops/coerces it and still indexes, rather than failing the whole document.
- Failure logs (when they do occur) name the concrete validation cause.

---

## F-05 (Medium) — Default query timeout too small for local hardware

**Symptom.** Default `AI_QUERY_TIMEOUT_SECONDS=30` is too small once real synthesis runs. Factual synthesis alone took ~31 s on this machine (DeepSeek reasoning model). UAT raised it to 120.

**Required fix.**
- Raise the documented LOCAL default (recommend 90 or 120) in `infra/.env.example`, `.env.example`, `ai-service/README.md`, and `infra/docker-compose.yml` default if appropriate.
- Keep configurability. If 30 s is intended for production-grade hardware, document that explicitly and note the local-dev recommended value.
- Consider whether the synthesis step itself should have a sub-timeout so a slow LLM call degrades to a clear "generation timed out" rather than failing the whole route as UNSUPPORTED.

**Acceptance criteria.**
- Out-of-the-box local run (following 05-USER-SETUP.md) does not hit `query_timeout` on a normal factual query on reference local hardware.
- The timeout value and rationale are documented in one place and referenced from the others.

---

## F-06 (Medium) — Graph citation snippet shows `entity:X` instead of document text

**Symptom.** On the GRAPH route, citation `quote`/`snippet` was `entity:CloudSec Inc` (an internal entity marker) rather than human-readable text from the source document. On the HYBRID route the snippet correctly contained document text.

**Impact.** Phase 6 source viewer would show `entity:CloudSec Inc` instead of the actual passage; poor UX and not useful for "open the cited source".

**Required fix.**
- For graph-route citations, resolve each citation to the underlying document chunk text (the child chunk content) and use that as `quote`/`snippet`, consistent with the hybrid route. The graph node/entity marker can remain internal but must not surface as the user-facing snippet.

**Acceptance criteria.**
- A graph-route answer's citations have `quote`/`snippet` containing document text, not `entity:...`.
- Hybrid and graph citations have the same shape and field semantics.

---

## F-07 (Low) — Degraded Qdrant-off does not emit `vector_retrieval_unavailable`

**Symptom.** Scenario 6 stopped Qdrant and ran an AGGREGATION query. It answered correctly via GRAPH, but `degradationWarnings` contained only `reranker_disabled`, not `vector_retrieval_unavailable`. The AGGREGATION route never calls Qdrant, so its outage was neither detected nor reported.

**Impact.** Functionally safe (graph route does not need Qdrant), but does not satisfy D-209 literally — there is no explicit vector-degraded signal when Qdrant is down.

**Required fix (choose one, document the choice).**
- (a) Emit a `vector_retrieval_unavailable` (or `vectorDegraded=true`) signal whenever Qdrant is detected down, regardless of whether the chosen route uses it (e.g. a cheap health probe contributing to retrievalMeta), OR
- (b) Explicitly document that vector-degraded is only reported for routes that use Qdrant (FACTUAL/COMPARISON), and update D-209 wording accordingly so the contract matches behavior.

**Acceptance criteria.**
- Either Scenario 6 emits the vector-degraded warning, or D-209 and 05-UAT.md are updated to state the route-scoped reporting rule and the test asserts the documented behavior.

---

## F-08 (Low) — Orphan Qdrant point + Neo4j Document node after delete/reupload

**Symptom.** After several delete/reupload cycles, Qdrant `points_count=4` and Neo4j `Document` count=4 while only 3 working documents existed. One orphan point and one orphan Document node remained.

**Impact.** Stale vector point / graph node could surface in retrieval for a deleted document (data hygiene + potential access-stale evidence).

**Root cause hypotheses (verify).**
- Delete cleanup (D-22) may not remove the Qdrant point if the failed/partial document never reached a known chunk id, or a rollback path left a point behind.
- Rapid delete-before-fully-indexed races may leave residue.

**Required fix.**
- Audit delete cleanup to ensure Qdrant `delete-by-filter documentId` and Neo4j `MATCH (d:Document {id}) DETACH DELETE d` always run even for documents that failed indexing or were re-uploaded.
- Add a reconciliation/verification step or test that after delete, Qdrant points for that documentId == 0 and the Neo4j Document node is gone.

**Acceptance criteria.**
- A test does upload -> (simulate failure) -> delete -> assert 0 Qdrant points and 0 Neo4j Document nodes for that documentId.
- After a delete/reupload cycle, store counts equal the number of live documents (no orphans).

---

## F-09 (Low/Doc) — ADR-004 and docs still specify `:free`; record paid-tier reality + free-tier limits

**Symptom.** Free-tier `deepseek/deepseek-v4-flash:free` 429-rate-limited indexing under a 3-document burst (multiple retries all 429). UAT switched to paid `deepseek/deepseek-v4-flash`, which resolved it. ADR-004, ARCHITECTURE.md, README, USER_SETUP, and OpenAPI examples still say `:free`.

**Required fix.**
- Update `docs/decisions/ADR-004-llm-provider-deepseek-openrouter.md` to note: free tier is rate-limited for burst indexing; paid `deepseek/deepseek-v4-flash` was used for UAT and is recommended for any multi-document indexing or live query demo; `DEEPSEEK_MODEL_ID` selects between them.
- Note in `05-USER-SETUP.md` that the paid model id is recommended for live UAT and why.
- (Optional) leave code defaults as-is, but make the docs accurate. Decide whether the runtime default should become the paid id; if changed, update config.py default and the three `DEFAULT_DEEPSEEK_MODEL` constants consistently (synthesizer.py, query_router.py, entity_extractor.py) so there is one source of truth.

**Acceptance criteria.**
- Docs no longer imply free tier is sufficient for indexing bursts.
- If the default model id is changed, all four default locations agree, and a query response `modelId` reflects it.

---

## F-10 (Low) — Qdrant client/server version mismatch warning

**Symptom.** Startup warning:
```
Qdrant client version 1.17.1 is incompatible with server version 1.12.6. Major versions should match and minor version difference must not exceed 1.
```
Everything worked, but the mismatch is noise and a latent risk.

**Required fix.**
- Align versions: either pin the `qdrant-client` Python dependency to a 1.12.x compatible with the `qdrant/qdrant:v1.12.6` server image, or bump the server image to match the client's supported range. Prefer matching the client to the deployed server image for stability.

**Acceptance criteria.**
- No version-incompatibility warning on python-ai startup.
- Qdrant query/upsert/delete operations still pass tests.

---

## F-11 (Info/Hardening) — HuggingFace anonymous download throttling; reranker model pre-bake

**Symptom.** Reranker `model.safetensors` (~600 MB) downloaded extremely slowly via anonymous HF (`You are sending unauthenticated requests to the HF Hub`), repeatedly restarting on each query and contributing to timeouts before it was finally cached. bge-m3 was already cached so it loaded instantly.

**Required fix (optional but recommended for reproducible UAT).**
- Support an optional `HF_TOKEN` env var passed into the `python-ai` container to lift anonymous rate limits (document it; do not commit a token).
- Consider pre-baking or pre-warming both models into the `bge-m3-cache` volume during setup (a documented one-time `snapshot_download`/FlagReranker load step) so the first live query is not gated on a 600 MB cold download.
- Document in 05-USER-SETUP.md that the first query after a fresh volume will be slow until both models cache.

**Acceptance criteria.**
- 05-USER-SETUP.md documents the model pre-warm step and optional HF_TOKEN.
- After pre-warm, the first factual query does not spend its budget downloading the reranker.

---

## F-12 (Info) — Misc cleanups observed during UAT

- **CSRF/Origin for unsafe requests.** Java requires an `Origin`/`Referer` header for unsafe cookie-authenticated requests (`ORIGIN_VALIDATION_FAILED`, 403). This is correct behavior. Just ensure Phase 6 frontend always sends Origin, and document it for any API consumer/UAT script.
- **Session expiry mid-UAT.** The admin session JWT expired during the session (401 `AUTHENTICATION_FAILED`) and required re-login. Fine for security; note in UAT docs that long sessions need a re-login step.
- **LangGraph deprecation warning.** `LangChainPendingDeprecationWarning: The default value of allowed_objects will change...` at startup. Harmless now; pass an explicit `allowed_objects` when constructing the serializer to silence and future-proof.
- **`mimeType` stored as `text/plain` for `.md` uploads.** Uploaded markdown showed `mimeType: text/plain` even with `type=text/markdown` in the form. Did not block indexing (Docling/markdown path worked). Verify this is intended (Java MIME sniff) and that it does not affect parser dispatch.
- **Generic `INDEXING_PIPELINE_ERROR`.** The wrapped error code is good for safety but hides cause; see F-04 logging request. Ensure internal logs always carry the concrete stage exception even when the outward code is generic.

---

## Suggested validation after fixes

1. Rebuild `python-ai`, bring up the stack, confirm `/diagnostics` all true.
2. Re-run `uv run --group dev pytest tests` (expect green; new tests for F-01/F-02/F-03/F-04/F-08 added).
3. Re-enable `AI_RERANKER_ENABLED=true`. Re-run Scenario 3 and confirm `rerankerUsed=true`, no degrade warning, within timeout.
4. Re-run Scenario 4 Probe B and Probe C: both `answered=true`, citations array non-empty, every `[N]` maps to a citation; no out-of-range refs accepted.
5. Re-upload the incident report several times: indexes first try each time.
6. Re-run Scenario 6: vector-degraded behavior matches the documented decision (warning emitted or doc updated).
7. Delete + reupload a doc: assert zero orphan Qdrant points / Neo4j Document nodes.
8. Update `05-UAT-EVIDENCE.md` (or a follow-up evidence file) with `rerankerUsed=true` results to close P4 and PH5-UAT-DEF-02/03/04.

## Config state left after UAT (for reference)

`infra/.env` currently holds the working demo configuration:
- `DEEPSEEK_MODEL_ID=deepseek/deepseek-v4-flash` (paid)
- `AI_QUERY_TIMEOUT_SECONDS=120`
- `AI_RERANKER_ENABLED=false` (keep false until F-01 is fixed, otherwise queries time out)

After F-01/F-02 land, set `AI_RERANKER_ENABLED=true` and re-validate.

## Do-not-break list

- bge-m3 dense+sparse embedding behavior (Phase 4) must not regress when changing transformers/FlagEmbedding versions.
- Atomic Qdrant rollback (D-94/D-95) currently works correctly — preserve it.
- Input guard two-layer behavior (prompt_injection / out_of_scope) works correctly — preserve it.
- Access-filter enforcement and no-evidence honest refusal work correctly — preserve them.
- The 202/11 mocked test suite must stay green.
