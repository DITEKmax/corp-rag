package com.corprag.service.access;

import com.corprag.domain.AccessLevel;
import com.corprag.domain.AccessPolicyDefinition;
import com.corprag.domain.DocType;
import com.corprag.domain.ResolvedAccessFilter;
import com.corprag.repository.AccessPolicyRepository;
import java.util.Comparator;
import java.util.EnumSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class AccessFilterResolver {

    private final AccessPolicyRepository accessPolicyRepository;
    private final AccessFilterCache cache;

    public AccessFilterResolver(AccessPolicyRepository accessPolicyRepository, AccessFilterCache cache) {
        this.accessPolicyRepository = accessPolicyRepository;
        this.cache = cache;
    }

    public ResolvedAccessFilter resolve(UUID userId) {
        return cache.get(userId).orElseGet(() -> {
            ResolvedAccessFilter resolved = resolve(accessPolicyRepository.findPoliciesForUser(userId));
            cache.put(userId, resolved);
            return resolved;
        });
    }

    ResolvedAccessFilter resolve(List<AccessPolicyDefinition> policies) {
        EnumSet<AccessLevel> accessLevels = EnumSet.of(AccessLevel.PUBLIC);
        Set<String> departments = new LinkedHashSet<>();
        EnumSet<DocType> docTypes = EnumSet.noneOf(DocType.class);
        boolean wildcardDepartments = policies.isEmpty();

        for (AccessPolicyDefinition policy : policies) {
            policy.accessLevels().forEach(level -> accessLevels.addAll(hierarchy(level)));
            if (policy.departments().isEmpty()) {
                wildcardDepartments = true;
            } else if (!wildcardDepartments) {
                departments.addAll(policy.departments());
            }
            docTypes.addAll(policy.docTypes());
        }

        if (docTypes.isEmpty()) {
            docTypes.addAll(EnumSet.allOf(DocType.class));
        }

        return new ResolvedAccessFilter(
                accessLevels.stream()
                        .sorted(Comparator.comparingInt(AccessLevel::rank))
                        .toList(),
                wildcardDepartments
                        ? List.of()
                        : departments.stream().sorted().toList(),
                docTypes.stream().sorted().toList());
    }

    private EnumSet<AccessLevel> hierarchy(AccessLevel level) {
        EnumSet<AccessLevel> levels = EnumSet.noneOf(AccessLevel.class);
        for (AccessLevel candidate : AccessLevel.values()) {
            if (candidate.rank() <= level.rank()) {
                levels.add(candidate);
            }
        }
        return levels;
    }
}
