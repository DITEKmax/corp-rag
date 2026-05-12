package com.corprag.adapter.rest;

import com.corprag.contracts.api.v1.model.ProblemDetail;
import com.corprag.contracts.constants.ErrorCodes;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.net.URI;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;

@Component
public class ProblemDetailsWriter {

    private final ObjectMapper objectMapper;

    public ProblemDetailsWriter(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public ProblemDetail problem(ErrorCodes.ErrorCode errorCode, String detail, HttpServletRequest request) {
        return new ProblemDetail()
                .type(URI.create(errorCode.problemType()))
                .title(errorCode.defaultTitle())
                .status(errorCode.httpStatus())
                .detail(detail)
                .instance(request == null ? null : request.getRequestURI())
                .errorCode(errorCode.code());
    }

    public void write(
            HttpServletResponse response,
            HttpServletRequest request,
            ErrorCodes.ErrorCode errorCode,
            String detail) throws IOException {
        response.setStatus(errorCode.httpStatus());
        response.setContentType(MediaType.APPLICATION_PROBLEM_JSON_VALUE);
        objectMapper.writeValue(response.getOutputStream(), problem(errorCode, detail, request));
    }
}
