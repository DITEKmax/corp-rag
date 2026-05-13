package com.corprag.repository;

import com.corprag.domain.ProcessedEventRecord;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

@Repository
public class ProcessedEventRepository {

    private static final RowMapper<ProcessedEventRecord> PROCESSED_EVENT_MAPPER = (rs, rowNum) -> new ProcessedEventRecord(
            rs.getObject("event_id", UUID.class),
            rs.getString("event_type"),
            rs.getObject("correlation_id", UUID.class),
            JdbcRowSupport.instant(rs, "processed_at"));

    private final JdbcClient jdbc;

    public ProcessedEventRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public boolean insertIfAbsent(UUID eventId, String eventType, UUID correlationId, Instant processedAt) {
        int inserted = jdbc.sql(
                        """
                        INSERT INTO processed_events (event_id, event_type, correlation_id, processed_at)
                        VALUES (:eventId, :eventType, :correlationId, :processedAt)
                        ON CONFLICT (event_id) DO NOTHING
                        """)
                .param("eventId", eventId)
                .param("eventType", eventType)
                .param("correlationId", correlationId)
                .param("processedAt", JdbcRowSupport.timestamp(processedAt))
                .update();
        return inserted == 1;
    }

    public Optional<ProcessedEventRecord> findById(UUID eventId) {
        return jdbc.sql("SELECT * FROM processed_events WHERE event_id = :eventId")
                .param("eventId", eventId)
                .query(PROCESSED_EVENT_MAPPER)
                .optional();
    }

    public int cleanupProcessedBefore(Instant cutoff) {
        return jdbc.sql("DELETE FROM processed_events WHERE processed_at < :cutoff")
                .param("cutoff", JdbcRowSupport.timestamp(cutoff))
                .update();
    }
}
