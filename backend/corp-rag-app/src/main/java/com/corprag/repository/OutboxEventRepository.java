package com.corprag.repository;

import com.corprag.domain.OutboxEventRecord;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

@Repository
public class OutboxEventRepository {

    private static final RowMapper<OutboxEventRecord> OUTBOX_MAPPER = (rs, rowNum) -> new OutboxEventRecord(
            rs.getObject("id", UUID.class),
            rs.getString("aggregate_type"),
            rs.getObject("aggregate_id", UUID.class),
            rs.getString("event_type"),
            rs.getString("routing_key"),
            rs.getString("exchange_name"),
            rs.getString("payload"),
            rs.getString("headers"),
            rs.getObject("correlation_id", UUID.class),
            JdbcRowSupport.instant(rs, "created_at"),
            JdbcRowSupport.instant(rs, "published_at"),
            rs.getInt("publish_attempts"),
            rs.getString("last_error"),
            JdbcRowSupport.instant(rs, "next_attempt_at"));

    private final JdbcClient jdbc;

    public OutboxEventRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public void insert(OutboxEventRecord event) {
        jdbc.sql(
                        """
                        INSERT INTO outbox_events (
                            id, aggregate_type, aggregate_id, event_type, routing_key, exchange_name,
                            payload, headers, correlation_id, created_at, published_at, publish_attempts,
                            last_error, next_attempt_at
                        )
                        VALUES (
                            :id, :aggregateType, :aggregateId, :eventType, :routingKey, :exchangeName,
                            CAST(:payloadJson AS jsonb), CAST(:headersJson AS jsonb), :correlationId,
                            :createdAt, :publishedAt, :publishAttempts, :lastError, :nextAttemptAt
                        )
                        """)
                .param("id", event.id())
                .param("aggregateType", event.aggregateType())
                .param("aggregateId", event.aggregateId())
                .param("eventType", event.eventType())
                .param("routingKey", event.routingKey())
                .param("exchangeName", event.exchangeName())
                .param("payloadJson", event.payloadJson())
                .param("headersJson", event.headersJson())
                .param("correlationId", event.correlationId())
                .param("createdAt", JdbcRowSupport.timestamp(event.createdAt()))
                .param("publishedAt", JdbcRowSupport.timestamp(event.publishedAt()))
                .param("publishAttempts", event.publishAttempts())
                .param("lastError", event.lastError())
                .param("nextAttemptAt", JdbcRowSupport.timestamp(event.nextAttemptAt()))
                .update();
    }

    public Optional<OutboxEventRecord> findById(UUID id) {
        return jdbc.sql("SELECT * FROM outbox_events WHERE id = :id")
                .param("id", id)
                .query(OUTBOX_MAPPER)
                .optional();
    }

    public List<OutboxEventRecord> pollReadyUnpublished(Instant now, int limit) {
        return jdbc.sql(
                        """
                        SELECT *
                        FROM outbox_events
                        WHERE published_at IS NULL
                          AND next_attempt_at <= :now
                        ORDER BY created_at ASC
                        FOR UPDATE SKIP LOCKED
                        LIMIT :limit
                        """)
                .param("now", JdbcRowSupport.timestamp(now))
                .param("limit", limit)
                .query(OUTBOX_MAPPER)
                .list();
    }

    public boolean markPublished(UUID id, Instant publishedAt) {
        int updated = jdbc.sql(
                        """
                        UPDATE outbox_events
                        SET published_at = :publishedAt,
                            last_error = NULL
                        WHERE id = :id
                          AND published_at IS NULL
                        """)
                .param("id", id)
                .param("publishedAt", JdbcRowSupport.timestamp(publishedAt))
                .update();
        return updated == 1;
    }

    public boolean markFailure(UUID id, String lastError, Instant nextAttemptAt) {
        int updated = jdbc.sql(
                        """
                        UPDATE outbox_events
                        SET publish_attempts = publish_attempts + 1,
                            last_error = :lastError,
                            next_attempt_at = :nextAttemptAt
                        WHERE id = :id
                          AND published_at IS NULL
                        """)
                .param("id", id)
                .param("lastError", lastError)
                .param("nextAttemptAt", JdbcRowSupport.timestamp(nextAttemptAt))
                .update();
        return updated == 1;
    }

    public int cleanupPublishedBefore(Instant cutoff) {
        return jdbc.sql("DELETE FROM outbox_events WHERE published_at < :cutoff")
                .param("cutoff", JdbcRowSupport.timestamp(cutoff))
                .update();
    }
}
