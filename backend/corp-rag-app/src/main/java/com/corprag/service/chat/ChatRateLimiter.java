package com.corprag.service.chat;

import java.time.Clock;
import java.time.Duration;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;
import org.springframework.stereotype.Service;

@Service
public class ChatRateLimiter {

    static final int DEFAULT_LIMIT = 30;
    static final Duration DEFAULT_WINDOW = Duration.ofMinutes(1);
    private static final Duration DEFAULT_STALE_AFTER = Duration.ofMinutes(10);

    private final Clock clock;
    private final int capacity;
    private final long windowMillis;
    private final long staleAfterMillis;
    private final ConcurrentHashMap<UUID, Bucket> buckets = new ConcurrentHashMap<>();
    private final AtomicLong lastCleanupMillis;

    public ChatRateLimiter() {
        this(Clock.systemUTC(), DEFAULT_LIMIT, DEFAULT_WINDOW, DEFAULT_STALE_AFTER);
    }

    ChatRateLimiter(Clock clock, int capacity, Duration window, Duration staleAfter) {
        if (capacity <= 0) {
            throw new IllegalArgumentException("rate limit capacity must be positive");
        }
        if (window.isZero() || window.isNegative()) {
            throw new IllegalArgumentException("rate limit window must be positive");
        }
        this.clock = clock;
        this.capacity = capacity;
        this.windowMillis = window.toMillis();
        this.staleAfterMillis = staleAfter.toMillis();
        this.lastCleanupMillis = new AtomicLong(clock.millis());
    }

    public Decision tryAcquire(UUID userId) {
        long now = clock.millis();
        cleanupStale(now);
        Bucket bucket = buckets.computeIfAbsent(userId, ignored -> new Bucket(capacity, now));
        return bucket.tryAcquire(now, capacity, windowMillis);
    }

    int bucketCount() {
        return buckets.size();
    }

    private void cleanupStale(long now) {
        long lastCleanup = lastCleanupMillis.get();
        if (now - lastCleanup < staleAfterMillis) {
            return;
        }
        if (!lastCleanupMillis.compareAndSet(lastCleanup, now)) {
            return;
        }
        buckets.entrySet().removeIf(entry -> entry.getValue().isStale(now, staleAfterMillis));
    }

    public record Decision(boolean allowed, long retryAfterSeconds) {
        public static Decision permitted() {
            return new Decision(true, 0);
        }

        public static Decision denied(long retryAfterSeconds) {
            return new Decision(false, Math.max(1, retryAfterSeconds));
        }
    }

    private static final class Bucket {
        private double tokens;
        private long lastRefillMillis;
        private volatile long lastSeenMillis;

        private Bucket(int capacity, long now) {
            this.tokens = capacity;
            this.lastRefillMillis = now;
            this.lastSeenMillis = now;
        }

        private synchronized Decision tryAcquire(long now, int capacity, long windowMillis) {
            refill(now, capacity, windowMillis);
            lastSeenMillis = now;
            if (tokens >= 1.0d) {
                tokens -= 1.0d;
                return Decision.permitted();
            }
            double missingTokens = 1.0d - tokens;
            long retryAfterMillis = (long) Math.ceil(missingTokens * windowMillis / capacity);
            long retryAfterSeconds = (long) Math.ceil(retryAfterMillis / 1000.0d);
            return Decision.denied(retryAfterSeconds);
        }

        private boolean isStale(long now, long staleAfterMillis) {
            return now - lastSeenMillis >= staleAfterMillis;
        }

        private void refill(long now, int capacity, long windowMillis) {
            long elapsed = Math.max(0, now - lastRefillMillis);
            if (elapsed == 0) {
                return;
            }
            double refillTokens = (elapsed * (double) capacity) / windowMillis;
            tokens = Math.min(capacity, tokens + refillTokens);
            lastRefillMillis = now;
        }
    }
}
