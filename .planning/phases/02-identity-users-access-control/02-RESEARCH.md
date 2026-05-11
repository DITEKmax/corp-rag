# Phase 2 Research Notes: Identity, Users & Access Control

Date: 2026-05-12
Status: research complete, refreshed for Nyquist validation gate

## Guardrails

- Decisions D-01..D-71 in `02-CONTEXT.md` are treated as fixed inputs.
- This research supplements those decisions and does not revise them.
- Any decision pressure found during research is listed explicitly in
  "Decision pressure / conflicts" below.
- Out of scope: OAuth2/OIDC external providers, SAML/LDAP, 2FA/MFA, WebFlux,
  Spring Authorization Server.

## Local stack fit

- Java 21.
- Spring Boot BOM: 3.3.6.
- Spring Framework managed by Boot 3.3.6: 6.1.15.
- Spring Security managed by Boot 3.3.6: 6.3.5.
- Testcontainers managed by Boot 3.3.6: 1.19.8.
- App is servlet Spring MVC with JDBC, Flyway, PostgreSQL runtime, and current
  H2-based smoke test.

## JWT and cookie auth pattern for Spring Security 6.x

Use Spring Security Resource Server JWT support for request authentication, but
keep token issuing inside the application. The "OAuth2" package name is
unfortunate here; this does not require external OAuth2/OIDC providers or
Spring Authorization Server.

Recommended dependencies:

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-security</artifactId>
</dependency>
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-oauth2-resource-server</artifactId>
</dependency>
<dependency>
    <groupId>org.springframework.security</groupId>
    <artifactId>spring-security-test</artifactId>
    <scope>test</scope>
</dependency>
```

Key classes and patterns:

- `SecurityFilterChain` plus `HttpSecurity`.
- `SessionCreationPolicy.STATELESS`.
- `oauth2ResourceServer(oauth2 -> oauth2.jwt(...))` for access-token
  validation.
- `JwtDecoder`, preferably `NimbusJwtDecoder.withSecretKey(...)` or
  `NimbusJwtDecoder.withPublicKey(...)` for self-issued tokens.
- `JwtEncoder` with `NimbusJwtEncoder` for minting access JWTs.
- `JwtClaimsSet`, `JwsHeader`, `JwtEncoderParameters`.
- `JwtAuthenticationConverter` with a custom authority converter so permissions
  remain exact dotted values such as `users.read`, not `ROLE_*`.
- `BearerTokenResolver` customized to read `corp_rag_session` from an
  httpOnly cookie. `DefaultBearerTokenResolver` is header/form/query oriented
  and is not enough for the locked cookie decision.
- `AuthenticationEntryPoint` and `AccessDeniedHandler` mapped to the contract
  error format.
- `PasswordEncoder` / `BCryptPasswordEncoder` for password hashing.
- A custom servlet filter, likely `OncePerRequestFilter`, for Origin/Referer
  validation on unsafe browser requests when using httpOnly auth cookies.

High-level flow:

1. `POST /api/v1/auth/login` authenticates username/password through an
   application service, issues a 15 minute access JWT and a persisted opaque
   refresh token, and writes both as `ResponseCookie` cookies.
2. Protected `/api/v1/**` requests authenticate via Resource Server JWT
   validation, with a custom `BearerTokenResolver` extracting the access token
   from `corp_rag_session`.
3. `POST /api/v1/auth/refresh` validates and rotates the opaque refresh token
   from `corp_rag_refresh`, then writes replacement cookies.
4. `POST /api/v1/auth/logout` revokes the refresh-token family/session records
   and clears cookies using the same cookie paths as issuance.

## JWT library choice

Choose `spring-boot-starter-oauth2-resource-server` under the existing Spring
Boot 3.3.6 BOM.

Concrete versions with the current BOM:

- `spring-boot-starter-oauth2-resource-server`: 3.3.6, no explicit version in
  module POM.
- `spring-security-oauth2-resource-server`: 6.3.5 via Boot BOM.
- `spring-security-oauth2-jose`: 6.3.5 via Boot BOM.
- `com.nimbusds:nimbus-jose-jwt`: 9.37.3 transitively through
  `spring-security-oauth2-jose` 6.3.5.

Rationale:

- Spring Security already wraps Nimbus through `JwtDecoder`, `JwtEncoder`,
  `JwtValidator`, and authentication conversion APIs that integrate with
  `SecurityFilterChain`.
- Direct `com.nimbusds:nimbus-jose-jwt` 10.9 is current on Maven Central, but it
  would move validation, authority mapping, and security filter integration into
  application code. That adds implementation surface without a Phase 2 need.
- Direct Nimbus should only be added later if we need a JOSE feature not exposed
  by Spring Security's JWT APIs.

Important version caveat:

- Spring Security advisory CVE-2026-22748 affects 6.3.0 through 6.3.14 when
  developers use `NimbusJwtDecoder.withIssuerLocation(...)` and forget explicit
  issuer validation. Because Boot 3.3.6 manages Spring Security 6.3.5, avoid
  `withIssuerLocation` for this phase. For self-issued tokens, configure
  `NimbusJwtDecoder.withSecretKey(...)` or `withPublicKey(...)` and explicit
  validators. If the plan wants issuer discovery, route that through
  discuss-phase first because it implies a dependency/security decision.

## Refresh token rotation practices

The locked decisions already match current guidance: short-lived access JWTs,
persisted refresh tokens, rotation, reuse detection, logout revocation, and
active-session limits.

Implementation pattern:

- Use an opaque high-entropy refresh token, not a JWT refresh token.
- Store only a server-side digest/verifier, never the raw refresh token.
- Use a token family identifier so reuse can revoke the active successor chain.
- Use a single database transaction for refresh:
  1. Read the presented token row by digest and lock it.
  2. Reject expired, revoked, or already rotated tokens.
  3. Insert successor token.
  4. Mark the presented token rotated/revoked.
  5. Write audit event and update `last_used_at`.
- On reuse of a rotated/revoked token, revoke the token family and write a
  security audit event. The server cannot reliably know whether the attacker or
  legitimate client presented the reused token, so the safe action is to force a
  fresh login.

Suggested table fields:

- `id`
- `user_id`
- `token_hash`
- `family_id`
- `parent_token_id`
- `issued_at`
- `expires_at`
- `last_used_at`
- `rotated_at`
- `revoked_at`
- `revoked_reason`
- `user_agent_hash`
- `ip_hash`

## ResponseCookie usage

Use `org.springframework.http.ResponseCookie` from Spring Framework 6.1.x.

```java
ResponseCookie accessCookie = ResponseCookie.from("corp_rag_session", accessToken)
        .httpOnly(true)
        .secure(cookieProperties.secure())
        .sameSite("Strict")
        .path("/api/v1")
        .maxAge(Duration.ofMinutes(15))
        .build();

ResponseCookie refreshCookie = ResponseCookie.from("corp_rag_refresh", refreshToken)
        .httpOnly(true)
        .secure(cookieProperties.secure())
        .sameSite("Strict")
        .path("/api/v1/auth")
        .maxAge(Duration.ofDays(7))
        .build();
```

Cookie deletion must use the same names and paths:

```java
ResponseCookie deleteAccess = ResponseCookie.from("corp_rag_session", "")
        .httpOnly(true)
        .secure(cookieProperties.secure())
        .sameSite("Strict")
        .path("/api/v1")
        .maxAge(Duration.ZERO)
        .build();
```

## CSRF with SameSite=Strict and httpOnly cookies

Spring Security's CSRF docs treat SameSite as useful but not a complete
replacement for CSRF tokens. They also call out that stateless browser apps are
still vulnerable when the browser automatically attaches a custom auth cookie.

Because D-10/D-11 lock SameSite Strict, Origin/Referer validation, and no
frontend-readable CSRF cookie, the implementation should be explicit:

- Do not use `csrf(AbstractHttpConfigurer::disable)` globally.
- Keep CSRF enabled for any future non-API form/session surface.
- For `/api/v1/**`, either:
  - use Spring's CSRF token machinery if the decision is reopened, or
  - intentionally configure API CSRF ignoring together with a mandatory
    `OriginRefererValidationFilter` for unsafe methods.
- The Origin/Referer guard should apply to all unsafe methods that can be
  authenticated by httpOnly cookies, not just login and refresh. Unsafe means
  anything outside GET, HEAD, OPTIONS, TRACE.
- Require JSON content type on JSON mutation endpoints.

Possible config shape:

```java
@Bean
SecurityFilterChain securityFilterChain(HttpSecurity http,
        OriginRefererValidationFilter originRefererValidationFilter,
        BearerTokenResolver cookieBearerTokenResolver) throws Exception {
    http
            .sessionManagement(session -> session
                    .sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .csrf(csrf -> csrf
                    .ignoringRequestMatchers(new AntPathRequestMatcher("/api/v1/**")))
            .addFilterBefore(originRefererValidationFilter, CsrfFilter.class)
            .oauth2ResourceServer(oauth2 -> oauth2
                    .bearerTokenResolver(cookieBearerTokenResolver)
                    .jwt(Customizer.withDefaults()));
    return http.build();
}
```

This is acceptable only if documented as the custom CSRF defense required by
D-10/D-11, not as "CSRF is irrelevant because JWT is stateless".

## Method security: @PreAuthorize vs PermissionEvaluator

Use `@EnableMethodSecurity` and `@PreAuthorize` for Phase 2.

Recommended split:

- Use simple authority checks for static permissions:
  `@PreAuthorize("hasAuthority('users.read')")`.
- Use a bean-based authorization service for conditional checks:
  `@PreAuthorize("@userAuthz.canReadUser(authentication, #userId)")`.
- Avoid a custom `PermissionEvaluator` at the start unless the domain needs
  object-style `hasPermission(target, permission)` checks across many object
  types.
- Avoid complex SpEL that repeats role/permission logic inline. Seed roles so
  admins receive the relevant authorities, then keep annotations simple.

Spring Security 6 method security uses `AuthorizationManager` internals under
`@EnableMethodSecurity`, and `@PreAuthorize` supports direct bean calls. That
fits the contract-first `x-required-permissions` model without adding an ACL
subsystem.

## ETag and If-Match in Spring MVC

Use optimistic version columns for mutable role/access-policy resources.

Pattern:

- Add `version BIGINT NOT NULL DEFAULT 0` to versioned tables.
- Represent ETags as quoted versions, for example `"role-12-v3"` or `"v3"`.
- GET returns `ETag` using `ResponseEntity.ok().eTag(etag).body(dto)`.
- PUT/PATCH/DELETE requires `If-Match`:
  - missing header: return 428 Precondition Required using contract error body,
  - stale/mismatched value: return 412 Precondition Failed,
  - successful update: increment version and return the new ETag.
- Use `HttpHeaders.IF_MATCH` for the request header constant.

Controller shape:

```java
@PutMapping("/api/v1/roles/{roleId}")
ResponseEntity<RoleResponse> updateRole(
        @PathVariable UUID roleId,
        @RequestHeader(HttpHeaders.IF_MATCH) String ifMatch,
        @Valid @RequestBody UpdateRoleRequest request) {
    RoleResponse updated = roleService.update(roleId, request, ETags.parse(ifMatch));
    return ResponseEntity.ok()
            .eTag(ETags.role(updated.id(), updated.version()))
            .body(updated);
}
```

## Testcontainers PostgreSQL integration

Add Testcontainers dependencies to `backend/corp-rag-app/pom.xml` without
explicit versions because the existing backend parent imports the Spring Boot
3.3.6 BOM.

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-testcontainers</artifactId>
    <scope>test</scope>
</dependency>
<dependency>
    <groupId>org.testcontainers</groupId>
    <artifactId>junit-jupiter</artifactId>
    <scope>test</scope>
</dependency>
<dependency>
    <groupId>org.testcontainers</groupId>
    <artifactId>postgresql</artifactId>
    <scope>test</scope>
</dependency>
```

If Docker-backed tests should run only on `mvn verify`, add Failsafe in
`backend/pom.xml` plugin management and bind integration tests named `*IT`.

```xml
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-failsafe-plugin</artifactId>
    <version>${maven-surefire.version}</version>
    <executions>
        <execution>
            <goals>
                <goal>integration-test</goal>
                <goal>verify</goal>
            </goals>
        </execution>
    </executions>
</plugin>
```

Test class shape:

```java
@Testcontainers
@SpringBootTest
@AutoConfigureMockMvc
class AuthFlowIT {

    @Container
    @ServiceConnection
    static PostgreSQLContainer<?> postgres =
            new PostgreSQLContainer<>(DockerImageName.parse("postgres:16-alpine"));
}
```

Important imports:

- `org.springframework.boot.testcontainers.service.connection.ServiceConnection`
- `org.testcontainers.containers.PostgreSQLContainer`
- `org.testcontainers.junit.jupiter.Container`
- `org.testcontainers.junit.jupiter.Testcontainers`
- `org.testcontainers.utility.DockerImageName`

Planner implication:

- Keep fast unit/slice tests Docker-free under Surefire and `mvn test`.
- Put Postgres/Flyway/auth flow integration tests under Failsafe and `mvn verify`.
- Replace or demote the current H2 `@SpringBootTest` because Phase 2 schema and
  auth behavior depend on PostgreSQL/Flyway semantics.

## Decision pressure / conflicts

No hard conflict was found that requires silently changing D-01..D-71.

Items to review before planning:

1. CSRF coverage pressure: Spring guidance recommends CSRF protection for any
   browser-processable unsafe request, and SameSite is defense-in-depth. If
   D-10/D-11 are interpreted as Origin/Referer checks only on auth endpoints,
   that under-covers cookie-authenticated mutation endpoints. Recommended plan
   input: apply Origin/Referer validation to all unsafe `/api/v1/**` cookie
   requests, or reopen through discuss-phase if a Spring CSRF-token design is
   desired.
2. Spring Security 6.3.5 advisory pressure: Boot 3.3.6 manages a Spring Security
   version affected by CVE-2026-22748 for `withIssuerLocation`. Recommended plan
   input: do not use `withIssuerLocation`; use explicit self-issued-token
   decoder configuration. If issuer discovery is desired, discuss dependency
   upgrade or validator requirements first.
3. H2 test pressure: current app has an H2-backed Spring Boot smoke test, while
   D-71 requires Testcontainers PostgreSQL for integration coverage. Recommended
   plan input: keep H2 only for lightweight non-schema tests, otherwise migrate
   integration tests to PostgreSQL containers under `mvn verify`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Login, refresh, logout, current profile, password change | Java backend | PostgreSQL | Browser auth state is cookie-based; Java owns credentials, JWT issuing, refresh-token persistence, and ProblemDetail failures. |
| User, role, permission, and access-policy administration | Java backend | PostgreSQL | These are enterprise access-control workflows and must not move into frontend or Python. |
| Access-filter resolution for retrieval | Java backend | Python AI service | Java computes `AccessFilter` from roles and policies; Python only applies the filter passed in `QueryRequest.accessFilter`. |
| Audit event recording | Java backend | PostgreSQL | Phase 2 writes durable AUTH, ROLE, and ACCESS_POLICY audit rows in the Java-owned database. |
| Contract deltas and generated DTO/constants | Root contracts + backend contract module | Java backend | Contract-first changes start in `contracts/`, then Java generated surfaces compile against them. |
| Validation and regression evidence | Maven test layers | Docker/Testcontainers for full suite | Unit and slice tests stay Docker-free; PostgreSQL-specific behavior uses Testcontainers under `mvn verify`. |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Java 21 | backend compile/test | assumed from Phase 1 build | project property `java.version=21` | none |
| Maven | backend compile/test | available through local approved Maven command path | 3.9.x approved in runner config | none |
| Docker | Testcontainers integration tests and compose | available in Phase 1 verification context | local Docker daemon | keep unit/slice tests under `mvn test`; run integration tests only in `mvn verify` |
| PostgreSQL 16 | Java integration tests | available through compose/Testcontainers image | `postgres:16-alpine` target | no H2 fallback for schema-specific tests |

Missing dependencies with no fallback:
- None for planning. Execution must still verify Docker before running Testcontainers integration tests.

Missing dependencies with fallback:
- If Docker is unavailable during a quick task, run unit/slice tests through `mvn test` and defer Testcontainers-only checks to the wave/phase gate.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | JUnit Jupiter, Spring Boot Test, Spring Security Test, Maven Surefire, Maven Failsafe, Testcontainers PostgreSQL |
| Config file | `backend/pom.xml`, `backend/corp-rag-app/pom.xml` |
| Quick run command | `cd backend; mvn -q -pl corp-rag-app -am test` |
| Full suite command | `cd backend; mvn -q -pl corp-rag-app -am verify` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| AUTH-01 | User can log in, call `/me`, refresh, change password when required, and log out with httpOnly cookies. | unit + slice + integration | `cd backend; mvn -q -pl corp-rag-app -am test` and `cd backend; mvn -q -pl corp-rag-app -am verify` | Wave 0 |
| AUTH-02 | Admin can create users and roles, assign/remove memberships, reset passwords, and manage access policies. | slice + integration | `cd backend; mvn -q -pl corp-rag-app -am test` and `cd backend; mvn -q -pl corp-rag-app -am verify` | Wave 0 |
| AUTH-03 | Protected endpoints reject unauthenticated users, insufficient permissions, bad Origin/Referer, self-modification, and last-admin-breaking changes. | unit + slice + security integration | `cd backend; mvn -q -pl corp-rag-app -am test` and `cd backend; mvn -q -pl corp-rag-app -am verify` | Wave 0 |
| AUTH-04 | Java resolves a user's effective `AccessFilter`, caches it for 60 seconds, evicts it on role/policy/user mutations, and passes it to downstream query requests. | unit + integration | `cd backend; mvn -q -pl corp-rag-app -am test` and `cd backend; mvn -q -pl corp-rag-app -am verify` | Wave 0 |

### Sampling Rate

- Per task commit: `cd backend; mvn -q -pl corp-rag-app -am test`
- Per wave merge: `cd backend; mvn -q -pl corp-rag-app -am verify`
- Phase gate: full suite green before `$gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/corp-rag-app/src/test/java/com/corprag/security/PasswordPolicyValidatorTest.java` covers AUTH-01 password policy and `must_change_password` constraints.
- [ ] `backend/corp-rag-app/src/test/java/com/corprag/security/JwtServiceTest.java` covers AUTH-01 JWT issue/verify claims and expiry.
- [ ] `backend/corp-rag-app/src/test/java/com/corprag/security/AccessFilterResolverTest.java` covers AUTH-04 effective policy union, PUBLIC visibility, empty role fail-safe, and cache eviction triggers.
- [ ] `backend/corp-rag-app/src/test/java/com/corprag/security/RolePermissionMatrixTest.java` covers AUTH-02/AUTH-03 seeded role permission matrix and dotted wire values.
- [ ] `backend/corp-rag-app/src/test/java/com/corprag/adapter/rest/AuthControllerTest.java` covers AUTH-01 login, `/me`, refresh, logout, password change, cookie flags, and ProblemDetail errors.
- [ ] `backend/corp-rag-app/src/test/java/com/corprag/adapter/rest/UserRoleAccessPolicyControllerTest.java` covers AUTH-02 and AUTH-03 admin endpoints, ETag/If-Match, self-vs-other access, self-modification block, and last-admin protections.
- [ ] `backend/corp-rag-app/src/test/java/com/corprag/AuthFlowIT.java` covers AUTH-01/AUTH-03 end-to-end auth flow against PostgreSQL with Testcontainers.
- [ ] `backend/corp-rag-app/src/test/java/com/corprag/AuthSchemaIT.java` covers Flyway migration shape, seeds, constraints, refresh-token rotation fields, and audit indexes against PostgreSQL.
- [ ] Add Maven test dependencies: `spring-boot-starter-security`, `spring-boot-starter-oauth2-resource-server`, `spring-security-test`, `spring-boot-testcontainers`, `org.testcontainers:junit-jupiter`, and `org.testcontainers:postgresql`.
- [ ] Add Maven Failsafe binding so `mvn test` remains fast and `mvn verify` runs `*IT` PostgreSQL/Testcontainers tests.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | yes | BCrypt cost 12, generated temporary passwords, password policy validator, no reusable default password |
| V3 Session Management | yes | short-lived access JWT, opaque refresh token rotation, chain reuse detection, httpOnly SameSite Strict cookies |
| V4 Access Control | yes | Spring Security Resource Server, `@EnableMethodSecurity`, explicit permissions and self-vs-other checks |
| V5 Input Validation | yes | Bean Validation, domain validators, contract-first request schemas, department/doc type validation |
| V6 Cryptography | yes | Spring Security/Nimbus JWT APIs, HS256 secret from `JWT_SECRET`, `SecureRandom`, no hand-rolled crypto |
| V7 Error Handling and Logging | yes | RFC 7807 ProblemDetail, durable audit events, correlation IDs |

### Known Threat Patterns for Spring Security Auth/RBAC

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Stolen refresh token reuse | Spoofing/Elevation of Privilege | Store only hashes, rotate on every refresh, revoke family on reuse |
| CSRF on cookie-authenticated unsafe methods | Tampering | SameSite Strict plus Origin/Referer validation for unsafe `/api/v1/**` cookie-auth requests |
| Stale permissions in JWT | Elevation of Privilege | Short 15-minute access TTL; force-refresh is deferred by D-12 |
| Last admin lockout | Denial of Service | Last-admin and last-admin-visibility protections before role/user/policy mutation |
| Weak password reset/onboarding | Spoofing | SecureRandom temporary passwords returned once, `must_change_password`, BCrypt cost 12 |
| JWT issuer misconfiguration | Spoofing | Do not use `NimbusJwtDecoder.withIssuerLocation`; use explicit self-issued secret-key decoder/encoder |

## Open Questions (RESOLVED)

1. **Scope of Origin/Referer validation** — RESOLVED: apply to all unsafe `/api/v1/**` cookie-auth requests per D-10/D-11.
2. **JWT decoder builder** — RESOLVED: use `NimbusJwtDecoder.withSecretKey()` and avoid `withIssuerLocation` for Phase 2 self-issued HS256 tokens.
3. **Integration test database** — RESOLVED: use Testcontainers PostgreSQL under `mvn verify`; do not rely on H2 for Phase 2 schema behavior.

## Sources

- Spring Boot 3.3.6 dependency BOM on Maven Central:
  https://central.sonatype.com/artifact/org.springframework.boot/spring-boot-dependencies/3.3.6
- Spring Security OAuth2 Resource Server overview:
  https://docs.spring.io/spring-security/reference/servlet/oauth2/
- Spring Security Resource Server JWT reference:
  https://docs.spring.io/spring-security/reference/6.5/servlet/oauth2/resource-server/jwt.html
- Spring Security `spring-security-oauth2-jose` 6.3.5 POM on Maven Central:
  https://central.sonatype.com/artifact/org.springframework.security/spring-security-oauth2-jose/6.3.5
- Nimbus JOSE + JWT 10.9 on Maven Central:
  https://central.sonatype.com/artifact/com.nimbusds/nimbus-jose-jwt
- Spring Security CSRF reference:
  https://docs.spring.io/spring-security/reference/features/exploits/csrf.html
- Spring Security 6.3 method security reference:
  https://docs.spring.io/spring-security/reference/6.3/servlet/authorization/method-security.html
- Spring Framework `ResponseCookie` 6.1.22 Javadoc:
  https://docs.enterprise.spring.io/spring-framework/docs/6.1.22/javadoc-api/org/springframework/http/ResponseCookie.html
- Spring Framework `ResponseCookie.ResponseCookieBuilder` 6.1.22 Javadoc:
  https://docs.enterprise.spring.io/spring-framework/docs/6.1.22/javadoc-api/org/springframework/http/ResponseCookie.ResponseCookieBuilder.html
- Spring Framework MVC `ResponseEntity` reference:
  https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-controller/ann-methods/responseentity.html
- Spring Boot Testcontainers reference:
  https://docs.enterprise.spring.io/spring-boot/reference/testing/testcontainers.html
- RFC 9700, OAuth 2.0 Security Best Current Practice:
  https://www.rfc-editor.org/rfc/rfc9700.html
- OWASP JSON Web Token for Java Cheat Sheet:
  https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html
- Spring Security advisory CVE-2026-22748:
  https://spring.io/security/cve-2026-22748/
