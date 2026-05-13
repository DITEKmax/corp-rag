package com.corprag.adapter.rest;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.corprag.config.AppSecurityProperties;
import com.corprag.config.SecurityConfig;
import com.corprag.domain.AccessLevel;
import com.corprag.domain.DocType;
import com.corprag.domain.DocumentRecord;
import com.corprag.domain.DocumentStatus;
import com.corprag.service.document.DocumentUploadCommand;
import com.corprag.service.document.DocumentUploadService;
import com.corprag.testsupport.AuthTestFixtures;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

@WebMvcTest(controllers = DocumentController.class, properties = {
        "app.security.jwt.secret=test-only-phase-two-hs256-secret-never-use-in-runtime",
        "app.security.jwt.issuer=corp-rag-test",
        "app.security.cookies.secure=false"
})
@Import({DocumentAssembler.class, ProblemDetailsExceptionHandler.class, ProblemDetailsWriter.class, SecurityConfig.class})
class DocumentControllerTest {

    private static final UUID DOCUMENT_ID = UUID.fromString("d8f3a1c2-e89b-42d3-a456-426614174000");

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private AppSecurityProperties properties;

    @MockBean
    private DocumentUploadService uploadService;

    @Test
    void uploadRequiresDocumentsUploadPermission() throws Exception {
        mockMvc.perform(multipart("/api/v1/documents")
                        .file(file())
                        .param("title", "Policy")
                        .param("accessLevel", "INTERNAL")
                        .param("department", "HR")
                        .param("docType", "POLICY")
                        .param("language", "en")
                        .with(jwtWith(AuthTestFixtures.PERMISSION_DOCUMENTS_READ)))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.errorCode").value("INSUFFICIENT_PERMISSIONS"));

        verifyNoInteractions(uploadService);
    }

    @Test
    void uploadReturnsCreatedDocumentAndPassesValidatedCommand() throws Exception {
        when(uploadService.upload(any())).thenReturn(document());

        mockMvc.perform(multipart("/api/v1/documents")
                        .file(file())
                        .param("title", "Policy")
                        .param("description", "Upload test")
                        .param("accessLevel", "INTERNAL")
                        .param("department", "HR")
                        .param("docType", "POLICY")
                        .param("language", "en")
                        .with(jwtWith(AuthTestFixtures.PERMISSION_DOCUMENTS_UPLOAD)))
                .andExpect(status().isCreated())
                .andExpect(header().string(HttpHeaders.LOCATION, "/api/v1/documents/" + DOCUMENT_ID))
                .andExpect(jsonPath("$.id").value(DOCUMENT_ID.toString()))
                .andExpect(jsonPath("$.status").value("UPLOADED"))
                .andExpect(jsonPath("$._links.raw.href").value("/api/v1/documents/" + DOCUMENT_ID + "/raw"));

        ArgumentCaptor<DocumentUploadCommand> captor = ArgumentCaptor.forClass(DocumentUploadCommand.class);
        verify(uploadService).upload(captor.capture());
        org.assertj.core.api.Assertions.assertThat(captor.getValue().accessLevel()).isEqualTo(AccessLevel.INTERNAL);
        org.assertj.core.api.Assertions.assertThat(captor.getValue().department()).isEqualTo("HR");
        org.assertj.core.api.Assertions.assertThat(captor.getValue().docType()).isEqualTo(DocType.POLICY);
        org.assertj.core.api.Assertions.assertThat(captor.getValue().language()).isEqualTo("en");
    }

    private RequestPostProcessor jwtWith(String... permissions) {
        return jwt().jwt(token -> token
                .subject(AuthTestFixtures.ADMIN_USER_ID.toString())
                .claim("permissions", List.of(permissions))
                .claim("roles", List.of(AuthTestFixtures.ROLE_ADMIN))
                .claim("must_change_password", false)
                .issuer(properties.getJwt().getIssuer()));
    }

    private static MockMultipartFile file() {
        return new MockMultipartFile("file", "policy.txt", "text/plain", "plain text".getBytes());
    }

    private static DocumentRecord document() {
        return new DocumentRecord(
                DOCUMENT_ID,
                "Policy",
                "Upload test",
                "policy.txt",
                "text/plain",
                10,
                AccessLevel.INTERNAL,
                "HR",
                DocType.POLICY,
                "en",
                DocumentStatus.UPLOADED,
                AuthTestFixtures.ADMIN_USER_ID,
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
