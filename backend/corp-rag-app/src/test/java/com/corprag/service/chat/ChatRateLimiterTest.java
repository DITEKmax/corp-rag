package com.corprag.service.chat;

import static org.assertj.core.api.Assertions.assertThat;

import com.corprag.adapter.rest.ProblemDetailsWriter;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

class ChatRateLimiterTest {

    @Test
    void allowsThirtyRequestsPerMinuteThenReturnsRetryAfter() {
        MutableClock clock = new MutableClock(Instant.parse("2026-05-21T10:00:00Z"));
        ChatRateLimiter limiter = new ChatRateLimiter(clock, 30, Duration.ofMinutes(1), Duration.ofMinutes(10));
        UUID userId = UUID.randomUUID();

        for (int index = 0; index < 30; index++) {
            assertThat(limiter.tryAcquire(userId).allowed()).isTrue();
        }

        ChatRateLimiter.Decision denied = limiter.tryAcquire(userId);
        assertThat(denied.allowed()).isFalse();
        assertThat(denied.retryAfterSeconds()).isPositive();

        clock.advance(Duration.ofSeconds(2));
        assertThat(limiter.tryAcquire(userId).allowed()).isTrue();
    }

    @Test
    void usersHaveIndependentBucketsAndStaleEntriesAreCleaned() {
        MutableClock clock = new MutableClock(Instant.parse("2026-05-21T11:00:00Z"));
        ChatRateLimiter limiter = new ChatRateLimiter(clock, 1, Duration.ofMinutes(1), Duration.ofMinutes(5));
        UUID firstUser = UUID.randomUUID();
        UUID secondUser = UUID.randomUUID();

        assertThat(limiter.tryAcquire(firstUser).allowed()).isTrue();
        assertThat(limiter.tryAcquire(firstUser).allowed()).isFalse();
        assertThat(limiter.tryAcquire(secondUser).allowed()).isTrue();
        assertThat(limiter.bucketCount()).isEqualTo(2);

        clock.advance(Duration.ofMinutes(6));
        limiter.tryAcquire(UUID.randomUUID());
        assertThat(limiter.bucketCount()).isEqualTo(1);
    }

    @Test
    void concurrentCallsCannotOvershootCapacity() throws InterruptedException {
        ChatRateLimiter limiter = new ChatRateLimiter(
                new MutableClock(Instant.parse("2026-05-21T12:00:00Z")),
                30,
                Duration.ofMinutes(1),
                Duration.ofMinutes(10));
        UUID userId = UUID.randomUUID();
        int workers = 80;
        CountDownLatch ready = new CountDownLatch(workers);
        CountDownLatch start = new CountDownLatch(1);
        AtomicInteger allowed = new AtomicInteger();
        var executor = Executors.newFixedThreadPool(workers);

        for (int index = 0; index < workers; index++) {
            executor.submit(() -> {
                ready.countDown();
                try {
                    start.await(5, TimeUnit.SECONDS);
                } catch (InterruptedException exception) {
                    Thread.currentThread().interrupt();
                }
                if (limiter.tryAcquire(userId).allowed()) {
                    allowed.incrementAndGet();
                }
            });
        }

        assertThat(ready.await(5, TimeUnit.SECONDS)).isTrue();
        start.countDown();
        executor.shutdown();
        assertThat(executor.awaitTermination(10, TimeUnit.SECONDS)).isTrue();
        assertThat(allowed).hasValue(30);
    }

    @Test
    void rateLimitProblemWriterUsesProjectProblemDetailsAndRetryAfterHeader() throws Exception {
        ChatRateLimitProblemWriter writer =
                new ChatRateLimitProblemWriter(new ProblemDetailsWriter(new ObjectMapper()));
        MockHttpServletResponse response = new MockHttpServletResponse();
        MockHttpServletRequest request = new MockHttpServletRequest("POST", "/api/v1/chat/query");

        writer.write(response, request, ChatRateLimiter.Decision.denied(12));

        assertThat(response.getStatus()).isEqualTo(429);
        assertThat(response.getHeader("Retry-After")).isEqualTo("12");
        assertThat(response.getContentAsString()).contains("RATE_LIMIT_EXCEEDED", "retryAfterSeconds", "correlationId");
    }

    private static final class MutableClock extends Clock {
        private Instant instant;

        private MutableClock(Instant instant) {
            this.instant = instant;
        }

        private void advance(Duration duration) {
            instant = instant.plus(duration);
        }

        @Override
        public ZoneId getZone() {
            return ZoneId.of("UTC");
        }

        @Override
        public Clock withZone(ZoneId zone) {
            return this;
        }

        @Override
        public Instant instant() {
            return instant;
        }
    }
}
