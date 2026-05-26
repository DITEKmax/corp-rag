package com.corprag.domain.chat;

import com.corprag.domain.AccessLevel;
import java.math.BigDecimal;
import java.util.UUID;

public record ChatCitationSnapshot(
        UUID documentId,
        String documentTitle,
        UUID chunkId,
        String sectionPath,
        String quote,
        String snippet,
        Integer pageNumber,
        BigDecimal score,
        AccessLevel accessLevel) {
}
