package com.corprag.adapter.rest;

import com.corprag.contracts.api.v1.model.ProblemDetail;
import com.corprag.contracts.constants.ErrorCodes;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class ProblemDetailsExceptionHandler {

    private final ProblemDetailsWriter problemDetailsWriter;

    public ProblemDetailsExceptionHandler(ProblemDetailsWriter problemDetailsWriter) {
        this.problemDetailsWriter = problemDetailsWriter;
    }

    @ExceptionHandler(ApiProblemException.class)
    ResponseEntity<ProblemDetail> handleApiProblem(ApiProblemException exception, HttpServletRequest request) {
        ProblemDetail problem = problemDetailsWriter.problem(
                exception.errorCode(),
                exception.getMessage(),
                request);
        return ResponseEntity.status(exception.errorCode().httpStatus()).body(problem);
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    ResponseEntity<ProblemDetail> handleValidation(MethodArgumentNotValidException exception, HttpServletRequest request) {
        ProblemDetail problem = problemDetailsWriter.problem(
                ErrorCodes.VALIDATION_FAILED,
                "Request validation failed",
                request);
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(problem);
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    ResponseEntity<ProblemDetail> handleUnreadable(HttpMessageNotReadableException exception, HttpServletRequest request) {
        ErrorCodes.ErrorCode errorCode = ErrorCodes.VALIDATION_FAILED;
        if (isInvalidPermissionCode(exception)) {
            errorCode = ErrorCodes.INVALID_PERMISSION_CODE;
        } else if (isInvalidAccessLevel(exception)) {
            errorCode = ErrorCodes.INVALID_ACCESS_LEVEL;
        }
        ProblemDetail problem = problemDetailsWriter.problem(
                errorCode,
                "Request body is invalid",
                request);
        return ResponseEntity.status(errorCode.httpStatus()).body(problem);
    }

    private boolean isInvalidPermissionCode(Throwable exception) {
        Throwable current = exception;
        while (current != null) {
            String message = current.getMessage();
            if (message != null && message.contains("Unexpected value") && message.contains("PermissionCode")) {
                return true;
            }
            current = current.getCause();
        }
        return false;
    }

    private boolean isInvalidAccessLevel(Throwable exception) {
        Throwable current = exception;
        while (current != null) {
            String message = current.getMessage();
            if (message != null && message.contains("Unexpected value") && message.contains("AccessLevel")) {
                return true;
            }
            current = current.getCause();
        }
        return false;
    }
}
