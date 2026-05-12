package com.corprag.security;

import com.corprag.adapter.rest.ProblemDetailsWriter;
import com.corprag.config.AppSecurityProperties;
import com.corprag.contracts.constants.ErrorCodes;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.net.URI;
import java.util.Set;
import java.util.stream.Collectors;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.web.filter.OncePerRequestFilter;

public class OriginRefererValidationFilter extends OncePerRequestFilter {

    private final AppSecurityProperties properties;
    private final ProblemDetailsWriter problemDetailsWriter;
    private final Set<String> allowedOrigins;

    public OriginRefererValidationFilter(AppSecurityProperties properties, ProblemDetailsWriter problemDetailsWriter) {
        this.properties = properties;
        this.problemDetailsWriter = problemDetailsWriter;
        this.allowedOrigins = properties.getCors().getAllowedOrigins().stream()
                .map(OriginRefererValidationFilter::normalizeOrigin)
                .collect(Collectors.toUnmodifiableSet());
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain) throws ServletException, IOException {
        if (!requiresValidation(request)) {
            filterChain.doFilter(request, response);
            return;
        }

        String origin = request.getHeader(HttpHeaders.ORIGIN);
        String referer = request.getHeader(HttpHeaders.REFERER);
        if (isAllowedOrigin(origin) || isAllowedReferer(referer)) {
            filterChain.doFilter(request, response);
            return;
        }

        problemDetailsWriter.write(
                response,
                request,
                ErrorCodes.ORIGIN_VALIDATION_FAILED,
                "Origin or Referer is required for unsafe cookie-authenticated requests");
    }

    private boolean requiresValidation(HttpServletRequest request) {
        if (!request.getRequestURI().startsWith("/api/v1/") || isSafeMethod(request.getMethod())) {
            return false;
        }
        if (request.getHeader(HttpHeaders.AUTHORIZATION) != null) {
            return false;
        }
        return hasCookie(request, properties.getCookies().getSessionName())
                || hasCookie(request, properties.getCookies().getRefreshName());
    }

    private static boolean isSafeMethod(String method) {
        return HttpMethod.GET.matches(method) || HttpMethod.HEAD.matches(method) || HttpMethod.OPTIONS.matches(method);
    }

    private static boolean hasCookie(HttpServletRequest request, String cookieName) {
        Cookie[] cookies = request.getCookies();
        if (cookies == null) {
            return false;
        }
        for (Cookie cookie : cookies) {
            if (cookieName.equals(cookie.getName()) && !cookie.getValue().isBlank()) {
                return true;
            }
        }
        return false;
    }

    private boolean isAllowedOrigin(String value) {
        return value != null && allowedOrigins.contains(normalizeOrigin(value));
    }

    private boolean isAllowedReferer(String value) {
        if (value == null || value.isBlank()) {
            return false;
        }
        return allowedOrigins.contains(normalizeOrigin(value));
    }

    private static String normalizeOrigin(String value) {
        URI uri = URI.create(value);
        int port = uri.getPort();
        String origin = uri.getScheme() + "://" + uri.getHost();
        if (port >= 0) {
            origin += ":" + port;
        }
        return origin;
    }
}
