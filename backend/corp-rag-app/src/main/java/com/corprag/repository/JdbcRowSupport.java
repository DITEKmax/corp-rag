package com.corprag.repository;

import java.sql.Array;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.Arrays;
import java.util.List;

final class JdbcRowSupport {

    private JdbcRowSupport() {
    }

    static Instant instant(ResultSet resultSet, String column) throws SQLException {
        Timestamp timestamp = resultSet.getTimestamp(column);
        return timestamp == null ? null : timestamp.toInstant();
    }

    static Timestamp timestamp(Instant value) {
        return value == null ? null : Timestamp.from(value);
    }

    static List<String> stringArray(ResultSet resultSet, String column) throws SQLException {
        Array array = resultSet.getArray(column);
        if (array == null) {
            return List.of();
        }
        return Arrays.asList((String[]) array.getArray());
    }
}
