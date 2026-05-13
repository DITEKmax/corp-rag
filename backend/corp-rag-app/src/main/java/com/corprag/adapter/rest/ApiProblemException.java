package com.corprag.adapter.rest;

import com.corprag.contracts.constants.ErrorCodes;
import java.util.Map;

public class ApiProblemException extends RuntimeException {

    private final ErrorCodes.ErrorCode errorCode;
    private final Map<String, Object> details;

    public ApiProblemException(ErrorCodes.ErrorCode errorCode, String detail) {
        this(errorCode, detail, Map.of());
    }

    public ApiProblemException(ErrorCodes.ErrorCode errorCode, String detail, Map<String, Object> details) {
        super(detail);
        this.errorCode = errorCode;
        this.details = details == null ? Map.of() : Map.copyOf(details);
    }

    public ErrorCodes.ErrorCode errorCode() {
        return errorCode;
    }

    public Map<String, Object> details() {
        return details;
    }
}
