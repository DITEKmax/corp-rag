import { apiClient } from '../core/api-client.js';

const DEFAULT_PAGE_SIZE = 50;
const MESSAGE_PAGE_SIZE = 100;

export const chatApi = {
  listConversations({ page = 0, size = DEFAULT_PAGE_SIZE } = {}) {
    return apiClient.request(`/chat/conversations${query({ page, size })}`);
  },

  createConversation({ title } = {}) {
    const body = title ? { title } : {};
    return apiClient.request('/chat/conversations', {
      method: 'POST',
      body,
    });
  },

  deleteConversation(conversationId) {
    return apiClient.request(`/chat/conversations/${encodeURIComponent(conversationId)}`, {
      method: 'DELETE',
      emptyResponse: true,
    });
  },

  listMessages(conversationId, { page = 0, size = MESSAGE_PAGE_SIZE } = {}) {
    return apiClient.request(
      `/chat/conversations/${encodeURIComponent(conversationId)}/messages${query({ page, size })}`,
    );
  },

  query({ conversationId, message }) {
    return apiClient.request('/chat/query', {
      method: 'POST',
      body: {
        conversationId,
        message,
      },
    });
  },
};

function query(params) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) {
      search.set(key, String(value));
    }
  }
  const value = search.toString();
  return value ? `?${value}` : '';
}
