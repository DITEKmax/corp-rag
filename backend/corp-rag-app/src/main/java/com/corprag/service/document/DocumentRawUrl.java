package com.corprag.service.document;

import java.net.URI;
import java.time.Instant;

public record DocumentRawUrl(
        URI url,
        Instant expiresAt) {
}
