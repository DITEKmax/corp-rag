package com.corprag.config;

import io.minio.MinioClient;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
@EnableConfigurationProperties(DocumentStorageProperties.class)
public class DocumentStorageConfig {

    @Bean
    MinioClient minioClient(DocumentStorageProperties properties) {
        String endpoint = properties.getEndpoint();
        if (!endpoint.startsWith("http://") && !endpoint.startsWith("https://")) {
            endpoint = (properties.isSecure() ? "https://" : "http://") + endpoint;
        }
        return MinioClient.builder()
                .endpoint(endpoint)
                .region(properties.getRegion())
                .credentials(properties.getAccessKey(), properties.getSecretKey())
                .build();
    }
}
