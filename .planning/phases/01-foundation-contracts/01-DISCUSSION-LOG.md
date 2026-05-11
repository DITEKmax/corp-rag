# Phase 1: Foundation & Contracts - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-05-11
**Phase:** 1-Foundation & Contracts
**Areas discussed:** Contract scope depth, Contract source location, Generated code policy, Foundation scaffold floor

---

## Contract Scope Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Full v1 | Define the entire API/event surface upfront so contract-first works end-to-end. | yes |
| Foundation only | Define only health/auth skeleton and indexing event shells now. | |
| Hybrid | Define all shared schemas now, fully detail only near-term endpoints/events. | |

**User's choice:** Full v1.
**Notes:** Full v1 includes frontend Java OpenAPI, Java-to-Python OpenAPI, and RabbitMQ AsyncAPI. Contracts must be implementation-ready but not prose-heavy. Later breaking changes require ADRs. Completion is proven by lint, codegen, compile/import smoke tests, and generated-model sanity checks.

---

## Contract Source Location

| Option | Description | Selected |
|--------|-------------|----------|
| Top-level `contracts/` | Root shared source of truth, consumed by Java and Python. | yes |
| Inside `backend/corp-rag-contracts` | Java-owned contract source with Python mirror. | |
| Duplicated per service | Service-local contract copies with drift checks. | |

**User's choice:** Top-level `contracts/`.
**Notes:** Java and Python consume root contracts directly. `backend/corp-rag-contracts` and `ai-service/src/corp_rag_ai/contracts/generated/` are generated contract surfaces. `contracts/constants.yaml` supersedes earlier handwritten-constants discussion and generates routing keys, queue names, exchange names, and error codes for both languages.

---

## Generated Code Policy

| Option | Description | Selected |
|--------|-------------|----------|
| Do not commit generated outputs | Commit contract sources and generator scripts only. | yes |
| Commit generated outputs | Check generated Java/Python files into source control. | |
| Commit only release snapshots | Ignore generated outputs normally; commit snapshots at milestones. | |

**User's choice:** Do not commit generated outputs.
**Notes:** Java outputs use Maven `target/generated-sources`; Python outputs use `ai-service/src/corp_rag_ai/contracts/generated/`. `scripts/verify-contracts.py` owns verification logic, with Makefile, PowerShell, and Bash wrappers. Pre-commit hook is optional and documented only.

---

## Foundation Scaffold Floor

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal runnable skeletons | Prove service shape, health endpoints, compose, contracts, migrations. | yes |
| Directories only | Create folders/contracts/generators without runnable services. | |
| Feature-ready skeletons | Include auth/security placeholders and richer app skeletons now. | |

**User's choice:** Minimal runnable skeletons.
**Notes:** Phase 1 proves shape, not behavior. Java/Python/frontend are runnable and healthy; all 9 Compose services reach healthy. Both Java and Python logical databases are created in one Postgres container with empty migration baselines. Python uses Alembic. Langfuse is container-only with no SDK instrumentation yet.

---

## the agent's Discretion

- Choose exact generator implementation details and healthcheck command variants as long as the locked behavior is preserved.
- Keep scaffolding minimal; do not pull Phase 2+ behavior into Phase 1.

## Deferred Ideas

None.
