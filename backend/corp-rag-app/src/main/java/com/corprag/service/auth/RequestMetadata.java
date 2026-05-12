package com.corprag.service.auth;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpHeaders;

public record RequestMetadata(String ipAddress, String userAgent) {

    public static RequestMetadata from(HttpServletRequest request) {
        return new RequestMetadata(request.getRemoteAddr(), request.getHeader(HttpHeaders.USER_AGENT));
    }
}
