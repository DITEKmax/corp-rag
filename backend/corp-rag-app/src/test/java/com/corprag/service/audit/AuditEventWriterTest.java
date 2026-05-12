package com.corprag.service.audit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatNoException;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;

import com.corprag.domain.AuditEventEntry;
import com.corprag.domain.AuditOutcome;
import com.corprag.repository.AuditEventRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class AuditEventWriterTest {

    private static final UUID ACTOR_ID = UUID.fromString("00000000-0000-4000-8000-00000000f001");
    private static final UUID TARGET_ID = UUID.fromString("00000000-0000-4000-8000-00000000f002");

    @Mock
    private AuditEventRepository auditEventRepository;

    private AuditEventWriter writer;

    @BeforeEach
    void setUp() {
        writer = new AuditEventWriter(auditEventRepository, new ObjectMapper());
    }

    @Test
    void writesStructuredAuditEvent() {
        writer.writeEvent(
                "ACCESS_POLICY",
                "ACCESS_POLICY_UPDATED",
                AuditOutcome.SUCCESS,
                ACTOR_ID,
                TARGET_ID,
                "ACCESS_POLICY",
                TARGET_ID,
                "127.0.0.1",
                "JUnit",
                Map.of("role", "ADMIN"));

        ArgumentCaptor<AuditEventEntry> captor = ArgumentCaptor.forClass(AuditEventEntry.class);
        verify(auditEventRepository).insert(captor.capture());
        AuditEventEntry event = captor.getValue();
        assertThat(event.eventCategory()).isEqualTo("ACCESS_POLICY");
        assertThat(event.eventType()).isEqualTo("ACCESS_POLICY_UPDATED");
        assertThat(event.outcome()).isEqualTo(AuditOutcome.SUCCESS);
        assertThat(event.actorUserId()).isEqualTo(ACTOR_ID);
        assertThat(event.detailsJson()).contains("\"role\":\"ADMIN\"");
        assertThat(event.correlationId()).isNotNull();
    }

    @Test
    void auditWriteFailuresDoNotCommitActionFailures() {
        doThrow(new IllegalStateException("database unavailable"))
                .when(auditEventRepository)
                .insert(org.mockito.ArgumentMatchers.any(AuditEventEntry.class));

        assertThatNoException().isThrownBy(() -> writer.writeEvent(
                "USER",
                "USER_CREATED",
                AuditOutcome.SUCCESS,
                ACTOR_ID,
                TARGET_ID,
                "USER",
                TARGET_ID,
                null,
                null,
                Map.of()));
    }
}
