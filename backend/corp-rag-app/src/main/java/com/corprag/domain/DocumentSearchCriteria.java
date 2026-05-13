package com.corprag.domain;

public record DocumentSearchCriteria(
        DocumentStatus status,
        String department,
        DocType docType,
        String language,
        String search) {

    public static DocumentSearchCriteria empty() {
        return new DocumentSearchCriteria(null, null, null, null, null);
    }
}
