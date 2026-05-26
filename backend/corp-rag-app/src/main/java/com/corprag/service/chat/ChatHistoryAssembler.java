package com.corprag.service.chat;

import com.corprag.domain.chat.AssistantMessageStatus;
import com.corprag.domain.chat.ChatMessage;
import com.corprag.domain.chat.ChatMessageRole;
import com.corprag.repository.ChatMessageRepository;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class ChatHistoryAssembler {

    static final int ANSWERED_PAIR_LIMIT = 10;

    private final ChatMessageRepository messageRepository;

    public ChatHistoryAssembler(ChatMessageRepository messageRepository) {
        this.messageRepository = messageRepository;
    }

    public List<ChatMessage> answeredPairHistory(UUID ownerUserId, UUID conversationId) {
        List<ChatMessage> rows = messageRepository.findAnsweredHistoryMessages(
                ownerUserId,
                conversationId,
                ANSWERED_PAIR_LIMIT);
        return completePairs(rows);
    }

    List<ChatMessage> completePairs(List<ChatMessage> rows) {
        Map<UUID, Pair> pairs = new LinkedHashMap<>();
        for (ChatMessage row : rows) {
            Pair pair = pairs.computeIfAbsent(row.correlationId(), ignored -> new Pair());
            if (row.role() == ChatMessageRole.USER) {
                pair.user = row;
            } else if (row.role() == ChatMessageRole.ASSISTANT && row.status() == AssistantMessageStatus.ANSWERED) {
                pair.assistant = row;
            }
        }

        List<ChatMessage> history = new ArrayList<>();
        for (Pair pair : pairs.values()) {
            if (pair.isComplete()) {
                history.add(pair.user);
                history.add(pair.assistant);
            }
        }
        return List.copyOf(history);
    }

    private static final class Pair {
        private ChatMessage user;
        private ChatMessage assistant;

        private boolean isComplete() {
            return user != null
                    && assistant != null
                    && user.content() != null
                    && assistant.content() != null;
        }
    }
}
