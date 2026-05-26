package com.corprag.adapter.rest;

import com.corprag.contracts.api.v1.model.Conversation;
import com.corprag.contracts.api.v1.model.CreateConversationRequest;
import com.corprag.contracts.api.v1.model.PagedConversations;
import com.corprag.contracts.api.v1.model.PagedMessages;
import com.corprag.security.Permission;
import com.corprag.service.chat.ChatConversationService;
import jakarta.validation.Valid;
import java.net.URI;
import java.util.UUID;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/chat")
public class ChatController {

    private final ChatConversationService conversationService;

    public ChatController(ChatConversationService conversationService) {
        this.conversationService = conversationService;
    }

    @GetMapping("/conversations")
    ResponseEntity<PagedConversations> listConversations(
            @AuthenticationPrincipal Jwt jwt,
            @RequestParam(value = "page", defaultValue = "0") int page,
            @RequestParam(value = "size", defaultValue = "20") int size) {
        JwtAuthorization.requirePermission(jwt, Permission.CHAT_QUERY.value());
        return ResponseEntity.ok(conversationService.list(JwtAuthorization.userId(jwt), page, size));
    }

    @PostMapping("/conversations")
    ResponseEntity<Conversation> createConversation(
            @AuthenticationPrincipal Jwt jwt,
            @Valid @RequestBody(required = false) CreateConversationRequest request) {
        JwtAuthorization.requirePermission(jwt, Permission.CHAT_QUERY.value());
        Conversation conversation = conversationService.create(JwtAuthorization.userId(jwt), request);
        return ResponseEntity.created(URI.create("/api/v1/chat/conversations/" + conversation.getId()))
                .body(conversation);
    }

    @GetMapping("/conversations/{conversationId}")
    ResponseEntity<Conversation> getConversation(
            @AuthenticationPrincipal Jwt jwt,
            @PathVariable("conversationId") UUID conversationId) {
        JwtAuthorization.requirePermission(jwt, Permission.CHAT_QUERY.value());
        return ResponseEntity.ok(conversationService.get(JwtAuthorization.userId(jwt), conversationId));
    }

    @DeleteMapping("/conversations/{conversationId}")
    ResponseEntity<Void> deleteConversation(
            @AuthenticationPrincipal Jwt jwt,
            @PathVariable("conversationId") UUID conversationId) {
        JwtAuthorization.requirePermission(jwt, Permission.CHAT_QUERY.value());
        conversationService.delete(JwtAuthorization.userId(jwt), conversationId);
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/conversations/{conversationId}/messages")
    ResponseEntity<PagedMessages> listMessages(
            @AuthenticationPrincipal Jwt jwt,
            @PathVariable("conversationId") UUID conversationId,
            @RequestParam(value = "page", defaultValue = "0") int page,
            @RequestParam(value = "size", defaultValue = "20") int size) {
        JwtAuthorization.requirePermission(jwt, Permission.CHAT_QUERY.value());
        return ResponseEntity.ok(conversationService.listMessages(
                JwtAuthorization.userId(jwt),
                conversationId,
                page,
                size));
    }
}
