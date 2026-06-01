---
phase: 08
slug: delivery-polish-demo-readiness
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-01
---

# Phase 08 - Validation Strategy

Per-phase validation contract for feedback sampling during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest for ai-service eval tooling; Maven/JUnit for Java polish; node syntax checks for frontend JS; Docker Compose live evidence |
| **Config file** | `ai-service/pyproject.toml`, `backend/pom.xml`, `infra/docker-compose.yml` |
| **Quick run command** | `uv run --project ai-service --group dev pytest ai-service/tests/test_eval_seed_corpus.py ai-service/tests/test_eval_final_regression.py` |
| **Full suite command** | Compose health, seed reset, chat/citation proof, and one RAGAS/eval run |
| **Estimated runtime** | Focused tests under a few minutes; live eval depends on model warm state and judge calls |

## Sampling Rate

- **After every task commit:** run the focused automated command named in the plan task.
- **After every wave:** run all focused tests for that wave and `docker compose --env-file infra/.env -f infra/docker-compose.yml ps` when live stack behavior is affected.
- **Before `$gsd-verify-work`:** compose health, seed reset, chat/citation proof, RAGAS/eval evidence, and demo docs must be present or explicitly blocked.
- **Max feedback latency:** focused code tests should stay under 120 seconds; live Docker/eval checks are wave-gated.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | DEL-01 | Seed client authenticates to Java and never mutates stores directly. | unit | `uv run --project ai-service --group dev pytest ai-service/tests/test_eval_seed_corpus.py` | planned | pending |
| 08-01-02 | 01 | 1 | DEL-01 | Reset deletes prior seed docs through Java before upload. | unit + live | `uv run --project ai-service python eval/seed_corpus.py --help` | planned | pending |
| 08-01-03 | 01 | 1 | DEL-01 | Corpus verification reports Java/Qdrant/Neo4j mismatches without hiding failures. | unit + live | `uv run --project ai-service --group dev pytest ai-service/tests/test_eval_seed_corpus.py` | planned | pending |
| 08-02-01 | 02 | 1 | DEL-01 | Stack checker records service health without secrets. | unit + live | `python scripts/check_demo_stack.py --help` | planned | pending |
| 08-02-02 | 02 | 1 | DEL-01 | Runbook documents memory and env setup without committing secret values. | docs | docs grep/link check | planned | pending |
| 08-02-03 | 02 | 1 | DEL-01 | Compose evidence captures 9/9 health and diagnostics. | live | `docker compose --env-file infra/.env -f infra/docker-compose.yml ps` | existing | pending |
| 08-05-01 | 05 | 1 | DEL-01 | Raw UTF-8 polish does not proxy bytes or weaken document access. | unit | backend focused tests | planned | pending |
| 08-05-02 | 05 | 1 | DEL-01 | Requirements traceability reflects implemented behavior without hiding multi-hop limitation. | docs | requirements grep/check script | existing | pending |
| 08-05-03 | 05 | 1 | DEL-01 | Stretch guard/router work is explicitly not attempted unless separately opened. | docs | known-limitation grep | planned | pending |
| 08-03-01 | 03 | 2 | DEL-01 | Final regression runner uses Java chat API and preserves citations/guard outcomes. | unit | `uv run --project ai-service --group dev pytest ai-service/tests/test_eval_final_regression.py` | planned | pending |
| 08-03-02 | 03 | 2 | DEL-01 | Live evidence chain records compose, seed, chat/citation, diagnostics, and eval. | live | final regression command | planned | pending |
| 08-03-03 | 03 | 2 | DEL-01 | Generated RAGAS reports are not committed before review. | checkpoint | human review checkpoint | planned | pending |
| 08-04-01 | 04 | 3 | DEL-01 | README and diagram reflect actual Java/Python/frontend boundaries. | docs | markdown grep/link check | planned | pending |
| 08-04-02 | 04 | 3 | DEL-01 | Demo script includes factual, trace, latency, injection/refusal, and known-limit scenes. | docs | demo asset grep | planned | pending |
| 08-04-03 | 04 | 3 | DEL-01 | Short video is recorded or explicitly marked ready with review checklist. | checkpoint | human review checkpoint | planned | pending |

## Wave 0 Requirements

Existing infrastructure covers the phase:

- Java/Maven, Python/pytest, frontend/node checks, Docker Compose, and eval runners already exist.
- Missing focused test files and helper scripts are created by Wave 1 plans before later live evidence depends on them.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Stochastic final RAGAS report acceptance | DEL-01 | Judge-backed metrics can vary and should be reviewed before commit. | Review report summary and approve commit or record blocker. |
| Short video capture | DEL-01 | Audio/screen recording is a review artifact outside normal code automation. | Use the generated script/checklist; record or waive explicitly. |

## Validation Sign-Off

- [x] All tasks have automated verify or a documented checkpoint.
- [x] Sampling continuity: no 3 consecutive implementation tasks without automated verify.
- [x] Wave 0 covers all missing test/script references.
- [x] No watch-mode flags.
- [x] Feedback latency target documented.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** planned 2026-06-01
