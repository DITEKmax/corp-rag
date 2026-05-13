package com.corprag.config;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app.outbox-publisher")
public class OutboxPublisherProperties {

    private boolean enabled;
    private int batchSize = 50;
    private long initialDelayMs = 5000;
    private long pollDelayMs = 5000;
    private Duration initialBackoff = Duration.ofSeconds(1);
    private Duration maxBackoff = Duration.ofMinutes(5);
    private boolean cleanupEnabled = true;
    private long cleanupInitialDelayMs = 60000;
    private long cleanupDelayMs = 3600000;
    private Duration retention = Duration.ofDays(7);

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public int getBatchSize() {
        return batchSize;
    }

    public void setBatchSize(int batchSize) {
        this.batchSize = batchSize;
    }

    public long getInitialDelayMs() {
        return initialDelayMs;
    }

    public void setInitialDelayMs(long initialDelayMs) {
        this.initialDelayMs = initialDelayMs;
    }

    public long getPollDelayMs() {
        return pollDelayMs;
    }

    public void setPollDelayMs(long pollDelayMs) {
        this.pollDelayMs = pollDelayMs;
    }

    public Duration getInitialBackoff() {
        return initialBackoff;
    }

    public void setInitialBackoff(Duration initialBackoff) {
        this.initialBackoff = initialBackoff;
    }

    public Duration getMaxBackoff() {
        return maxBackoff;
    }

    public void setMaxBackoff(Duration maxBackoff) {
        this.maxBackoff = maxBackoff;
    }

    public boolean isCleanupEnabled() {
        return cleanupEnabled;
    }

    public void setCleanupEnabled(boolean cleanupEnabled) {
        this.cleanupEnabled = cleanupEnabled;
    }

    public long getCleanupInitialDelayMs() {
        return cleanupInitialDelayMs;
    }

    public void setCleanupInitialDelayMs(long cleanupInitialDelayMs) {
        this.cleanupInitialDelayMs = cleanupInitialDelayMs;
    }

    public long getCleanupDelayMs() {
        return cleanupDelayMs;
    }

    public void setCleanupDelayMs(long cleanupDelayMs) {
        this.cleanupDelayMs = cleanupDelayMs;
    }

    public Duration getRetention() {
        return retention;
    }

    public void setRetention(Duration retention) {
        this.retention = retention;
    }
}
