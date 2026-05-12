package com.corprag.adapter.rest;

import com.corprag.contracts.constants.ErrorCodes;

public class ApiProblemException extends RuntimeException {

    private final ErrorCodes.ErrorCode errorCode;

    public ApiProblemException(ErrorCodes.ErrorCode errorCode, String detail) {
        super(detail);
        this.errorCode = errorCode;
    }

    public ErrorCodes.ErrorCode errorCode() {
        return errorCode;
    }
}
