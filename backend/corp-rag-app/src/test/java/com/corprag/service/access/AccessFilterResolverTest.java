package com.corprag.service.access;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.corprag.domain.AccessLevel;
import com.corprag.domain.AccessPolicyDefinition;
import com.corprag.domain.DocType;
import com.corprag.domain.ResolvedAccessFilter;
import com.corprag.repository.AccessPolicyRepository;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class AccessFilterResolverTest {

    private static final UUID USER_ID = UUID.fromString("00000000-0000-4000-8000-00000000c001");
    private static final UUID ROLE_ID = UUID.fromString("00000000-0000-4000-8000-00000000d001");

    @Mock
    private AccessPolicyRepository accessPolicyRepository;

    @Test
    void noPoliciesFailSafeToPublicAllDocTypesAndWildcardDepartments() {
        AccessFilterResolver resolver = resolver();
        when(accessPolicyRepository.findPoliciesForUser(USER_ID)).thenReturn(List.of());

        ResolvedAccessFilter resolved = resolver.resolve(USER_ID);

        assertThat(resolved.accessLevels()).containsExactly(AccessLevel.PUBLIC);
        assertThat(resolved.departments()).isEmpty();
        assertThat(resolved.docTypes()).containsExactly(DocType.POLICY, DocType.REGULATION, DocType.GUIDE, DocType.REPORT, DocType.MANUAL, DocType.OTHER);
    }

    @Test
    void mergesRolePoliciesWithHierarchyAndWildcardDepartmentSemantics() {
        AccessFilterResolver resolver = resolver();

        ResolvedAccessFilter resolved = resolver.resolve(List.of(
                policy(
                        List.of(AccessLevel.INTERNAL),
                        List.of("HR"),
                        List.of(DocType.POLICY)),
                policy(
                        List.of(AccessLevel.RESTRICTED),
                        List.of(),
                        List.of(DocType.REPORT))));

        assertThat(resolved.accessLevels())
                .containsExactly(AccessLevel.PUBLIC, AccessLevel.INTERNAL, AccessLevel.CONFIDENTIAL, AccessLevel.RESTRICTED);
        assertThat(resolved.departments()).isEmpty();
        assertThat(resolved.docTypes()).containsExactly(DocType.POLICY, DocType.REPORT);
    }

    @Test
    void cachedValuesExpireAfterTtl() {
        MutableClock clock = new MutableClock();
        AccessFilterResolver resolver = new AccessFilterResolver(
                accessPolicyRepository,
                new AccessFilterCache(clock, Duration.ofSeconds(60)));
        when(accessPolicyRepository.findPoliciesForUser(USER_ID))
                .thenReturn(List.of(policy(
                        List.of(AccessLevel.PUBLIC),
                        List.of("HR"),
                        List.of(DocType.POLICY))))
                .thenReturn(List.of(policy(
                        List.of(AccessLevel.INTERNAL),
                        List.of("IT"),
                        List.of(DocType.GUIDE))));

        assertThat(resolver.resolve(USER_ID).docTypes()).containsExactly(DocType.POLICY);
        clock.advance(Duration.ofSeconds(59));
        assertThat(resolver.resolve(USER_ID).docTypes()).containsExactly(DocType.POLICY);
        verify(accessPolicyRepository).findPoliciesForUser(USER_ID);

        clock.advance(Duration.ofSeconds(2));
        assertThat(resolver.resolve(USER_ID).docTypes()).containsExactly(DocType.GUIDE);
    }

    private AccessFilterResolver resolver() {
        return new AccessFilterResolver(accessPolicyRepository, new AccessFilterCache());
    }

    private AccessPolicyDefinition policy(
            List<AccessLevel> accessLevels,
            List<String> departments,
            List<DocType> docTypes) {
        Instant now = Instant.now();
        return new AccessPolicyDefinition(UUID.randomUUID(), ROLE_ID, accessLevels, departments, docTypes, now, now, 0);
    }

    private static final class MutableClock extends Clock {

        private Instant instant = Instant.parse("2026-01-01T00:00:00Z");

        void advance(Duration duration) {
            instant = instant.plus(duration);
        }

        @Override
        public ZoneId getZone() {
            return ZoneId.of("UTC");
        }

        @Override
        public Clock withZone(ZoneId zone) {
            return this;
        }

        @Override
        public Instant instant() {
            return instant;
        }
    }
}
