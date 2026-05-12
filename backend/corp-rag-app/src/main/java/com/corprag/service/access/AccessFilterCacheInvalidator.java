package com.corprag.service.access;

import com.corprag.domain.UserRoleAssignment;
import com.corprag.repository.UserRoleRepository;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class AccessFilterCacheInvalidator {

    private final AccessFilterCache cache;
    private final UserRoleRepository userRoleRepository;

    public AccessFilterCacheInvalidator(AccessFilterCache cache, UserRoleRepository userRoleRepository) {
        this.cache = cache;
        this.userRoleRepository = userRoleRepository;
    }

    public void invalidate(UUID userId) {
        cache.invalidate(userId);
    }

    public void invalidateForRole(UUID roleId) {
        userRoleRepository.findByRoleId(roleId).stream()
                .map(UserRoleAssignment::userId)
                .distinct()
                .forEach(cache::invalidate);
    }
}
