package com.corprag.service.auth;

import com.corprag.domain.UserAccount;
import java.util.List;

public record AuthenticatedUser(
        UserAccount account,
        List<String> roles,
        List<String> permissions) {
}
