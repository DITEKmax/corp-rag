---
phase: 08-delivery-polish-demo-readiness
plan: "05"
subsystem: polish-traceability
tags: [raw-view, utf-8, traceability, known-limitations, waiver]

requires:
  - phase: 08-delivery-polish-demo-readiness
    provides: Seeded 16-document demo corpus and running compose stack
provides:
  - Narrow UTF-8 raw-view path for text documents through MinIO presigned URL response content type
  - Corrected RET/AGT requirement traceability while DEL-01 remains pending
  - Explicit Phase 8 known limitations and stretch-work boundaries
affects: [document-raw-url, demo-polish, requirements, backlog]

tech-stack:
  added: []
  patterns:
    - Presigned URL response header override instead of Java byte proxy
    - Documentation waiver for known eval limitations without changing guard/router/retrieval code

key-files:
  created:
    - .planning/phases/08-delivery-polish-demo-readiness/08-KNOWN-LIMITATIONS.md
    - .planning/phases/08-delivery-polish-demo-readiness/08-05-SUMMARY.md
  modified:
    - backend/corp-rag-app/src/main/java/com/corprag/adapter/storage/DocumentStorageClient.java
    - backend/corp-rag-app/src/main/java/com/corprag/adapter/storage/MinioDocumentStorageClient.java
    - backend/corp-rag-app/src/main/java/com/corprag/service/document/DocumentRawUrlService.java
    - backend/corp-rag-app/src/test/java/com/corprag/adapter/storage/MinioDocumentStorageClientTest.java
    - backend/corp-rag-app/src/test/java/com/corprag/service/document/DocumentRawUrlServiceTest.java
    - .planning/REQUIREMENTS.md
    - .planning/BACKLOG.md

key-decisions:
  - "Raw-view polish uses MinIO `response-content-type` on presigned URLs for text/plain, text/markdown, .txt, and .md/.markdown documents."
  - "Non-text raw URLs keep the existing presign path."
  - "RET-01, RET-02, RET-03, AGT-01, and AGT-02 are marked Complete as implemented Phase 5 behavior; DEL-01 remains Pending until final Phase 8 closeout."
  - "Multi-hop records `ru-multihop-002/003/005/006` are waived for Phase 8 demo readiness and remain future retrieval work."

requirements-progressed: ["DEL-01"]

duration: 1h
completed: 2026-06-02
---

# Phase 08 Plan 05: Polish And Traceability Summary

**Delivery polish closed the raw UTF-8 browser-view issue and made Phase 8 limitations explicit without changing RAG guard, citation, access, router, or graph-retrieval semantics.**

## Accomplishments

- Added a narrow raw URL content-type override path: Java still checks document visibility first, then MinIO signs a URL with `response-content-type` for text raw views.
- Covered text and non-text raw URL behavior in unit tests, including `.txt`, `.md`, and PDF cases.
- Marked implemented Phase 5 RET/AGT requirements as Complete in `.planning/REQUIREMENTS.md`; `DEL-01` remains Pending.
- Created `08-KNOWN-LIMITATIONS.md` documenting the Phase 8 multi-hop waiver, safe `refused_no_evidence`, data-exfiltration guard classification as non-attempted stretch, and `ru-factual-009` as future router/retrieval quality work.
- Updated backlog state for BL-UAT-01 closure and kept multi-hop/data-exfil/router debt visible as future work.

## Verification

- `C:\dev\apache-maven-3.9.15\bin\mvn.cmd --% -q -f backend/pom.xml -pl corp-rag-app -am -Dtest=DocumentRawUrlServiceTest,MinioDocumentStorageClientTest -Dsurefire.failIfNoSpecifiedTests=false test` - passed.
- `python -c "... REQUIREMENTS traceability assertions ..."` - passed.
- `python -c "... 08-KNOWN-LIMITATIONS required text assertions ..."` - passed.
- `C:\dev\apache-maven-3.9.15\bin\mvn.cmd --% -q -pl corp-rag-app -am test` from `backend/` - passed.
- `docker compose --env-file infra\.env -f infra\docker-compose.yml up -d --build java-backend` - rebuilt and restarted Java backend without deleting volumes.
- `python scripts/check_demo_stack.py --compose-file infra/docker-compose.yml --env-file infra/.env` - `services_healthy=9/9`.
- Live raw URL check through the rebuilt Java container - `raw_url_has_utf8_response_content_type=true`.

## Guardrails

- No output guard, citation validation, access filter, weak-evidence threshold, refusal behavior, router, Cypher, graph retrieval, golden corpus, frozen corpus, reference answer, or UUID expectation was changed.
- No Java byte proxy was added for raw documents.
- No Docker volumes were deleted and no manual backing-store cleanup was performed.

## Deviations From Plan

None. Docker-side verification was added after the unit/doc checks to satisfy Phase 8 verification boundaries.

## User Setup Required

None for committed artifacts. Live raw URL checks require the local seeded stack and ignored `infra/.env` credentials.

## Next Phase Readiness

Phase 8 Wave 1 is complete. Wave 2/3 can proceed with 08-03 regression and 08-04 demo assets; they were not started in this iteration.

---
*Phase: 08-delivery-polish-demo-readiness*
*Completed: 2026-06-02*
