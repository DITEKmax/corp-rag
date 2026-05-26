package com.corprag.domain.chat;

import java.util.List;

public record ChatRetrievalMetaSnapshot(
        String route,
        List<String> retrieversAttempted,
        List<String> retrieversUsed,
        List<String> degradationWarnings,
        Long latencyMs,
        Integer chunksConsidered,
        Integer chunksReturned,
        Boolean rerankerUsed,
        String modelId) {
}
