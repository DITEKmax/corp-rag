package com.corprag.adapter.storage;

import java.io.InputStream;
import java.net.URI;
import java.time.Duration;

public interface DocumentStorageClient {

    void ensureBucket();

    void putObject(String objectKey, String contentType, long sizeBytes, InputStream content);

    URI presignedGetUrl(String objectKey, Duration ttl);
}
