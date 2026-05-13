package com.corprag.repository;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.corprag.domain.AccessLevel;
import com.corprag.domain.DocType;
import com.corprag.domain.DocumentPage;
import com.corprag.domain.DocumentRecord;
import com.corprag.domain.DocumentStatus;
import com.corprag.domain.OutboxEventRecord;
import com.corprag.domain.ResolvedAccessFilter;
import com.corprag.testsupport.PostgresIntegrationTestSupport;
import java.time.Instant;
import java.util.Arrays;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.DataAccessException;
import org.testcontainers.junit.jupiter.Testcontainers;

@SpringBootTest
@Testcontainers(disabledWithoutDocker = true)
class DocumentPersistenceIT extends PostgresIntegrationTestSupport {

    @Autowired
    private DocumentRepository documentRepository;

    @Autowired
    private OutboxEventRepository outboxEventRepository;

    @Autowired
    private ProcessedEventRepository processedEventRepository;

    @Test
    void documentDuplicateConstraintAllowsReuploadAfterSoftDelete() {
        Instant now = Instant.parse("2026-05-13T10:00:00Z");
        String sha = sha256();
        DocumentRecord first = document("Duplicate One", sha, "FINANCE", DocType.POLICY, AccessLevel.INTERNAL, now);
        documentRepository.insert(first);

        assertThat(documentRepository.findActiveDuplicate(sha, "FINANCE"))
                .hasValueSatisfying(found -> assertThat(found.id()).isEqualTo(first.id()));

        DocumentRecord activeDuplicate = document("Duplicate Two", sha, "FINANCE", DocType.POLICY, AccessLevel.INTERNAL, now.plusSeconds(1));
        assertThatThrownBy(() -> documentRepository.insert(activeDuplicate))
                .isInstanceOf(DataAccessException.class);

        assertThat(documentRepository.softDeleteVisible(first.id(), fullFilter(), null, now.plusSeconds(2))).isTrue();

        DocumentRecord replacement = document("Duplicate Replacement", sha, "FINANCE", DocType.POLICY, AccessLevel.INTERNAL, now.plusSeconds(3));
        documentRepository.insert(replacement);

        assertThat(documentRepository.findActiveDuplicate(sha, "FINANCE"))
                .hasValueSatisfying(found -> assertThat(found.id()).isEqualTo(replacement.id()));
    }

    @Test
    void documentVisibilityUsesDocTypeDepartmentAccessLevelAndDeletedPredicates() {
        Instant now = Instant.parse("2026-05-13T11:00:00Z");
        DocumentRecord visible = document("Visible", sha256(), "HR", DocType.POLICY, AccessLevel.INTERNAL, now);
        DocumentRecord wrongDepartment = document("Wrong Department", sha256(), "FINANCE", DocType.POLICY, AccessLevel.INTERNAL, now.plusSeconds(1));
        DocumentRecord wrongType = document("Wrong Type", sha256(), "HR", DocType.REPORT, AccessLevel.INTERNAL, now.plusSeconds(2));
        DocumentRecord tooSensitive = document("Too Sensitive", sha256(), "HR", DocType.POLICY, AccessLevel.RESTRICTED, now.plusSeconds(3));
        DocumentRecord deleted = document("Deleted", sha256(), "HR", DocType.POLICY, AccessLevel.INTERNAL, now.plusSeconds(4));

        documentRepository.insert(visible);
        documentRepository.insert(wrongDepartment);
        documentRepository.insert(wrongType);
        documentRepository.insert(tooSensitive);
        documentRepository.insert(deleted);
        assertThat(documentRepository.softDeleteVisible(deleted.id(), fullFilter(), null, now.plusSeconds(5))).isTrue();

        ResolvedAccessFilter hrPolicyInternal = new ResolvedAccessFilter(
                List.of(AccessLevel.PUBLIC, AccessLevel.INTERNAL),
                List.of("HR"),
                List.of(DocType.POLICY));
        DocumentPage page = documentRepository.pageVisibleDocuments(hrPolicyInternal, 25, 0);

        assertThat(page.total()).isEqualTo(1);
        assertThat(page.documents()).extracting(DocumentRecord::id).containsExactly(visible.id());
        assertThat(documentRepository.findVisibleById(wrongDepartment.id(), hrPolicyInternal)).isEmpty();
        assertThat(documentRepository.findVisibleById(wrongType.id(), hrPolicyInternal)).isEmpty();
        assertThat(documentRepository.findVisibleById(tooSensitive.id(), hrPolicyInternal)).isEmpty();
        assertThat(documentRepository.findVisibleById(deleted.id(), hrPolicyInternal)).isEmpty();

        ResolvedAccessFilter wildcardDepartment = new ResolvedAccessFilter(
                List.of(AccessLevel.PUBLIC, AccessLevel.INTERNAL),
                List.of(),
                List.of(DocType.POLICY));
        assertThat(documentRepository.findVisibleById(wrongDepartment.id(), wildcardDepartment)).isPresent();
    }

    @Test
    void outboxPollingAndProcessedEventInsertAreIdempotent() {
        Instant now = Instant.parse("2026-05-13T12:00:00Z");
        OutboxEventRecord ready = outboxEvent(now.minusSeconds(10), now.minusSeconds(1));
        OutboxEventRecord future = outboxEvent(now.minusSeconds(5), now.plusSeconds(60));

        outboxEventRepository.insert(ready);
        outboxEventRepository.insert(future);

        assertThat(outboxEventRepository.pollReadyUnpublished(now, 10))
                .extracting(OutboxEventRecord::id)
                .containsExactly(ready.id());
        assertThat(outboxEventRepository.markFailure(ready.id(), "rabbitmq unavailable", now.plusSeconds(30))).isTrue();
        assertThat(outboxEventRepository.findById(ready.id()))
                .hasValueSatisfying(found -> {
                    assertThat(found.publishAttempts()).isEqualTo(1);
                    assertThat(found.lastError()).isEqualTo("rabbitmq unavailable");
                });
        assertThat(outboxEventRepository.markPublished(future.id(), now.plusSeconds(90))).isTrue();

        UUID eventId = UUID.randomUUID();
        UUID correlationId = UUID.randomUUID();
        assertThat(processedEventRepository.insertIfAbsent(eventId, "document.indexed", correlationId, now)).isTrue();
        assertThat(processedEventRepository.insertIfAbsent(eventId, "document.indexed", correlationId, now.plusSeconds(1))).isFalse();
        assertThat(processedEventRepository.findById(eventId))
                .hasValueSatisfying(found -> assertThat(found.correlationId()).isEqualTo(correlationId));
    }

    @Test
    void indexingResultUpdatesOnlyActiveUploadedDocuments() {
        Instant now = Instant.parse("2026-05-13T13:00:00Z");
        DocumentRecord uploaded = document("Uploaded", sha256(), "HR", DocType.POLICY, AccessLevel.INTERNAL, now);
        DocumentRecord deleted = document("Deleted", sha256(), "HR", DocType.POLICY, AccessLevel.INTERNAL, now.plusSeconds(1));
        DocumentRecord alreadyIndexed = document(
                "Indexed",
                sha256(),
                "HR",
                DocType.POLICY,
                AccessLevel.INTERNAL,
                now.plusSeconds(2),
                DocumentStatus.INDEXED);
        documentRepository.insert(uploaded);
        documentRepository.insert(deleted);
        documentRepository.insert(alreadyIndexed);
        assertThat(documentRepository.softDeleteVisible(deleted.id(), fullFilter(), null, now.plusSeconds(3))).isTrue();

        assertThat(documentRepository.markIndexed(
                uploaded.id(),
                now.plusSeconds(10),
                42,
                "documents_chunks",
                18,
                87520L)).isTrue();
        assertThat(documentRepository.markIndexed(
                deleted.id(),
                now.plusSeconds(10),
                42,
                "documents_chunks",
                18,
                87520L)).isFalse();
        assertThat(documentRepository.markIndexingFailed(
                alreadyIndexed.id(),
                "PARSING",
                "INVALID_FILE_FORMAT",
                "No extractable text",
                false,
                0)).isFalse();

        assertThat(documentRepository.findById(uploaded.id()))
                .hasValueSatisfying(document -> {
                    assertThat(document.status()).isEqualTo(DocumentStatus.INDEXED);
                    assertThat(document.chunkCount()).isEqualTo(42);
                });
        assertThat(documentRepository.findById(deleted.id()))
                .hasValueSatisfying(document -> assertThat(document.status()).isEqualTo(DocumentStatus.UPLOADED));
        assertThat(documentRepository.findById(alreadyIndexed.id()))
                .hasValueSatisfying(document -> assertThat(document.status()).isEqualTo(DocumentStatus.INDEXED));
    }

    private static ResolvedAccessFilter fullFilter() {
        return new ResolvedAccessFilter(
                Arrays.asList(AccessLevel.values()),
                List.of(),
                Arrays.asList(DocType.values()));
    }

    private static DocumentRecord document(
            String title,
            String contentSha256,
            String department,
            DocType docType,
            AccessLevel accessLevel,
            Instant uploadedAt) {
        UUID id = UUID.randomUUID();
        return new DocumentRecord(
                id,
                title,
                null,
                title + ".txt",
                "text/plain",
                128,
                accessLevel,
                department,
                docType,
                "en",
                DocumentStatus.UPLOADED,
                null,
                "corp-rag-documents",
                "2026/05/" + id + ".txt",
                contentSha256,
                uploadedAt,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null);
    }

    private static DocumentRecord document(
            String title,
            String contentSha256,
            String department,
            DocType docType,
            AccessLevel accessLevel,
            Instant uploadedAt,
            DocumentStatus status) {
        UUID id = UUID.randomUUID();
        return new DocumentRecord(
                id,
                title,
                null,
                title + ".txt",
                "text/plain",
                128,
                accessLevel,
                department,
                docType,
                "en",
                status,
                null,
                "corp-rag-documents",
                "2026/05/" + id + ".txt",
                contentSha256,
                uploadedAt,
                null,
                status == DocumentStatus.INDEXED ? 3 : null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null);
    }

    private static OutboxEventRecord outboxEvent(Instant createdAt, Instant nextAttemptAt) {
        UUID id = UUID.randomUUID();
        return new OutboxEventRecord(
                id,
                "DOCUMENT",
                UUID.randomUUID(),
                "document.uploaded",
                "document.uploaded",
                "corp-rag.documents",
                "{\"eventId\":\"" + id + "\"}",
                "{}",
                UUID.randomUUID(),
                createdAt,
                null,
                0,
                null,
                nextAttemptAt);
    }

    private static String sha256() {
        return UUID.randomUUID().toString().replace("-", "") + UUID.randomUUID().toString().replace("-", "");
    }
}
