package com.corprag.config;

import java.util.ArrayList;
import java.util.List;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app.security")
public class AppSecurityProperties {

    private final Jwt jwt = new Jwt();
    private final Cookies cookies = new Cookies();
    private final Cors cors = new Cors();
    private final Sessions sessions = new Sessions();

    public Jwt getJwt() {
        return jwt;
    }

    public Cookies getCookies() {
        return cookies;
    }

    public Cors getCors() {
        return cors;
    }

    public Sessions getSessions() {
        return sessions;
    }

    public static class Jwt {
        private String secret = "";
        private String issuer = "corp-rag";
        private int accessTokenMinutes = 15;

        public String getSecret() {
            return secret;
        }

        public void setSecret(String secret) {
            this.secret = secret;
        }

        public String getIssuer() {
            return issuer;
        }

        public void setIssuer(String issuer) {
            this.issuer = issuer;
        }

        public int getAccessTokenMinutes() {
            return accessTokenMinutes;
        }

        public void setAccessTokenMinutes(int accessTokenMinutes) {
            this.accessTokenMinutes = accessTokenMinutes;
        }
    }

    public static class Cookies {
        private String sessionName = "corp_rag_session";
        private String refreshName = "corp_rag_refresh";
        private String sessionPath = "/api/v1";
        private String refreshPath = "/api/v1/auth";
        private boolean secure;

        public String getSessionName() {
            return sessionName;
        }

        public void setSessionName(String sessionName) {
            this.sessionName = sessionName;
        }

        public String getRefreshName() {
            return refreshName;
        }

        public void setRefreshName(String refreshName) {
            this.refreshName = refreshName;
        }

        public String getSessionPath() {
            return sessionPath;
        }

        public void setSessionPath(String sessionPath) {
            this.sessionPath = sessionPath;
        }

        public String getRefreshPath() {
            return refreshPath;
        }

        public void setRefreshPath(String refreshPath) {
            this.refreshPath = refreshPath;
        }

        public boolean isSecure() {
            return secure;
        }

        public void setSecure(boolean secure) {
            this.secure = secure;
        }
    }

    public static class Cors {
        private List<String> allowedOrigins = new ArrayList<>(
                List.of("http://localhost", "http://localhost:80", "http://localhost:8080"));

        public List<String> getAllowedOrigins() {
            return allowedOrigins;
        }

        public void setAllowedOrigins(List<String> allowedOrigins) {
            this.allowedOrigins = allowedOrigins;
        }
    }

    public static class Sessions {
        private int maxActive = 5;
        private int refreshTokenDays = 7;

        public int getMaxActive() {
            return maxActive;
        }

        public void setMaxActive(int maxActive) {
            this.maxActive = maxActive;
        }

        public int getRefreshTokenDays() {
            return refreshTokenDays;
        }

        public void setRefreshTokenDays(int refreshTokenDays) {
            this.refreshTokenDays = refreshTokenDays;
        }
    }
}
