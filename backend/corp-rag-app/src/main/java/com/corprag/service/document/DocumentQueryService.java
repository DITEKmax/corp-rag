package com.corprag.service.document;

import com.corprag.adapter.rest.ApiProblemException;
import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.domain.DocumentPage;
import com.corprag.domain.DocumentRecord;
import com.corprag.domain.DocumentSearchCriteria;
import com.corprag.domain.ResolvedAccessFilter;
import com.corprag.repository.DocumentRepository;
import com.corprag.service.access.AccessFilterResolver;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class DocumentQueryService {

    private final DocumentRepository documentRepository;
    private final AccessFilterResolver accessFilterResolver;

    public DocumentQueryService(
            DocumentRepository documentRepository,
            AccessFilterResolver accessFilterResolver) {
        this.documentRepository = documentRepository;
        this.accessFilterResolver = accessFilterResolver;
    }

    public DocumentPage listVisible(UUID actorUserId, DocumentSearchCriteria criteria, int page, int size) {
        ResolvedAccessFilter filter = accessFilterResolver.resolve(actorUserId);
        return documentRepository.pageVisibleDocuments(filter, criteria, size, Math.multiplyExact(page, size));
    }

    public DocumentRecord getVisible(UUID actorUserId, UUID documentId) {
        ResolvedAccessFilter filter = accessFilterResolver.resolve(actorUserId);
        return documentRepository.findVisibleById(documentId, filter)
                .orElseThrow(DocumentQueryService::notFound);
    }

    static ApiProblemException notFound() {
        return new ApiProblemException(ErrorCodes.DOCUMENT_NOT_FOUND, "Document not found");
    }
}
