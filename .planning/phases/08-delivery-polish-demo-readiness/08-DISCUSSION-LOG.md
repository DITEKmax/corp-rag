# Phase 8: Delivery Polish & Demo Readiness - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-06-01
**Phase:** 8-Delivery Polish & Demo Readiness
**Areas discussed:** Seed reset strategy, final regression scope, opportunistic polish priority, locked boundaries

---

## Seed Reset Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Idempotent reset | Script brings demo corpus to exactly 16 documents through delete + upload and waits for indexing. | yes |
| Append only | Script uploads only missing documents and leaves existing data untouched. | |
| Verify only | Script only checks an already-loaded corpus. | |

**User's choice:** Idempotent reset.

**Notes:** The user emphasized that reproducibility is the point of the phase. Append-only would accumulate duplicates across repeated demos and distort RAGAS/context/citation metrics. Verify-only fails on a clean laptop where the corpus may not exist. Reset must use Java delete and upload APIs so normal Qdrant/Neo4j cleanup paths run. It must not use manual volume cleanup or `docker compose down -v`. Backlog F-08 means verification must check Qdrant point and Neo4j node counters, not only Java document count.

---

## Final Regression Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Core path + eval | Verify 9/9 healthy, seed/index, chat-to-citation, and one RAGAS/eval run. | yes |
| Smoke only | Verify health and one factual chat only. | |
| Full evidence replay | Re-run RAGAS, ablation, injection, and Langfuse evidence. | |

**User's choice:** Core path + eval.

**Notes:** Smoke-only does not prove the success criterion that the core chat/citation/evaluation path still works. Full replay is excessive and risky on the local memory budget because Phase 7 artifacts already provide ablation, injection, and Langfuse evidence. The required eval run must use the known safeguards: `--ragas-max-retries 1`, `--ragas-max-wait 5`, `concurrency=1`, and monitor `reranker_degraded_count=0`. RAGAS remains report-only evidence, not a hard CI gate.

---

## Opportunistic Polish Priority

| Option | Description | Selected |
|--------|-------------|----------|
| Guard exfiltration | Explicitly classify data-exfiltration as guard refusal. | stretch |
| Router factual | Fix `ru-factual-009` false `UNSUPPORTED` without training or golden tuning. | low priority |
| UI/doc polish | Address charset mojibake, documentTitle polish, and REQUIREMENTS traceability. | yes |

**User's choice:** UI/doc polish first, data-exfiltration guard classification as stretch, router factual last.

**Notes:** The user rejected making guard exfiltration the first priority because it changes guard logic late in the project. Current data-exfiltration probes are resisted 100% through no-evidence/unsupported behavior, so this can be explained as defense-in-depth. UI/doc polish is low-risk and useful for the defense: charset mojibake, document titles through seed metadata, and REQUIREMENTS traceability for `RET-01`, `RET-02`, `RET-03`, `AGT-01`, and `AGT-02`. Guard exfiltration may be attempted only as a narrow Docker-verified commit, and any regression in the 12 injection probes means backing out. `ru-factual-009` should be attempted only if the fix is a general localization/routing rule, not a golden-record patch.

---

## Locked Boundaries

| Topic | Decision |
|-------|----------|
| Multi-hop graph retrieval | Waived for Phase 8; document as known limitation with safe `refused_no_evidence`. |
| Production compose | Do not create. Use single `infra/docker-compose.yml`. |
| Demo assets | Full set required: README, architecture diagram, and short video. |
| Compose success criterion | Reword as 9/9 healthy from the single local compose file, no new deployment file. |

**User's choice:** Keep all prior planning decisions locked and do not reopen them.

**Notes:** The user explicitly asked not to relitigate the Phase 7 handoff decisions. The planner must not convert the original ROADMAP phrase "production-like compose" into a new compose file or deployment scope.

---

## the agent's Discretion

- Choose exact seed script language and location, provided it is easy to run locally and documented.
- Choose polling/timeout details for indexing wait.
- Choose factual demo questions and final evidence filenames.
- Choose exact diagram format.

## Deferred Ideas

- Full text-conditioned multi-hop graph retrieval and graph path ranking.
- New production deployment/compose topology.
- Full Phase 7 evidence replay as a mandatory Phase 8 gate.
- Router training or golden-specific route tuning.
