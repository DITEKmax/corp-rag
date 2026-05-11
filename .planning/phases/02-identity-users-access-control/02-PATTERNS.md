---
phase: 02
slug: identity-users-access-control
created: 2026-05-12
status: complete
---

# Phase 02 - Pattern Map

## Existing Baseline

The Java app is currently a minimal Spring Boot skeleton. There are no existing auth, domain, repository, controller, or security packages to mirror yet. Phase 2 establishes the backend patterns that later Java phases should reuse.

## File Classification

| File or Package | Role | Closest Existing Analog | Pattern to Follow |
|-----------------|------|-------------------------|-------------------|
| `contracts/openapi/api-v1.yaml` | REST contract source | Phase 1 contract baseline in same file | Contract-first additive edits; keep `/api/v1` flat namespace and RFC 7807 responses. |
| `contracts/constants.yaml` | Error-code source | Existing `error_codes` entries | Add symbolic constants before Java uses them; do not hand-write error string literals. |
| `backend/corp-rag-app/src/main/resources/db/migration/V*.sql` | Java DB schema | `V1__baseline.sql` location | One ordered Flyway migration per schema/seed concern; preserve FK order from `02-CONTEXT.md` D-69. |
| `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/**` | REST adapters | `CorpRagApplication.java` package root only | Thin controllers: validate/map DTOs, call services, return generated contract DTOs/ProblemDetail. |
| `backend/corp-rag-app/src/main/java/com/corprag/service/**` | Use-case layer | `docs/PATTERNS.md` service-layer pattern | Business decisions live here, not in controllers or repositories. Constructor injection only. |
| `backend/corp-rag-app/src/main/java/com/corprag/domain/**` | Domain model/value objects | `docs/PATTERNS.md` DTO separation | Use records/enums/value objects; keep generated DTOs out of domain. |
| `backend/corp-rag-app/src/main/java/com/corprag/repository/**` | JDBC persistence | Spring JDBC dependency in `corp-rag-app` | Use `JdbcClient` or `NamedParameterJdbcTemplate`; parameterized queries only. |
| `backend/corp-rag-app/src/main/java/com/corprag/security/**` | Auth/session/access-control | `02-RESEARCH.md` Spring Security section | Spring Security Resource Server JWT support, custom cookie bearer resolver, method security. |
| `backend/corp-rag-app/src/main/java/com/corprag/assembler/**` | Response mapping | `docs/PATTERNS.md` assembler pattern | Convert domain objects to generated DTOs/HATEOAS links; no business rules. |
| `backend/corp-rag-app/src/test/java/com/corprag/**` | Unit/slice/integration tests | `CorpRagApplicationTests.java` | Keep `mvn test` Docker-free; use `*IT` + Testcontainers under `mvn verify`. |

## Shared Patterns

- Contract-first: update `contracts/` before Java implementation.
- Layering: `adapter/rest` -> `service` -> `domain`/`repository`; controllers stay thin.
- Error handling: all REST errors become RFC 7807 ProblemDetail with generated `ErrorCodes`.
- Security: auth and authorization checks belong in Java, not frontend or Python.
- Persistence: PostgreSQL-specific schema is verified with Testcontainers, not H2.
- Events/audit: use durable `audit_events`; do not replace it with logs or an auth-only temp table.

## No Analog Found

These are first-use patterns in this codebase and must be implemented from `02-CONTEXT.md` and `02-RESEARCH.md`:

- `CookieBearerTokenResolver`
- `OriginRefererValidationFilter`
- `JwtService` using `NimbusJwtEncoder`/`NimbusJwtDecoder.withSecretKey`
- `RefreshTokenService` with rotation family reuse detection
- `PasswordPolicyValidator`
- `AccessFilterResolver` and `AccessFilterCacheInvalidator`
- `AuditEventWriter`
