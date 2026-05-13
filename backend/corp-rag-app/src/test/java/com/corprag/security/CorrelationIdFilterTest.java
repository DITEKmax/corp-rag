package com.corprag.security;

import static org.assertj.core.api.Assertions.assertThat;

import com.corprag.adapter.rest.ProblemDetailsWriter;
import com.corprag.contracts.api.v1.model.ProblemDetail;
import com.corprag.contracts.constants.ErrorCodes;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.slf4j.MDC;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

class CorrelationIdFilterTest {

    private final CorrelationIdFilter filter = new CorrelationIdFilter();
    private final ProblemDetailsWriter problemDetailsWriter = new ProblemDetailsWriter(new ObjectMapper());

    @AfterEach
    void tearDown() {
        MDC.clear();
    }

    @Test
    void preservesValidCorrelationIdForResponseProblemDetailsAndMdcLifecycle() throws Exception {
        UUID supplied = UUID.fromString("550e8400-e29b-41d4-a716-446655440099");
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/v1/documents");
        request.addHeader(CorrelationIdFilter.HEADER_NAME, supplied.toString());
        MockHttpServletResponse response = new MockHttpServletResponse();
        AtomicReference<ProblemDetail> problem = new AtomicReference<>();

        filter.doFilter(request, response, (servletRequest, servletResponse) -> {
            assertThat(MDC.get(CorrelationIdFilter.MDC_KEY)).isEqualTo(supplied.toString());
            problem.set(problemDetailsWriter.problem(
                    ErrorCodes.AUTHENTICATION_FAILED,
                    "Authentication is required",
                    (MockHttpServletRequest) servletRequest));
        });

        assertThat(response.getHeader(CorrelationIdFilter.HEADER_NAME)).isEqualTo(supplied.toString());
        assertThat(problem.get().getCorrelationId()).isEqualTo(supplied);
        assertThat(MDC.get(CorrelationIdFilter.MDC_KEY)).isNull();
    }

    @Test
    void generatesCorrelationIdWhenHeaderIsMissingOrInvalid() throws Exception {
        MockHttpServletRequest missingRequest = new MockHttpServletRequest("GET", "/api/v1/documents");
        MockHttpServletResponse missingResponse = new MockHttpServletResponse();

        filter.doFilter(missingRequest, missingResponse, (request, response) ->
                assertThat(MDC.get(CorrelationIdFilter.MDC_KEY)).isNotBlank());

        UUID generated = UUID.fromString(missingResponse.getHeader(CorrelationIdFilter.HEADER_NAME));
        assertThat(generated).isNotNull();
        assertThat(MDC.get(CorrelationIdFilter.MDC_KEY)).isNull();

        MockHttpServletRequest invalidRequest = new MockHttpServletRequest("GET", "/api/v1/documents");
        invalidRequest.addHeader(CorrelationIdFilter.HEADER_NAME, "not-a-uuid");
        MockHttpServletResponse invalidResponse = new MockHttpServletResponse();

        filter.doFilter(invalidRequest, invalidResponse, (request, response) -> {
        });

        assertThat(invalidResponse.getHeader(CorrelationIdFilter.HEADER_NAME)).isNotEqualTo("not-a-uuid");
        assertThat(UUID.fromString(invalidResponse.getHeader(CorrelationIdFilter.HEADER_NAME))).isNotNull();
        assertThat(MDC.get(CorrelationIdFilter.MDC_KEY)).isNull();
    }
}
