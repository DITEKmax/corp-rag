package com.corprag.security;

import static org.assertj.core.api.Assertions.assertThat;

import com.corprag.config.AppSecurityProperties;
import jakarta.servlet.http.Cookie;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

class CookieBearerTokenResolverTest {

    @Test
    void resolvesSessionCookieOnly() {
        AppSecurityProperties properties = new AppSecurityProperties();
        CookieBearerTokenResolver resolver = new CookieBearerTokenResolver(properties);
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.setCookies(
                new Cookie(properties.getCookies().getRefreshName(), "refresh-token"),
                new Cookie(properties.getCookies().getSessionName(), "access-token"));

        assertThat(resolver.resolve(request)).isEqualTo("access-token");
    }

    @Test
    void returnsNullWhenSessionCookieMissing() {
        AppSecurityProperties properties = new AppSecurityProperties();
        CookieBearerTokenResolver resolver = new CookieBearerTokenResolver(properties);
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.setCookies(new Cookie(properties.getCookies().getRefreshName(), "refresh-token"));

        assertThat(resolver.resolve(request)).isNull();
    }
}
