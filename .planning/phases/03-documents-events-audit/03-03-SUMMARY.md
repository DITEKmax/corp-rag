---
phase: "03-documents-events-audit"
plan: "03"
subsystem: "documents"
tags: ["spring-boot", "minio", "tika", "multipart", "outbox", "audit"]

requires:
  - phase: "03-documents-events-audit/03-02"
    provides: "document metadata repository, outbox repository, audit writer, and correlation filter"
provides:
  - "POST /api/v1/documents multipart upload endpoint"
  - "MinIO-backed document source storage with Tika MIME sniffing and SHA-256 hashing"
  - "document.uploaded outbox envelope with correlation headers"
  - "DOCUMENT_UPLOADED success/failure audit coverage"
affects: ["03-04-raw-downloads", "03-05-outbox-publisher", "04-ai-indexing"]

tech-stack:
  added: ["io.minio:minio 8.5.17", "org.apache.tika:tika-core 2.9.2"]
  patterns: ["storage adapter boundary", "prepare-upload then transactional metadata/outbox/audit", "contract ProblemDetails details map"]

key-files:
  created:
    - "backend/corp-rag-app/src/main/java/com/corprag/adapter/storage/DocumentStorageClient.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/adapter/storage/MinioDocumentStorageClient.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/document/DocumentUploadService.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/outbox/OutboxService.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/DocumentController.java"
  modified:
    - "backend/corp-rag-app/pom.xml"
    - "backend/corp-rag-app/src/main/resources/application.yml"
    - "infra/docker-compose.yml"
    - ".env.example"
    - "backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/ProblemDetailsWriter.java"

key-decisions:
  - "MinIO put happens before the database transaction so outbox publication cannot reference a missing object."
  - "Bucket initialization is enabled by docker compose and disabled by default so local unit tests do not require MinIO."
  - "Duplicate upload errors include details.existingDocumentId through ProblemDetails."
  - "If MinIO put succeeds and the later DB transaction fails, the orphan object is accepted for Phase 3 and cleanup is deferred to Phase 7+."

patterns-established:
  - "Upload preparation reads the stream once, computes SHA-256, sniffs MIME with Tika, and generates yyyy/MM/documentId.ext keys."
  - "Document upload writes document metadata, outbox event, and audit row inside one transaction after object storage succeeds."
  - "Outbox event services construct AsyncAPI envelope payloads and AMQP headers before repository JSONB persistence."

requirements-completed: ["DOC-01", "EVT-01", "AUD-01"]

duration: "28 min"
completed: "2026-05-13"
---

# Phase 03 Plan 03 Summary: Document Upload Storage and Events

**MinIO-backed document uploads with Tika validation, transactional metadata/outbox/audit writes, and contract-backed failure responses**

## Performance

- **Duration:** 28 min
- **Started:** 2026-05-13T19:20:53Z
- **Completed:** 2026-05-13T19:48:41Z
- **Tasks:** 3
- **Files modified:** 26

## Accomplishments

- Added bounded 50 MB multipart upload configuration, MinIO Java SDK wiring, Tika Core, and Java MinIO compose/env settings.
- Implemented storage preparation with idempotent bucket initialization, generated object keys, MIME allowlist enforcement, SHA-256 hashing, and presign support for the next plan.
- Implemented `POST /api/v1/documents` with `documents.upload`, access-level cap checks, duplicate detection before MinIO, MinIO-before-DB ordering, transactional document/outbox/audit inserts, and contract ProblemDetails for expected failures.
- Added unit and MVC coverage for permission failures, access-cap failures, duplicates, MIME mismatch audit details, ordering, and `document.uploaded` envelope/header shape.

## Task Commits

1. **Task 1: Add MinIO, Tika, and upload configuration** - `50f503a` (chore)
2. **Task 2: Implement storage adapter, MIME sniffing, hashing, and bucket initialization** - `724c790` (feat)
3. **Task 3: Implement upload service, REST endpoint, outbox row, and audit** - `9d4e047` (feat)

**Plan metadata:** this summary commit

## Files Created/Modified

- `backend/corp-rag-app/src/main/java/com/corprag/config/DocumentStorageProperties.java` - Typed MinIO/upload settings.
- `backend/corp-rag-app/src/main/java/com/corprag/config/DocumentStorageConfig.java` - MinIO client bean.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/storage/*` - Storage boundary, MinIO implementation, exception, and bucket initializer.
- `backend/corp-rag-app/src/main/java/com/corprag/service/document/*` - Upload command, upload service, MIME allowlist, prepared upload, and preparation logic.
- `backend/corp-rag-app/src/main/java/com/corprag/service/outbox/OutboxService.java` - `document.uploaded` envelope and headers.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/DocumentController.java` - Multipart REST endpoint.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/DocumentAssembler.java` - Domain to generated contract document mapping.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/ProblemDetailsWriter.java` - ProblemDetails `details` support.
- `backend/corp-rag-app/src/test/java/com/corprag/service/document/*` - Upload preparation and service behavior tests.
- `backend/corp-rag-app/src/test/java/com/corprag/service/outbox/OutboxServiceTest.java` - AsyncAPI envelope/header coverage.
- `backend/corp-rag-app/src/test/java/com/corprag/adapter/rest/DocumentControllerTest.java` - Upload endpoint MVC/security coverage.

## Decisions Made

- Stored objects are written before the DB transaction starts. This preserves the plan's safety invariant that no outbox row can be published for an object Python cannot fetch.
- Active duplicate checks run before MinIO writes. A partial unique index race is also mapped back to `DUPLICATE_DOCUMENT` when the existing active document can be found.
- Bucket initialization is opt-in with `JAVA_MINIO_INITIALIZE_BUCKET`, enabled by local compose and disabled by default for unit/app-context tests.
- `ApiProblemException` and `ProblemDetailsWriter` now carry structured `details`, used for `details.existingDocumentId`.

## Deviations from Plan

### Auto-fixed Issues

**1. Bucket initialization default guarded for testability**
- **Found during:** Task 2
- **Issue:** The plan required startup bucket initialization, but unconditional initialization would make local unit and context tests contact MinIO.
- **Fix:** Added `app.document-storage.initialize-bucket`; compose enables it while the default remains false.
- **Files modified:** `DocumentStorageBucketInitializer.java`, `DocumentStorageProperties.java`, `application.yml`, `infra/docker-compose.yml`, `.env.example`
- **Verification:** `mvn -q -pl corp-rag-app -am test`
- **Committed in:** `724c790`

**2. Upload service production constructor marked for Spring injection**
- **Found during:** Task 3 verification
- **Issue:** A package-private test constructor made Spring require an explicit injection constructor.
- **Fix:** Added `@Autowired` to the production constructor.
- **Files modified:** `DocumentUploadService.java`
- **Verification:** `mvn -q -pl corp-rag-app -am test`
- **Committed in:** `9d4e047`

---

**Total deviations:** 2 auto-fixed (1 testability guard, 1 Spring injection fix)
**Impact on plan:** No scope expansion. Both changes preserve the planned runtime behavior while keeping tests deterministic.

## Issues Encountered

- `python scripts/verify-contracts.py` could not run directly because the Windows Python launcher reported no installed Python. The same script passed via the repo uv environment: `$env:MAVEN_CMD='C:\dev\apache-maven-3.9.15\bin\mvn.cmd'; uv run --project ai-service python scripts\verify-contracts.py`.
- Maven test output still logs Docker/Testcontainers discovery errors for Docker-disabled integration tests, but the suite exits successfully.
- Known limitation from the plan: if MinIO `putObject` succeeds and the later metadata/outbox/audit transaction fails, the object remains orphaned. Cleanup is deferred to a Phase 7+ housekeeping job.

## Verification

- **Passed:** `$env:MAVEN_CMD='C:\dev\apache-maven-3.9.15\bin\mvn.cmd'; uv run --project ai-service python scripts\verify-contracts.py`
- **Passed:** `C:\dev\apache-maven-3.9.15\bin\mvn.cmd --% -q -pl corp-rag-app -am test`

## User Setup Required

None - local compose and `.env.example` were updated with Java MinIO settings.

## Next Phase Readiness

- Plan 03-04 can use `DocumentStorageClient.presignedGetObjectUrl` and the stored bucket/key metadata for raw file access.
- Plan 03-05 can publish persisted `document.uploaded` rows with AsyncAPI-compatible payload and headers.
- Phase 4 indexing can consume `minioBucket`, `minioObjectKey`, access metadata, language, and SHA-256 from the outbox event.

---
*Phase: 03-documents-events-audit*
*Completed: 2026-05-13*
