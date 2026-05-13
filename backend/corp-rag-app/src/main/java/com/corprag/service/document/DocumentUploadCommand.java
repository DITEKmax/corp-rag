package com.corprag.service.document;

import com.corprag.domain.AccessLevel;
import com.corprag.domain.DocType;
import java.util.UUID;
import org.springframework.web.multipart.MultipartFile;

public record DocumentUploadCommand(
        UUID actorUserId,
        String title,
        String description,
        AccessLevel accessLevel,
        String department,
        DocType docType,
        String language,
        MultipartFile file,
        String ipAddress,
        String userAgent) {
}
