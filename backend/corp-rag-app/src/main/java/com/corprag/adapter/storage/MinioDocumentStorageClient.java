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
import org.springframework.stereotype.Component;

@Component
public class MinioDocumentStorageClient implements DocumentStorageClient {

    private final MinioClient minioClient;
    private final DocumentStorageProperties properties;

    public MinioDocumentStorageClient(MinioClient minioClient, DocumentStorageProperties properties) {
        this.minioClient = minioClient;
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
            String url = minioClient.getPresignedObjectUrl(GetPresignedObjectUrlArgs.builder()
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
}
