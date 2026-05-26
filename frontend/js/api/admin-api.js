import { apiClient } from '../core/api-client.js';

const PAGE_SIZE = 50;

export const adminApi = {
  listDocuments(params = {}) {
    return apiClient.request(`/documents${query({ page: 0, size: PAGE_SIZE, ...params })}`);
  },

  uploadDocument(formData) {
    return apiClient.request('/documents', {
      method: 'POST',
      body: formData,
    });
  },

  deleteDocument(documentId) {
    return apiClient.request(`/documents/${encodeURIComponent(documentId)}`, {
      method: 'DELETE',
      emptyResponse: true,
    });
  },

  getDocumentRaw(documentId) {
    return apiClient.request(`/documents/${encodeURIComponent(documentId)}/raw`);
  },

  listUsers(params = {}) {
    return apiClient.request(`/users${query({ page: 0, size: PAGE_SIZE, ...params })}`);
  },

  createUser(payload) {
    return apiClient.request('/users', {
      method: 'POST',
      body: payload,
    });
  },

  updateUser(userId, payload) {
    return apiClient.request(`/users/${encodeURIComponent(userId)}`, {
      method: 'PATCH',
      body: payload,
    });
  },

  disableUser(userId) {
    return apiClient.request(`/users/${encodeURIComponent(userId)}`, {
      method: 'DELETE',
      emptyResponse: true,
    });
  },

  resetPassword(userId) {
    return apiClient.request(`/users/${encodeURIComponent(userId)}/reset-password`, {
      method: 'POST',
    });
  },

  assignUserRoles(userId, roles) {
    return apiClient.request(`/users/${encodeURIComponent(userId)}/roles`, {
      method: 'POST',
      body: { roles },
    });
  },

  listRoles() {
    return apiClient.request('/roles');
  },

  createRole(payload) {
    return apiClient.request('/roles', {
      method: 'POST',
      body: payload,
    });
  },

  updateRole(role, payload) {
    return apiClient.request(`/roles/${encodeURIComponent(role.id)}`, {
      method: 'PUT',
      headers: { 'If-Match': `"role-v${role.version ?? 0}"` },
      body: payload,
    });
  },

  listAccessPolicies() {
    return apiClient.request('/access-policies');
  },

  createAccessPolicy(payload) {
    return apiClient.request('/access-policies', {
      method: 'POST',
      body: payload,
    });
  },

  updateAccessPolicy(policy, payload) {
    return apiClient.request(`/access-policies/${encodeURIComponent(policy.id)}`, {
      method: 'PUT',
      headers: { 'If-Match': `"access-policy-v${policy.version ?? 0}"` },
      body: payload,
    });
  },

  deleteAccessPolicy(policyId) {
    return apiClient.request(`/access-policies/${encodeURIComponent(policyId)}`, {
      method: 'DELETE',
      emptyResponse: true,
    });
  },
};

function query(params) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, String(value));
    }
  }
  const value = search.toString();
  return value ? `?${value}` : '';
}
