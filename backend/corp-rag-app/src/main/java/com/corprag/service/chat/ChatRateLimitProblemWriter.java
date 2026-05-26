package com.corprag.service.chat;

import com.corprag.adapter.rest.ProblemDetailsWriter;
import com.corprag.contracts.api.v1.model.ProblemDetail;
import com.corprag.contracts.constants.ErrorCodes;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
public class ChatRateLimitProblemWriter {

    private static final int LIMIT = 30;
    private static final int WINDOW_SECONDS = 60;

    private final ProblemDetailsWriter problemDetailsWriter;

    public ChatRateLimitProblemWriter(ProblemDetailsWriter problemDetailsWriter) {
        this.problemDetailsWriter = problemDetailsWriter;
    }

    public ProblemDetail problem(HttpServletRequest request, ChatRateLimiter.Decision decision) {
        return problemDetailsWriter.problem(
                ErrorCodes.RATE_LIMIT_EXCEEDED,
                "Превышен лимит 30 запросов в минуту для пользователя.",
                request,
                details(decision.retryAfterSeconds()));
    }

    public void write(HttpServletResponse response, HttpServletRequest request, ChatRateLimiter.Decision decision)
            throws IOException {
        response.setHeader("Retry-After", Long.toString(decision.retryAfterSeconds()));
        problemDetailsWriter.write(
                response,
                request,
                ErrorCodes.RATE_LIMIT_EXCEEDED,
                "Превышен лимит 30 запросов в минуту для пользователя.",
                details(decision.retryAfterSeconds()));
    }

    private static Map<String, Object> details(long retryAfterSeconds) {
        return Map.of(
                "limit", LIMIT,
                "windowSeconds", WINDOW_SECONDS,
                "retryAfterSeconds", retryAfterSeconds);
    }
}
