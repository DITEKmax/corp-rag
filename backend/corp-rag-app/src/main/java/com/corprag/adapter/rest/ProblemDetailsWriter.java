package com.corprag.adapter.rest;

import com.corprag.contracts.api.v1.model.ProblemDetail;
import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.security.CorrelationIdFilter;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.net.URI;
import java.util.Map;
import java.util.UUID;
import org.slf4j.MDC;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;

@Component
public class ProblemDetailsWriter {

    private final ObjectMapper objectMapper;

    public ProblemDetailsWriter(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public ProblemDetail problem(ErrorCodes.ErrorCode errorCode, String detail, HttpServletRequest request) {
        return problem(errorCode, detail, request, Map.of());
    }

    public ProblemDetail problem(
            ErrorCodes.ErrorCode errorCode,
            String detail,
            HttpServletRequest request,
            Map<String, Object> details) {
        return new ProblemDetail()
                .type(URI.create(errorCode.problemType()))
                .title(errorCode.defaultTitle())
                .status(errorCode.httpStatus())
                .detail(detail)
                .instance(request == null ? null : request.getRequestURI())
                .errorCode(errorCode.code())
                .correlationId(correlationId())
                .details(details == null ? Map.of() : details);
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

    private static UUID correlationId() {
        String value = MDC.get(CorrelationIdFilter.MDC_KEY);
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            return UUID.fromString(value);
        } catch (IllegalArgumentException ignored) {
            return null;
        }
    }
}
