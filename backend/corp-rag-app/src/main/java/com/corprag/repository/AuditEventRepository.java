package com.corprag.repository;

import com.corprag.domain.AuditEventEntry;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

@Repository
public class AuditEventRepository {

    private final JdbcClient jdbc;

    public AuditEventRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public void insert(AuditEventEntry event) {
        jdbc.sql(
                        """
                        INSERT INTO audit_events (
                            id, occurred_at, event_category, event_type, outcome,
                            actor_user_id, target_user_id, entity_type, entity_id,
                            ip_address, user_agent, details, correlation_id
                        )
                        VALUES (
                            :id, :occurredAt, :eventCategory, :eventType, :outcome,
                            CASE
                                WHEN CAST(:actorUserId AS UUID) IS NULL THEN NULL
                                WHEN EXISTS (SELECT 1 FROM users WHERE id = CAST(:actorUserId AS UUID))
                                    THEN CAST(:actorUserId AS UUID)
                                ELSE NULL::UUID
                            END,
                            CASE
                                WHEN CAST(:targetUserId AS UUID) IS NULL THEN NULL
                                WHEN EXISTS (SELECT 1 FROM users WHERE id = CAST(:targetUserId AS UUID))
                                    THEN CAST(:targetUserId AS UUID)
                                ELSE NULL::UUID
                            END,
                            :entityType, :entityId,
                            :ipAddress, :userAgent, CAST(:detailsJson AS jsonb), :correlationId
                        )
                        """)
                .param("id", event.id())
                .param("occurredAt", JdbcRowSupport.timestamp(event.occurredAt()))
                .param("eventCategory", event.eventCategory())
                .param("eventType", event.eventType())
                .param("outcome", event.outcome().name())
                .param("actorUserId", event.actorUserId())
                .param("targetUserId", event.targetUserId())
                .param("entityType", event.entityType())
                .param("entityId", event.entityId())
                .param("ipAddress", event.ipAddress())
                .param("userAgent", event.userAgent())
                .param("detailsJson", event.detailsJson())
                .param("correlationId", event.correlationId())
                .update();
    }
}
