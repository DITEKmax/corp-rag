package com.corprag.service.document;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.corprag.adapter.rest.ApiProblemException;
import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.domain.AccessLevel;
import com.corprag.domain.DocType;
import com.corprag.domain.DocumentPage;
import com.corprag.domain.DocumentRecord;
import com.corprag.domain.DocumentSearchCriteria;
import com.corprag.domain.DocumentStatus;
import com.corprag.domain.ResolvedAccessFilter;
import com.corprag.repository.DocumentRepository;
import com.corprag.service.access.AccessFilterResolver;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class DocumentQueryServiceTest {

    private static final UUID ACTOR_ID = UUID.fromString("11111111-1111-4111-8111-111111111111");
    private static final UUID DOCUMENT_ID = UUID.fromString("d8f3a1c2-e89b-42d3-a456-426614174000");
    private static final ResolvedAccessFilter FILTER = new ResolvedAccessFilter(
            List.of(AccessLevel.PUBLIC, AccessLevel.INTERNAL),
            List.of("HR"),
            List.of(DocType.POLICY));

    private final DocumentRepository documentRepository = mock(DocumentRepository.class);
    private final AccessFilterResolver accessFilterResolver = mock(AccessFilterResolver.class);
    private final DocumentQueryService service = new DocumentQueryService(documentRepository, accessFilterResolver);

    @Test
    void listVisibleResolvesAccessFilterBeforeRepositoryPaging() {
        DocumentSearchCriteria criteria = new DocumentSearchCriteria(DocumentStatus.UPLOADED, "HR", DocType.POLICY, "en", "policy");
        DocumentPage expected = new DocumentPage(List.of(document()), 1);
        when(accessFilterResolver.resolve(ACTOR_ID)).thenReturn(FILTER);
        when(documentRepository.pageVisibleDocuments(FILTER, criteria, 25, 50)).thenReturn(expected);

        assertThat(service.listVisible(ACTOR_ID, criteria, 2, 25)).isEqualTo(expected);

        verify(accessFilterResolver).resolve(ACTOR_ID);
        verify(documentRepository).pageVisibleDocuments(FILTER, criteria, 25, 50);
    }

    @Test
    void getVisibleReturnsDocumentInsideResolvedFilter() {
        DocumentRecord document = document();
        when(accessFilterResolver.resolve(ACTOR_ID)).thenReturn(FILTER);
        when(documentRepository.findVisibleById(DOCUMENT_ID, FILTER)).thenReturn(Optional.of(document));

        assertThat(service.getVisible(ACTOR_ID, DOCUMENT_ID)).isEqualTo(document);
    }

    @Test
    void getVisibleMapsInvisibleExistingDocumentToDocumentNotFound() {
        when(accessFilterResolver.resolve(ACTOR_ID)).thenReturn(FILTER);
        when(documentRepository.findVisibleById(DOCUMENT_ID, FILTER)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.getVisible(ACTOR_ID, DOCUMENT_ID))
                .isInstanceOf(ApiProblemException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCodes.DOCUMENT_NOT_FOUND);
    }

    private static DocumentRecord document() {
        return new DocumentRecord(
                DOCUMENT_ID,
                "Policy",
                null,
                "policy.txt",
                "text/plain",
                10,
                AccessLevel.INTERNAL,
                "HR",
                DocType.POLICY,
                "en",
                DocumentStatus.UPLOADED,
                ACTOR_ID,
                "corp-rag-documents",
                "2026/05/" + DOCUMENT_ID + ".txt",
                "0".repeat(64),
                Instant.parse("2026-05-13T12:00:00Z"),
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
}
