package com.corprag;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.corprag.adapter.amqp.AmqpHeaderNames;
import com.corprag.adapter.amqp.DocumentIndexedConsumer;
import com.corprag.adapter.amqp.DocumentIndexingFailedConsumer;
import com.corprag.adapter.storage.DocumentStorageClient;
import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.contracts.constants.EventRoutingKeys;
import com.corprag.domain.DocumentRecord;
import com.corprag.domain.DocumentStatus;
import com.corprag.domain.UserAccount;
import com.corprag.repository.DocumentRepository;
import com.corprag.repository.ProcessedEventRepository;
import com.corprag.repository.UserRepository;
import com.corprag.repository.UserRoleRepository;
import com.corprag.testsupport.AuthTestFixtures;
import com.corprag.testsupport.PostgresIntegrationTestSupport;
import com.jayway.jsonpath.JsonPath;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessageBuilder;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.request.RequestPostProcessor;
import org.testcontainers.junit.jupiter.Testcontainers;

@AutoConfigureMockMvc
@SpringBootTest(properties = {
        "app.security.jwt.secret=test-only-phase-two-hs256-secret-never-use-in-runtime",
        "app.security.jwt.issuer=corp-rag-test",
        "app.security.cookies.secure=false",
        "app.document-storage.initialize-bucket=false",
        "app.document-indexing-consumers.enabled=true",
        "spring.rabbitmq.listener.simple.auto-startup=false",
        "spring.rabbitmq.listener.direct.auto-startup=false"
})
@Testcontainers(disabledWithoutDocker = true)
class DocumentLifecycleFlowIT extends PostgresIntegrationTestSupport {

    private static final UUID ADMIN_ROLE_ID = UUID.fromString("00000000-0000-4000-8000-000000000001");

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private UserRoleRepository userRoleRepository;

    @Autowired
    private DocumentRepository documentRepository;

    @Autowired
    private ProcessedEventRepository processedEventRepository;

    @Autowired
    private DocumentIndexedConsumer indexedConsumer;

    @Autowired
    private DocumentIndexingFailedConsumer failedConsumer;

    @Autowired
    private JdbcClient jdbc;

    @MockBean
    private DocumentStorageClient storageClient;

    @Test
    void phaseThreeLifecycleCoversUploadVisibilityOutboxDeleteConsumersAndAudit() throws Exception {
        TestUser admin = createAdmin();
        when(storageClient.presignedGetUrl(any(), any(Duration.class)))
                .thenReturn(URI.create("https://minio.local/corp-rag-documents/raw-url?signature=test"));

        String unique = UUID.randomUUID().toString().replace("-", "").substring(0, 8);
        UUID deletedDocumentId = uploadDocument(admin, "Lifecycle Deleted " + unique, "deleted " + unique);

        mockMvc.perform(get("/api/v1/documents")
                        .param("search", "Lifecycle Deleted " + unique)
                        .with(jwtFor(admin)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total").value(1))
                .andExpect(jsonPath("$.items[0].id").value(deletedDocumentId.toString()));

        assertThat(countOutbox(deletedDocumentId, EventRoutingKeys.DOCUMENT_UPLOADED)).isEqualTo(1);
        assertThat(countAudit(deletedDocumentId, "DOCUMENT_UPLOADED")).isEqualTo(1);

        mockMvc.perform(get("/api/v1/documents/{documentId}/raw", deletedDocumentId)
                        .with(jwtFor(admin)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.url").value("https://minio.local/corp-rag-documents/raw-url?signature=test"));
        assertThat(countAudit(deletedDocumentId, "DOCUMENT_RAW_URL_ISSUED")).isEqualTo(1);

        mockMvc.perform(delete("/api/v1/documents/{documentId}", deletedDocumentId)
                        .with(jwtFor(admin)))
                .andExpect(status().isNoContent());
        assertThat(documentRepository.findById(deletedDocumentId))
                .hasValueSatisfying(document -> {
                    assertThat(document.status()).isEqualTo(DocumentStatus.UPLOADED);
                    assertThat(document.deletedAt()).isNotNull();
                });
        assertThat(countOutbox(deletedDocumentId, EventRoutingKeys.DOCUMENT_DELETED)).isEqualTo(1);
        assertThat(countAudit(deletedDocumentId, "DOCUMENT_DELETED")).isEqualTo(1);

        mockMvc.perform(get("/api/v1/documents")
                        .param("search", "Lifecycle Deleted " + unique)
                        .with(jwtFor(admin)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total").value(0));

        UUID indexedDocumentId = uploadDocument(admin, "Lifecycle Indexed " + unique, "indexed " + unique);
        UUID indexedEventId = UUID.randomUUID();
        UUID indexedCorrelationId = UUID.randomUUID();
        Message indexedMessage = message(
                indexedEnvelope(indexedEventId, indexedDocumentId, indexedCorrelationId),
                indexedCorrelationId);
        indexedConsumer.handle(indexedMessage);
        indexedConsumer.handle(indexedMessage);

        DocumentRecord indexedDocument = documentRepository.findById(indexedDocumentId).orElseThrow();
        assertThat(indexedDocument.status()).isEqualTo(DocumentStatus.INDEXED);
        assertThat(indexedDocument.chunkCount()).isEqualTo(42);
        assertThat(indexedDocument.qdrantCollection()).isEqualTo("documents_chunks");
        assertThat(indexedDocument.neo4jEntityCount()).isEqualTo(18);
        assertThat(indexedDocument.indexingDurationMs()).isEqualTo(87520);
        assertThat(processedEventRepository.findById(indexedEventId)).isPresent();
        assertThat(countAudit(indexedDocumentId, "DOCUMENT_INDEXED")).isEqualTo(1);
        assertThat(auditCorrelation(indexedDocumentId, "DOCUMENT_INDEXED")).isEqualTo(indexedCorrelationId);

        UUID failedDocumentId = uploadDocument(admin, "Lifecycle Failed " + unique, "failed " + unique);
        UUID failedEventId = UUID.randomUUID();
        UUID failedCorrelationId = UUID.randomUUID();
        failedConsumer.handle(message(failedEnvelope(failedEventId, failedDocumentId, failedCorrelationId), failedCorrelationId));

        DocumentRecord failedDocument = documentRepository.findById(failedDocumentId).orElseThrow();
        assertThat(failedDocument.status()).isEqualTo(DocumentStatus.INDEXING_FAILED);
        assertThat(failedDocument.failureStage()).isEqualTo("PARSING");
        assertThat(failedDocument.failureErrorCode()).isEqualTo(ErrorCodes.INVALID_FILE_FORMAT.code());
        assertThat(failedDocument.failureMessage()).isEqualTo("No extractable text");
        assertThat(failedDocument.failureRetryable()).isFalse();
        assertThat(failedDocument.failureRetryCount()).isZero();
        assertThat(processedEventRepository.findById(failedEventId)).isPresent();
        assertThat(countAudit(failedDocumentId, "DOCUMENT_INDEXING_FAILED")).isEqualTo(1);

        UUID lateEventId = UUID.randomUUID();
        indexedConsumer.handle(message(indexedEnvelope(lateEventId, deletedDocumentId, UUID.randomUUID()), null));
        assertThat(processedEventRepository.findById(lateEventId)).isPresent();
        assertThat(documentRepository.findById(deletedDocumentId))
                .hasValueSatisfying(document -> {
                    assertThat(document.status()).isEqualTo(DocumentStatus.UPLOADED);
                    assertThat(document.deletedAt()).isNotNull();
                });
    }

    private UUID uploadDocument(TestUser user, String title, String content) throws Exception {
        MockMultipartFile file = new MockMultipartFile(
                "file",
                title.toLowerCase(Locale.ROOT).replace(" ", "-") + ".txt",
                "text/plain",
                content.getBytes(StandardCharsets.UTF_8));
        MvcResult result = mockMvc.perform(multipart("/api/v1/documents")
                        .file(file)
                        .param("title", title)
                        .param("description", "Lifecycle verification")
                        .param("accessLevel", "INTERNAL")
                        .param("department", "HR")
                        .param("docType", "POLICY")
                        .param("language", "en")
                        .contentType(MediaType.MULTIPART_FORM_DATA)
                        .with(jwtFor(user)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.status").value("UPLOADED"))
                .andReturn();
        return UUID.fromString(JsonPath.read(result.getResponse().getContentAsString(), "$.id"));
    }

    private TestUser createAdmin() {
        UUID id = UUID.randomUUID();
        String username = "lifecycle_" + id.toString().replace("-", "").substring(0, 10);
        Instant now = Instant.now();
        userRepository.create(new UserAccount(
                id,
                username,
                username + "@example.com",
                "Lifecycle Admin",
                AuthTestFixtures.DEPARTMENT_IT,
                passwordEncoder.encode("CorrectHorseBattery12!"),
                true,
                false,
                now,
                now,
                null,
                0));
        userRoleRepository.replaceUserRoles(id, List.of(ADMIN_ROLE_ID), id, now);
        return new TestUser(id, username);
    }

    private RequestPostProcessor jwtFor(TestUser user) {
        return jwt().jwt(token -> token
                .subject(user.id().toString())
                .claim("username", user.username())
                .claim("permissions", AuthTestFixtures.ALL_PERMISSIONS)
                .claim("roles", List.of(AuthTestFixtures.ROLE_ADMIN))
                .claim("must_change_password", false)
                .issuer(AuthTestFixtures.TEST_JWT_ISSUER));
    }

    private int countOutbox(UUID documentId, String eventType) {
        return jdbc.sql(
                        """
                        SELECT COUNT(*)
                        FROM outbox_events
                        WHERE aggregate_id = :documentId
                          AND event_type = :eventType
                        """)
                .param("documentId", documentId)
                .param("eventType", eventType)
                .query(Integer.class)
                .single();
    }

    private int countAudit(UUID documentId, String eventType) {
        return jdbc.sql(
                        """
                        SELECT COUNT(*)
                        FROM audit_events
                        WHERE entity_id = :documentId
                          AND event_type = :eventType
                        """)
                .param("documentId", documentId)
                .param("eventType", eventType)
                .query(Integer.class)
                .single();
    }

    private UUID auditCorrelation(UUID documentId, String eventType) {
        return jdbc.sql(
                        """
                        SELECT correlation_id
                        FROM audit_events
                        WHERE entity_id = :documentId
                          AND event_type = :eventType
                        ORDER BY occurred_at DESC
                        LIMIT 1
                        """)
                .param("documentId", documentId)
                .param("eventType", eventType)
                .query(UUID.class)
                .single();
    }

    private static Message message(String json, UUID correlationId) {
        MessageBuilder builder = MessageBuilder.withBody(json.getBytes(StandardCharsets.UTF_8));
        if (correlationId != null) {
            builder.setHeader(AmqpHeaderNames.CORRELATION_ID, correlationId.toString());
        }
        return builder.build();
    }

    private static String indexedEnvelope(UUID eventId, UUID documentId, UUID correlationId) {
        return """
                {
                  "metadata": {
                    "eventId": "%s",
                    "eventType": "%s",
                    "eventVersion": "1.0.0",
                    "occurredAt": "2026-05-13T12:00:00Z",
                    "correlationId": "%s",
                    "sourceService": "corp-rag-ai"
                  },
                  "payload": {
                    "documentId": "%s",
                    "chunkCount": 42,
                    "indexedAt": "2026-05-13T12:01:00Z",
                    "qdrantCollection": "documents_chunks",
                    "neo4jEntityCount": 18,
                    "durationMs": 87520
                  }
                }
                """.formatted(eventId, EventRoutingKeys.DOCUMENT_INDEXED, correlationId, documentId);
    }

    private static String failedEnvelope(UUID eventId, UUID documentId, UUID correlationId) {
        return """
                {
                  "metadata": {
                    "eventId": "%s",
                    "eventType": "%s",
                    "eventVersion": "1.0.0",
                    "occurredAt": "2026-05-13T12:00:00Z",
                    "correlationId": "%s",
                    "sourceService": "corp-rag-ai"
                  },
                  "payload": {
                    "documentId": "%s",
                    "stage": "PARSING",
                    "errorCode": "%s",
                    "errorMessage": "No extractable text",
                    "failedAt": "2026-05-13T12:02:00Z",
                    "retryable": false,
                    "retryCount": 0
                  }
                }
                """.formatted(
                eventId,
                EventRoutingKeys.DOCUMENT_INDEXING_FAILED,
                correlationId,
                documentId,
                ErrorCodes.INVALID_FILE_FORMAT.code());
    }

    private record TestUser(UUID id, String username) {
    }
}
