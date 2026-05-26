package com.corprag.adapter.rest;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.corprag.config.AppSecurityProperties;
import com.corprag.config.SecurityConfig;
import com.corprag.contracts.api.v1.model.AssistantMessageStatus;
import com.corprag.contracts.api.v1.model.Conversation;
import com.corprag.contracts.api.v1.model.ConversationRole;
import com.corprag.contracts.api.v1.model.Message;
import com.corprag.contracts.api.v1.model.PagedConversations;
import com.corprag.contracts.api.v1.model.PagedMessages;
import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.service.chat.ChatConversationService;
import com.corprag.testsupport.AuthTestFixtures;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

@WebMvcTest(controllers = ChatController.class, properties = {
        "app.security.jwt.secret=test-only-phase-two-hs256-secret-never-use-in-runtime",
        "app.security.jwt.issuer=corp-rag-test",
        "app.security.cookies.secure=false"
})
@Import({ProblemDetailsExceptionHandler.class, ProblemDetailsWriter.class, SecurityConfig.class})
class ChatControllerTest {

    private static final UUID CONVERSATION_ID = UUID.fromString("c1234567-e89b-12d3-a456-426614174000");
    private static final UUID MESSAGE_ID = UUID.fromString("11111111-1111-4111-8111-111111111001");
    private static final OffsetDateTime CREATED_AT = OffsetDateTime.parse("2026-05-21T10:00:00Z");

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private AppSecurityProperties properties;

    @MockBean
    private ChatConversationService conversationService;

    @Test
    void listRequiresChatQueryPermission() throws Exception {
        mockMvc.perform(get("/api/v1/chat/conversations")
                        .with(jwtWith(AuthTestFixtures.PERMISSION_DOCUMENTS_READ)))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.errorCode").value("INSUFFICIENT_PERMISSIONS"));

        verifyNoInteractions(conversationService);
    }

    @Test
    void listReturnsConversationPageForCurrentUser() throws Exception {
        when(conversationService.list(AuthTestFixtures.ADMIN_USER_ID, 1, 5))
                .thenReturn(new PagedConversations()
                        .items(List.of(conversation()))
                        .page(1)
                        .size(5)
                        .total(1L)
                        .links(Map.of()));

        mockMvc.perform(get("/api/v1/chat/conversations")
                        .param("page", "1")
                        .param("size", "5")
                        .with(jwtWith(AuthTestFixtures.PERMISSION_CHAT_QUERY)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items[0].id").value(CONVERSATION_ID.toString()))
                .andExpect(jsonPath("$.items[0].title").value("HR policy"))
                .andExpect(jsonPath("$.items[0].messageCount").value(2))
                .andExpect(jsonPath("$.total").value(1));
    }

    @Test
    void createReturnsCreatedConversationAndPassesRequestToService() throws Exception {
        when(conversationService.create(eq(AuthTestFixtures.ADMIN_USER_ID), any()))
                .thenReturn(conversation());

        mockMvc.perform(post("/api/v1/chat/conversations")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"title\":\"HR policy\"}")
                        .with(jwtWith(AuthTestFixtures.PERMISSION_CHAT_QUERY)))
                .andExpect(status().isCreated())
                .andExpect(header().string(HttpHeaders.LOCATION, "/api/v1/chat/conversations/" + CONVERSATION_ID))
                .andExpect(jsonPath("$.id").value(CONVERSATION_ID.toString()));

        ArgumentCaptor<com.corprag.contracts.api.v1.model.CreateConversationRequest> captor =
                ArgumentCaptor.forClass(com.corprag.contracts.api.v1.model.CreateConversationRequest.class);
        verify(conversationService).create(eq(AuthTestFixtures.ADMIN_USER_ID), captor.capture());
        org.assertj.core.api.Assertions.assertThat(captor.getValue().getTitle()).isEqualTo("HR policy");
    }

    @Test
    void getMapsMissingOrForeignConversationToConversationNotFound() throws Exception {
        when(conversationService.get(AuthTestFixtures.ADMIN_USER_ID, CONVERSATION_ID))
                .thenThrow(new ApiProblemException(ErrorCodes.CONVERSATION_NOT_FOUND, "Conversation not found"));

        mockMvc.perform(get("/api/v1/chat/conversations/{conversationId}", CONVERSATION_ID)
                        .with(jwtWith(AuthTestFixtures.PERMISSION_CHAT_QUERY)))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.errorCode").value("CONVERSATION_NOT_FOUND"));
    }

    @Test
    void deleteReturnsNoContentAndIsDelegatedToService() throws Exception {
        mockMvc.perform(delete("/api/v1/chat/conversations/{conversationId}", CONVERSATION_ID)
                        .with(jwtWith(AuthTestFixtures.PERMISSION_CHAT_QUERY)))
                .andExpect(status().isNoContent());

        verify(conversationService).delete(AuthTestFixtures.ADMIN_USER_ID, CONVERSATION_ID);
    }

    @Test
    void deleteMissingConversationReturnsConversationNotFound() throws Exception {
        doThrow(new ApiProblemException(ErrorCodes.CONVERSATION_NOT_FOUND, "Conversation not found"))
                .when(conversationService)
                .delete(AuthTestFixtures.ADMIN_USER_ID, CONVERSATION_ID);

        mockMvc.perform(delete("/api/v1/chat/conversations/{conversationId}", CONVERSATION_ID)
                        .with(jwtWith(AuthTestFixtures.PERMISSION_CHAT_QUERY)))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.errorCode").value("CONVERSATION_NOT_FOUND"));
    }

    @Test
    void listMessagesReturnsFailedAssistantOutcomesVisibleToOwner() throws Exception {
        when(conversationService.listMessages(AuthTestFixtures.ADMIN_USER_ID, CONVERSATION_ID, 0, 20))
                .thenReturn(new PagedMessages()
                        .items(List.of(timeoutMessage()))
                        .page(0)
                        .size(20)
                        .total(1L)
                        .links(Map.of()));

        mockMvc.perform(get("/api/v1/chat/conversations/{conversationId}/messages", CONVERSATION_ID)
                        .with(jwtWith(AuthTestFixtures.PERMISSION_CHAT_QUERY)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items[0].role").value("assistant"))
                .andExpect(jsonPath("$.items[0].status").value("TIMEOUT"))
                .andExpect(jsonPath("$.items[0].content").doesNotExist())
                .andExpect(jsonPath("$.items[0].citations").doesNotExist());
    }

    @Test
    void deferredCitationDetailsEndpointIsNotImplementedInPhaseSix() throws Exception {
        mockMvc.perform(get("/api/v1/chat/messages/{messageId}/citations", MESSAGE_ID)
                        .with(jwtWith(AuthTestFixtures.PERMISSION_CHAT_QUERY)))
                .andExpect(status().isNotFound());
    }

    private RequestPostProcessor jwtWith(String... permissions) {
        return jwt().jwt(token -> token
                .subject(AuthTestFixtures.ADMIN_USER_ID.toString())
                .claim("permissions", List.of(permissions))
                .claim("roles", List.of(AuthTestFixtures.ROLE_ADMIN))
                .claim("must_change_password", false)
                .issuer(properties.getJwt().getIssuer()));
    }

    private static Conversation conversation() {
        return new Conversation()
                .id(CONVERSATION_ID)
                .userId(AuthTestFixtures.ADMIN_USER_ID)
                .title("HR policy")
                .createdAt(CREATED_AT)
                .updatedAt(CREATED_AT)
                .messageCount(2)
                .links(Map.of());
    }

    private static Message timeoutMessage() {
        return new Message()
                .id(MESSAGE_ID)
                .conversationId(CONVERSATION_ID)
                .role(ConversationRole.ASSISTANT)
                .status(AssistantMessageStatus.TIMEOUT)
                .content(null)
                .citations(null)
                .createdAt(CREATED_AT)
                .links(Map.of());
    }
}
