package com.corprag.domain;

public enum AccessLevel {
    PUBLIC(0),
    INTERNAL(1),
    CONFIDENTIAL(2),
    RESTRICTED(3);

    private final int rank;

    AccessLevel(int rank) {
        this.rank = rank;
    }

    public int rank() {
        return rank;
    }
}
