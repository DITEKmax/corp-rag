package com.corprag.adapter.rest;

import com.corprag.contracts.api.v1.model.AccessPolicy;
import com.corprag.contracts.api.v1.model.CreateAccessPolicyRequest;
import com.corprag.contracts.api.v1.model.HateoasLink;
import com.corprag.contracts.api.v1.model.ListAccessPolicies200Response;
import com.corprag.contracts.api.v1.model.UpdateAccessPolicyRequest;
import com.corprag.security.Permission;
import com.corprag.service.access.AccessPolicyService;
import jakarta.validation.Valid;
import java.net.URI;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/access-policies")
public class AccessPolicyController {

    private final AccessPolicyService accessPolicyService;

    public AccessPolicyController(AccessPolicyService accessPolicyService) {
        this.accessPolicyService = accessPolicyService;
    }

    @GetMapping
    ListAccessPolicies200Response listPolicies(@AuthenticationPrincipal Jwt jwt) {
        JwtAuthorization.requirePermission(jwt, Permission.ACCESS_POLICIES_READ.value());
        return new ListAccessPolicies200Response()
                .items(accessPolicyService.listPolicies().stream().map(this::toAccessPolicy).toList())
                .links(Map.of("self", new HateoasLink().href("/api/v1/access-policies")));
    }

    @PostMapping
    ResponseEntity<AccessPolicy> createPolicy(
            @AuthenticationPrincipal Jwt jwt,
            @Valid @RequestBody CreateAccessPolicyRequest request) {
        JwtAuthorization.requirePermission(jwt, Permission.ACCESS_POLICIES_CREATE.value());
        AccessPolicyService.AccessPolicyView policy =
                accessPolicyService.createPolicy(request, JwtAuthorization.userId(jwt));
        return ResponseEntity.created(URI.create("/api/v1/access-policies/" + policy.policy().id()))
                .body(toAccessPolicy(policy));
    }

    @GetMapping("/{policyId}")
    ResponseEntity<AccessPolicy> getPolicy(
            @AuthenticationPrincipal Jwt jwt,
            @PathVariable("policyId") UUID policyId) {
        JwtAuthorization.requirePermission(jwt, Permission.ACCESS_POLICIES_READ.value());
        AccessPolicyService.AccessPolicyView policy = accessPolicyService.getPolicy(policyId);
        return ResponseEntity.ok()
                .header(HttpHeaders.ETAG, accessPolicyService.etag(policy))
                .body(toAccessPolicy(policy));
    }

    @PutMapping("/{policyId}")
    ResponseEntity<AccessPolicy> updatePolicy(
            @AuthenticationPrincipal Jwt jwt,
            @PathVariable("policyId") UUID policyId,
            @RequestHeader(value = HttpHeaders.IF_MATCH, required = false) String ifMatch,
            @Valid @RequestBody UpdateAccessPolicyRequest request) {
        JwtAuthorization.requirePermission(jwt, Permission.ACCESS_POLICIES_UPDATE.value());
        AccessPolicyService.AccessPolicyView policy =
                accessPolicyService.updatePolicy(policyId, request, ifMatch, JwtAuthorization.userId(jwt));
        return ResponseEntity.ok()
                .header(HttpHeaders.ETAG, accessPolicyService.etag(policy))
                .body(toAccessPolicy(policy));
    }

    @DeleteMapping("/{policyId}")
    ResponseEntity<Void> deletePolicy(
            @AuthenticationPrincipal Jwt jwt,
            @PathVariable("policyId") UUID policyId) {
        JwtAuthorization.requirePermission(jwt, Permission.ACCESS_POLICIES_DELETE.value());
        accessPolicyService.deletePolicy(policyId, JwtAuthorization.userId(jwt));
        return ResponseEntity.noContent().build();
    }

    private AccessPolicy toAccessPolicy(AccessPolicyService.AccessPolicyView view) {
        return new AccessPolicy()
                .id(view.policy().id())
                .roleId(view.policy().roleId())
                .roleName(view.roleName())
                .accessLevels(view.policy().accessLevels().stream()
                        .map(level -> com.corprag.contracts.api.v1.model.AccessLevel.fromValue(level.name()))
                        .toList())
                .departments(view.policy().departments())
                .docTypes(view.policy().docTypes().stream()
                        .map(docType -> com.corprag.contracts.api.v1.model.DocType.fromValue(docType.name()))
                        .toList())
                .version(view.policy().version())
                .links(Map.of("self", new HateoasLink().href("/api/v1/access-policies/" + view.policy().id())));
    }
}
