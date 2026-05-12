package com.corprag.security;

import com.corprag.adapter.rest.ProblemDetailsWriter;
import com.corprag.contracts.constants.ErrorCodes;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.springframework.http.HttpMethod;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.filter.OncePerRequestFilter;

public class MustChangePasswordFilter extends OncePerRequestFilter {

    private final ProblemDetailsWriter problemDetailsWriter;

    public MustChangePasswordFilter(ProblemDetailsWriter problemDetailsWriter) {
        this.problemDetailsWriter = problemDetailsWriter;
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain) throws ServletException, IOException {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (!(authentication instanceof JwtAuthenticationToken jwtAuthenticationToken)) {
            filterChain.doFilter(request, response);
            return;
        }
        Jwt jwt = jwtAuthenticationToken.getToken();
        if (!Boolean.TRUE.equals(jwt.getClaimAsBoolean("must_change_password")) || isAllowed(request)) {
            filterChain.doFilter(request, response);
            return;
        }
        problemDetailsWriter.write(
                response,
                request,
                ErrorCodes.PASSWORD_CHANGE_REQUIRED,
                "Password must be changed before using this endpoint");
    }

    private static boolean isAllowed(HttpServletRequest request) {
        String uri = request.getRequestURI();
        String method = request.getMethod();
        return (HttpMethod.POST.matches(method) && uri.equals("/api/v1/auth/password"))
                || (HttpMethod.POST.matches(method) && uri.equals("/api/v1/auth/refresh"))
                || (HttpMethod.POST.matches(method) && uri.equals("/api/v1/auth/logout"))
                || (HttpMethod.GET.matches(method) && uri.equals("/api/v1/me"));
    }
}
