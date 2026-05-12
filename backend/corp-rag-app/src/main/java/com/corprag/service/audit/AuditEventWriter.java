package com.corprag.service.audit;

import com.corprag.domain.AuditEventEntry;
import com.corprag.domain.AuditOutcome;
import com.corprag.repository.AuditEventRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AuditEventWriter {

    private static final Logger LOGGER = LoggerFactory.getLogger(AuditEventWriter.class);

    private final AuditEventRepository auditEventRepository;
    private final ObjectMapper objectMapper;

    public AuditEventWriter(AuditEventRepository auditEventRepository, ObjectMapper objectMapper) {
        this.auditEventRepository = auditEventRepository;
        this.objectMapper = objectMapper;
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void writeAuthEvent(
            String eventType,
            AuditOutcome outcome,
            UUID actorUserId,
            UUID targetUserId,
            String ipAddress,
            String userAgent,
            Map<String, ?> details) {
        try {
            auditEventRepository.insert(new AuditEventEntry(
                    UUID.randomUUID(),
                    Instant.now(),
                    "AUTH",
                    eventType,
                    outcome,
                    actorUserId,
                    targetUserId,
                    "USER",
                    targetUserId,
                    ipAddress,
                    userAgent,
                    detailsJson(details),
                    UUID.randomUUID()));
        } catch (RuntimeException exception) {
            LOGGER.warn("Failed to write auth audit event {}", eventType, exception);
        }
    }

    private String detailsJson(Map<String, ?> details) {
        try {
            return objectMapper.writeValueAsString(details == null ? Map.of() : details);
        } catch (JsonProcessingException exception) {
            return "{}";
        }
    }
}
