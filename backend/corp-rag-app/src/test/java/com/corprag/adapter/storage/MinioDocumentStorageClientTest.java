package com.corprag.adapter.storage;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.corprag.config.DocumentStorageProperties;
import io.minio.BucketExistsArgs;
import io.minio.MakeBucketArgs;
import io.minio.MinioClient;
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
}
