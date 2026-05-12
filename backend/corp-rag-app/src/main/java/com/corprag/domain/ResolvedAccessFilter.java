package com.corprag.domain;

import java.util.List;

public record ResolvedAccessFilter(
        List<AccessLevel> accessLevels,
        List<String> departments,
        List<DocType> docTypes) {
}
