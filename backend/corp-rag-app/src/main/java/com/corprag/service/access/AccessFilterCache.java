package com.corprag.service.access;

import com.corprag.domain.ResolvedAccessFilter;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import org.springframework.stereotype.Service;

@Service
public class AccessFilterCache {

    static final Duration DEFAULT_TTL = Duration.ofSeconds(60);

    private final Clock clock;
    private final Duration ttl;
    private final ConcurrentMap<UUID, CacheEntry> entries = new ConcurrentHashMap<>();

    public AccessFilterCache() {
        this(Clock.systemUTC(), DEFAULT_TTL);
    }

    AccessFilterCache(Clock clock, Duration ttl) {
        this.clock = clock;
        this.ttl = ttl;
    }

    Optional<ResolvedAccessFilter> get(UUID userId) {
        CacheEntry entry = entries.get(userId);
        if (entry == null) {
            return Optional.empty();
        }
        if (entry.expiresAt().isAfter(clock.instant())) {
            return Optional.of(entry.filter());
        }
        entries.remove(userId, entry);
        return Optional.empty();
    }

    void put(UUID userId, ResolvedAccessFilter filter) {
        entries.put(userId, new CacheEntry(filter, clock.instant().plus(ttl)));
    }

    public void invalidate(UUID userId) {
        entries.remove(userId);
    }

    private record CacheEntry(ResolvedAccessFilter filter, Instant expiresAt) {
    }
}
