package com.corprag.adapter.rest;

import com.corprag.contracts.api.v1.model.Document;
import com.corprag.contracts.api.v1.model.HateoasLink;
import com.corprag.contracts.api.v1.model.PagedDocuments;
import com.corprag.domain.DocumentPage;
import com.corprag.domain.DocumentRecord;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
public class DocumentAssembler {

    public Document toContract(DocumentRecord record) {
        return toContract(record, true, true);
    }

    public Document toContract(DocumentRecord record, boolean canReadRaw, boolean canDelete) {
        return new Document()
                .id(record.id())
                .title(record.title())
                .description(record.description())
                .originalFilename(record.originalFilename())
                .mimeType(record.mimeType())
                .sizeBytes(record.sizeBytes())
                .accessLevel(com.corprag.contracts.api.v1.model.AccessLevel.fromValue(record.accessLevel().name()))
                .department(record.department())
                .docType(com.corprag.contracts.api.v1.model.DocType.fromValue(record.docType().name()))
                .language(com.corprag.contracts.api.v1.model.Language.fromValue(record.language()))
                .status(com.corprag.contracts.api.v1.model.DocumentStatus.fromValue(record.status().name()))
                .ownerUserId(record.ownerUserId())
                .uploadedAt(OffsetDateTime.ofInstant(record.uploadedAt(), ZoneOffset.UTC))
                .indexedAt(record.indexedAt() == null ? null : OffsetDateTime.ofInstant(record.indexedAt(), ZoneOffset.UTC))
                .chunkCount(record.chunkCount())
                .failureReason(record.failureMessage())
                .links(links(record.id().toString(), canReadRaw, canDelete));
    }

    public PagedDocuments toPaged(DocumentPage page, int pageNumber, int pageSize, boolean canReadRaw, boolean canDelete) {
        return new PagedDocuments()
                .items(page.documents().stream()
                        .map(document -> toContract(document, canReadRaw, canDelete))
                        .toList())
                .page(pageNumber)
                .size(pageSize)
                .total(page.total())
                .links(Map.of("self", new HateoasLink().href("/api/v1/documents?page=" + pageNumber + "&size=" + pageSize)));
    }

    private static Map<String, HateoasLink> links(String documentId, boolean canReadRaw, boolean canDelete) {
        Map<String, HateoasLink> links = new LinkedHashMap<>();
        if (canReadRaw) {
            links.put("self", new HateoasLink().href("/api/v1/documents/" + documentId));
            links.put("raw", new HateoasLink().href("/api/v1/documents/" + documentId + "/raw"));
        }
        if (canDelete) {
            links.put("delete", new HateoasLink().href("/api/v1/documents/" + documentId));
        }
        return links;
    }
}
