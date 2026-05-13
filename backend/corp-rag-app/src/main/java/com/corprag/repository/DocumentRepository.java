package com.corprag.repository;

import com.corprag.domain.AccessLevel;
import com.corprag.domain.DocType;
import com.corprag.domain.DocumentPage;
import com.corprag.domain.DocumentRecord;
import com.corprag.domain.DocumentSearchCriteria;
import com.corprag.domain.DocumentStatus;
import com.corprag.domain.ResolvedAccessFilter;
import java.time.Instant;
import java.util.Collection;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.UUID;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.core.simple.JdbcClient.StatementSpec;
import org.springframework.stereotype.Repository;

@Repository
public class DocumentRepository {

    private static final RowMapper<DocumentRecord> DOCUMENT_MAPPER = (rs, rowNum) -> new DocumentRecord(
            rs.getObject("id", UUID.class),
            rs.getString("title"),
            rs.getString("description"),
            rs.getString("original_filename"),
            rs.getString("mime_type"),
            rs.getLong("size_bytes"),
            AccessLevel.valueOf(rs.getString("access_level")),
            rs.getString("department"),
            DocType.valueOf(rs.getString("doc_type")),
            rs.getString("language"),
            DocumentStatus.valueOf(rs.getString("status")),
            rs.getObject("owner_user_id", UUID.class),
            rs.getString("storage_bucket"),
            rs.getString("storage_key"),
            rs.getString("content_sha256"),
            JdbcRowSupport.instant(rs, "uploaded_at"),
            JdbcRowSupport.instant(rs, "indexed_at"),
            rs.getObject("chunk_count", Integer.class),
            rs.getString("failure_stage"),
            rs.getString("failure_error_code"),
            rs.getString("failure_message"),
            rs.getObject("failure_retryable", Boolean.class),
            rs.getObject("failure_retry_count", Integer.class),
            rs.getString("qdrant_collection"),
            rs.getObject("neo4j_entity_count", Integer.class),
            rs.getObject("indexing_duration_ms", Long.class),
            JdbcRowSupport.instant(rs, "deleted_at"),
            rs.getObject("deleted_by", UUID.class));

    private final JdbcClient jdbc;

    public DocumentRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public void insert(DocumentRecord document) {
        jdbc.sql(
                        """
                        INSERT INTO documents (
                            id, title, description, original_filename, mime_type, size_bytes,
                            access_level, department, doc_type, language, status, owner_user_id,
                            storage_bucket, storage_key, content_sha256, uploaded_at, indexed_at,
                            chunk_count, failure_stage, failure_error_code, failure_message,
                            failure_retryable, failure_retry_count, qdrant_collection,
                            neo4j_entity_count, indexing_duration_ms, deleted_at, deleted_by
                        )
                        VALUES (
                            :id, :title, :description, :originalFilename, :mimeType, :sizeBytes,
                            :accessLevel, :department, :docType, :language, :status, :ownerUserId,
                            :storageBucket, :storageKey, :contentSha256, :uploadedAt, :indexedAt,
                            :chunkCount, :failureStage, :failureErrorCode, :failureMessage,
                            :failureRetryable, :failureRetryCount, :qdrantCollection,
                            :neo4jEntityCount, :indexingDurationMs, :deletedAt, :deletedBy
                        )
                        """)
                .param("id", document.id())
                .param("title", document.title())
                .param("description", document.description())
                .param("originalFilename", document.originalFilename())
                .param("mimeType", document.mimeType())
                .param("sizeBytes", document.sizeBytes())
                .param("accessLevel", document.accessLevel().name())
                .param("department", document.department())
                .param("docType", document.docType().name())
                .param("language", document.language())
                .param("status", document.status().name())
                .param("ownerUserId", document.ownerUserId())
                .param("storageBucket", document.storageBucket())
                .param("storageKey", document.storageKey())
                .param("contentSha256", document.contentSha256())
                .param("uploadedAt", JdbcRowSupport.timestamp(document.uploadedAt()))
                .param("indexedAt", JdbcRowSupport.timestamp(document.indexedAt()))
                .param("chunkCount", document.chunkCount())
                .param("failureStage", document.failureStage())
                .param("failureErrorCode", document.failureErrorCode())
                .param("failureMessage", document.failureMessage())
                .param("failureRetryable", document.failureRetryable())
                .param("failureRetryCount", document.failureRetryCount())
                .param("qdrantCollection", document.qdrantCollection())
                .param("neo4jEntityCount", document.neo4jEntityCount())
                .param("indexingDurationMs", document.indexingDurationMs())
                .param("deletedAt", JdbcRowSupport.timestamp(document.deletedAt()))
                .param("deletedBy", document.deletedBy())
                .update();
    }

    public Optional<DocumentRecord> findById(UUID id) {
        return jdbc.sql("SELECT * FROM documents WHERE id = :id")
                .param("id", id)
                .query(DOCUMENT_MAPPER)
                .optional();
    }

    public Optional<DocumentRecord> findVisibleById(UUID id, ResolvedAccessFilter filter) {
        StatementSpec spec = bindVisibility(
                jdbc.sql("SELECT * FROM documents WHERE id = :id AND " + visibleWhere(filter))
                        .param("id", id),
                filter);
        return spec.query(DOCUMENT_MAPPER).optional();
    }

    public DocumentPage pageVisibleDocuments(ResolvedAccessFilter filter, int limit, int offset) {
        return pageVisibleDocuments(filter, DocumentSearchCriteria.empty(), limit, offset);
    }

    public DocumentPage pageVisibleDocuments(
            ResolvedAccessFilter filter,
            DocumentSearchCriteria criteria,
            int limit,
            int offset) {
        String where = visibleWhere(filter) + criteriaWhere(criteria);
        List<DocumentRecord> documents = bindCriteria(bindVisibility(
                        jdbc.sql(
                                        """
                                        SELECT *
                                        FROM documents
                                        WHERE %s
                                        ORDER BY uploaded_at DESC, id DESC
                                        LIMIT :limit OFFSET :offset
                                        """
                                                .formatted(where))
                                .param("limit", limit)
                                .param("offset", offset),
                        filter),
                        criteria)
                .query(DOCUMENT_MAPPER)
                .list();
        Long total = bindCriteria(bindVisibility(jdbc.sql("SELECT COUNT(*) FROM documents WHERE " + where), filter), criteria)
                .query(Long.class)
                .single();
        return new DocumentPage(documents, total);
    }

    public Optional<DocumentRecord> findActiveDuplicate(String contentSha256, String department) {
        return jdbc.sql(
                        """
                        SELECT *
                        FROM documents
                        WHERE content_sha256 = :contentSha256
                          AND department = :department
                          AND deleted_at IS NULL
                        ORDER BY uploaded_at ASC
                        LIMIT 1
                        """)
                .param("contentSha256", contentSha256)
                .param("department", department)
                .query(DOCUMENT_MAPPER)
                .optional();
    }

    public boolean softDeleteVisible(UUID id, ResolvedAccessFilter filter, UUID deletedBy, Instant deletedAt) {
        int updated = bindVisibility(
                        jdbc.sql(
                                        """
                                        UPDATE documents
                                        SET deleted_at = :deletedAt,
                                            deleted_by = :deletedBy
                                        WHERE id = :id
                                          AND %s
                                        """
                                                .formatted(visibleWhere(filter)))
                                .param("id", id)
                                .param("deletedAt", JdbcRowSupport.timestamp(deletedAt))
                                .param("deletedBy", deletedBy),
                        filter)
                .update();
        return updated == 1;
    }

    public boolean markIndexed(
            UUID id,
            Instant indexedAt,
            int chunkCount,
            String qdrantCollection,
            Integer neo4jEntityCount,
            Long indexingDurationMs) {
        int updated = jdbc.sql(
                        """
                        UPDATE documents
                        SET status = 'INDEXED',
                            indexed_at = :indexedAt,
                            chunk_count = :chunkCount,
                            failure_stage = NULL,
                            failure_error_code = NULL,
                            failure_message = NULL,
                            failure_retryable = NULL,
                            failure_retry_count = NULL,
                            qdrant_collection = :qdrantCollection,
                            neo4j_entity_count = :neo4jEntityCount,
                            indexing_duration_ms = :indexingDurationMs
                        WHERE id = :id
                          AND deleted_at IS NULL
                        """)
                .param("id", id)
                .param("indexedAt", JdbcRowSupport.timestamp(indexedAt))
                .param("chunkCount", chunkCount)
                .param("qdrantCollection", qdrantCollection)
                .param("neo4jEntityCount", neo4jEntityCount)
                .param("indexingDurationMs", indexingDurationMs)
                .update();
        return updated == 1;
    }

    public boolean markIndexingFailed(
            UUID id,
            String failureStage,
            String failureErrorCode,
            String failureMessage,
            boolean retryable,
            int retryCount) {
        int updated = jdbc.sql(
                        """
                        UPDATE documents
                        SET status = 'INDEXING_FAILED',
                            failure_stage = :failureStage,
                            failure_error_code = :failureErrorCode,
                            failure_message = :failureMessage,
                            failure_retryable = :retryable,
                            failure_retry_count = :retryCount
                        WHERE id = :id
                          AND deleted_at IS NULL
                        """)
                .param("id", id)
                .param("failureStage", failureStage)
                .param("failureErrorCode", failureErrorCode)
                .param("failureMessage", failureMessage)
                .param("retryable", retryable)
                .param("retryCount", retryCount)
                .update();
        return updated == 1;
    }

    private static String visibleWhere(ResolvedAccessFilter filter) {
        if (filter.accessLevels().isEmpty() || filter.docTypes().isEmpty()) {
            return "deleted_at IS NULL AND 1 = 0";
        }
        String where = "deleted_at IS NULL AND access_level IN (:accessLevels) AND doc_type IN (:docTypes)";
        if (!filter.departments().isEmpty()) {
            where += " AND department IN (:departments)";
        }
        return where;
    }

    private static StatementSpec bindVisibility(StatementSpec spec, ResolvedAccessFilter filter) {
        StatementSpec bound = spec
                .param("accessLevels", names(filter.accessLevels()))
                .param("docTypes", names(filter.docTypes()));
        if (!filter.departments().isEmpty()) {
            bound = bound.param("departments", filter.departments());
        }
        return bound;
    }

    private static String criteriaWhere(DocumentSearchCriteria criteria) {
        if (criteria == null) {
            return "";
        }
        StringBuilder where = new StringBuilder();
        if (criteria.status() != null) {
            where.append(" AND status = :status");
        }
        if (criteria.department() != null) {
            where.append(" AND department = :department");
        }
        if (criteria.docType() != null) {
            where.append(" AND doc_type = :criteriaDocType");
        }
        if (criteria.language() != null) {
            where.append(" AND language = :language");
        }
        if (criteria.search() != null) {
            where.append(" AND (LOWER(title) LIKE :search OR LOWER(original_filename) LIKE :search)");
        }
        return where.toString();
    }

    private static StatementSpec bindCriteria(StatementSpec spec, DocumentSearchCriteria criteria) {
        if (criteria == null) {
            return spec;
        }
        StatementSpec bound = spec;
        if (criteria.status() != null) {
            bound = bound.param("status", criteria.status().name());
        }
        if (criteria.department() != null) {
            bound = bound.param("department", criteria.department());
        }
        if (criteria.docType() != null) {
            bound = bound.param("criteriaDocType", criteria.docType().name());
        }
        if (criteria.language() != null) {
            bound = bound.param("language", criteria.language());
        }
        if (criteria.search() != null) {
            bound = bound.param("search", "%" + criteria.search().toLowerCase(Locale.ROOT) + "%");
        }
        return bound;
    }

    private static List<String> names(Collection<? extends Enum<?>> values) {
        return values.stream()
                .map(Enum::name)
                .toList();
    }
}
