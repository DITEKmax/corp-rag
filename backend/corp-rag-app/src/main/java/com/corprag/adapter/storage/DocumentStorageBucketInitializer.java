package com.corprag.adapter.storage;

import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(prefix = "app.document-storage", name = "initialize-bucket", havingValue = "true")
public class DocumentStorageBucketInitializer implements ApplicationRunner {

    private final DocumentStorageClient storageClient;

    public DocumentStorageBucketInitializer(DocumentStorageClient storageClient) {
        this.storageClient = storageClient;
    }

    @Override
    public void run(ApplicationArguments args) {
        storageClient.ensureBucket();
    }
}
