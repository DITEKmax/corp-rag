package com.corprag.adapter.storage;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.corprag.config.DocumentStorageProperties;
import io.minio.BucketExistsArgs;
import io.minio.GetPresignedObjectUrlArgs;
import io.minio.MakeBucketArgs;
import io.minio.MinioClient;
import java.net.URI;
import java.time.Duration;
import org.junit.jupiter.api.Test;

class MinioDocumentStorageClientTest {

    @Test
    void ensureBucketDoesNothingWhenBucketAlreadyExists() throws Exception {
        MinioClient minioClient = mock(MinioClient.class);
        when(minioClient.bucketExists(any(BucketExistsArgs.class))).thenReturn(true);
        DocumentStorageProperties properties = new DocumentStorageProperties();
        properties.setBucket("corp-rag-documents");

        new MinioDocumentStorageClient(minioClient, properties).ensureBucket();

        verify(minioClient).bucketExists(any(BucketExistsArgs.class));
        verify(minioClient, never()).makeBucket(any(MakeBucketArgs.class));
    }

    @Test
    void presignedGetUrlUsesPublicEndpointClientOnly() throws Exception {
        MinioClient internalClient = mock(MinioClient.class);
        MinioClient publicClient = mock(MinioClient.class);
        DocumentStorageProperties properties = new DocumentStorageProperties();
        properties.setBucket("corp-rag-documents");
        when(publicClient.getPresignedObjectUrl(any(GetPresignedObjectUrlArgs.class)))
                .thenReturn("http://localhost:9000/corp-rag-documents/file.txt?signature=test");

        URI result = new MinioDocumentStorageClient(internalClient, publicClient, properties)
                .presignedGetUrl("file.txt", Duration.ofMinutes(5));

        verify(publicClient).getPresignedObjectUrl(any(GetPresignedObjectUrlArgs.class));
        verify(internalClient, never()).getPresignedObjectUrl(any(GetPresignedObjectUrlArgs.class));
        org.assertj.core.api.Assertions.assertThat(result)
                .isEqualTo(URI.create("http://localhost:9000/corp-rag-documents/file.txt?signature=test"));
    }
}
