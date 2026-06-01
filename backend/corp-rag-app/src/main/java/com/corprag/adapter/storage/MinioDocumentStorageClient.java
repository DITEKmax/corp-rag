package com.corprag.adapter.storage;

import com.corprag.config.DocumentStorageProperties;
import io.minio.BucketExistsArgs;
import io.minio.GetPresignedObjectUrlArgs;
import io.minio.MakeBucketArgs;
import io.minio.MinioClient;
import io.minio.PutObjectArgs;
import io.minio.http.Method;
import java.io.InputStream;
import java.net.URI;
import java.time.Duration;
import java.util.concurrent.TimeUnit;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class MinioDocumentStorageClient implements DocumentStorageClient {

    private final MinioClient minioClient;
    private final MinioClient publicMinioClient;
    private final DocumentStorageProperties properties;

    @Autowired
    public MinioDocumentStorageClient(MinioClient minioClient, DocumentStorageProperties properties) {
        this(
                minioClient,
                MinioClient.builder()
                        .endpoint(endpointWithScheme(properties.getPublicEndpoint(), properties.isSecure()))
                        .credentials(properties.getAccessKey(), properties.getSecretKey())
                        .build(),
                properties);
    }

    MinioDocumentStorageClient(
            MinioClient minioClient,
            MinioClient publicMinioClient,
            DocumentStorageProperties properties) {
        this.minioClient = minioClient;
        this.publicMinioClient = publicMinioClient;
        this.properties = properties;
    }

    @Override
    public void ensureBucket() {
        try {
            boolean exists = minioClient.bucketExists(BucketExistsArgs.builder()
                    .bucket(properties.getBucket())
                    .build());
            if (!exists) {
                minioClient.makeBucket(MakeBucketArgs.builder()
                        .bucket(properties.getBucket())
                        .build());
            }
        } catch (Exception exception) {
            throw new DocumentStorageException("Could not ensure document storage bucket", exception);
        }
    }

    @Override
    public void putObject(String objectKey, String contentType, long sizeBytes, InputStream content) {
        try {
            minioClient.putObject(PutObjectArgs.builder()
                    .bucket(properties.getBucket())
                    .object(objectKey)
                    .contentType(contentType)
                    .stream(content, sizeBytes, -1)
                    .build());
        } catch (Exception exception) {
            throw new DocumentStorageException("Could not store document object", exception);
        }
    }

    @Override
    public URI presignedGetUrl(String objectKey, Duration ttl) {
        try {
            String url = publicMinioClient.getPresignedObjectUrl(GetPresignedObjectUrlArgs.builder()
                    .method(Method.GET)
                    .bucket(properties.getBucket())
                    .object(objectKey)
                    .expiry(Math.toIntExact(ttl.toSeconds()), TimeUnit.SECONDS)
                    .build());
            return URI.create(url);
        } catch (Exception exception) {
            throw new DocumentStorageException("Could not create document object URL", exception);
        }
    }

    private static String endpointWithScheme(String endpoint, boolean secure) {
        if (endpoint.startsWith("http://") || endpoint.startsWith("https://")) {
            return endpoint;
        }
        return (secure ? "https://" : "http://") + endpoint;
    }
}
