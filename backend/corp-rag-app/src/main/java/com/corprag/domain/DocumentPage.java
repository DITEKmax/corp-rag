package com.corprag.domain;

import java.util.List;

public record DocumentPage(
        List<DocumentRecord> documents,
        long total) {
}
