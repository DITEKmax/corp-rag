package com.corprag.config;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app.document-storage")
public class DocumentStorageProperties {

    private String endpoint = "http://localhost:9000";
    private String accessKey = "local-minio-root";
    private String secretKey = "local-minio-password";
    private boolean secure;
    private String bucket = "corp-rag-documents";
    private Duration rawUrlTtl = Duration.ofMinutes(5);

    public String getEndpoint() {
        return endpoint;
    }

    public void setEndpoint(String endpoint) {
        this.endpoint = endpoint;
    }

    public String getAccessKey() {
        return accessKey;
    }

    public void setAccessKey(String accessKey) {
        this.accessKey = accessKey;
    }

    public String getSecretKey() {
        return secretKey;
    }

    public void setSecretKey(String secretKey) {
        this.secretKey = secretKey;
    }

    public boolean isSecure() {
        return secure;
    }

    public void setSecure(boolean secure) {
        this.secure = secure;
    }

    public String getBucket() {
        return bucket;
    }

    public void setBucket(String bucket) {
        this.bucket = bucket;
    }

    public Duration getRawUrlTtl() {
        return rawUrlTtl;
    }

    public void setRawUrlTtl(Duration rawUrlTtl) {
        this.rawUrlTtl = rawUrlTtl;
    }
}
