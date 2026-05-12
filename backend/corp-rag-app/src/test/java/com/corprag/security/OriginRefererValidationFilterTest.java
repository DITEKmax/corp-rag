package com.corprag.security;

import static org.assertj.core.api.Assertions.assertThat;

import com.corprag.adapter.rest.ProblemDetailsWriter;
import com.corprag.config.AppSecurityProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.Cookie;
import java.io.IOException;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

class OriginRefererValidationFilterTest {

    @Test
    void rejectsUnsafeCookieRequestWithoutAllowedOriginOrReferer() throws ServletException, IOException {
        AppSecurityProperties properties = new AppSecurityProperties();
        OriginRefererValidationFilter filter =
                new OriginRefererValidationFilter(properties, new ProblemDetailsWriter(new ObjectMapper()));
        MockHttpServletRequest request = new MockHttpServletRequest("POST", "/api/v1/auth/logout");
        request.setCookies(new Cookie(properties.getCookies().getSessionName(), "access-token"));
        MockHttpServletResponse response = new MockHttpServletResponse();

        filter.doFilter(request, response, new MockFilterChain());

        assertThat(response.getStatus()).isEqualTo(403);
        assertThat(response.getContentAsString()).contains("ORIGIN_VALIDATION_FAILED");
    }

    @Test
    void allowsUnsafeCookieRequestWithAllowedOrigin() throws ServletException, IOException {
        AppSecurityProperties properties = new AppSecurityProperties();
        OriginRefererValidationFilter filter =
                new OriginRefererValidationFilter(properties, new ProblemDetailsWriter(new ObjectMapper()));
        MockHttpServletRequest request = new MockHttpServletRequest("POST", "/api/v1/auth/logout");
        request.setCookies(new Cookie(properties.getCookies().getSessionName(), "access-token"));
        request.addHeader(HttpHeaders.ORIGIN, "http://localhost:8080");
        MockHttpServletResponse response = new MockHttpServletResponse();

        filter.doFilter(request, response, new MockFilterChain());

        assertThat(response.getStatus()).isEqualTo(200);
    }

    @Test
    void skipsBearerTokenRequests() throws ServletException, IOException {
        AppSecurityProperties properties = new AppSecurityProperties();
        OriginRefererValidationFilter filter =
                new OriginRefererValidationFilter(properties, new ProblemDetailsWriter(new ObjectMapper()));
        MockHttpServletRequest request = new MockHttpServletRequest("POST", "/api/v1/documents");
        request.addHeader(HttpHeaders.AUTHORIZATION, "Bearer access-token");
        MockHttpServletResponse response = new MockHttpServletResponse();

        filter.doFilter(request, response, new MockFilterChain());

        assertThat(response.getStatus()).isEqualTo(200);
    }
}
