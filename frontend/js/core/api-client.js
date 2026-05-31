import { sessionState } from './session-state.js';

const API_BASE = globalThis.CORP_RAG_API_BASE || '/api/v1';

let refreshPromise = null;
let handlers = {
  onAuthRequired: null,
  onMustChangeRequired: null,
};

export class ApiError extends Error {
  constructor(problem, response) {
    super(problem?.detail || problem?.title || `Request failed with status ${response?.status || 0}`);
    this.name = 'ApiError';
    this.problem = problem || null;
    this.response = response || null;
    this.status = response?.status || problem?.status || 0;
    this.errorCode = problem?.errorCode || null;
  }
}

export function configureApiClient(nextHandlers) {
  handlers = { ...handlers, ...nextHandlers };
}

export const apiClient = {
  getMe() {
    return request('/me', { skipRefresh: true });
  },

  login(credentials) {
    return request('/auth/login', {
      method: 'POST',
      body: credentials,
      skipRefresh: true,
    });
  },

  refresh() {
    return refreshSession();
  },

  changePassword(payload) {
    return request('/auth/password', {
      method: 'POST',
      body: payload,
      skipRefresh: true,
    });
  },

  logout() {
    return request('/auth/logout', {
      method: 'POST',
      skipRefresh: true,
      emptyResponse: true,
    });
  },

  request,
};

export async function request(path, options = {}) {
  return requestWithRetry(path, options, false);
}

async function requestWithRetry(path, options, didRetry) {
  const response = await send(path, options);
  if (response.ok) {
    return parseSuccess(response, options);
  }

  const problem = await parseProblem(response);
  if (problem?.errorCode === 'PASSWORD_CHANGE_REQUIRED') {
    sessionState.markMustChangePassword();
    handlers.onMustChangeRequired?.();
    throw new ApiError(problem, response);
  }

  if (response.status === 401 && shouldRefresh(path, options, didRetry)) {
    try {
      await refreshSession();
      return requestWithRetry(path, options, true);
    } catch (error) {
      sessionState.clearSession();
      handlers.onAuthRequired?.();
      throw error;
    }
  }

  if (response.status === 401 && didRetry) {
    sessionState.clearSession();
    handlers.onAuthRequired?.();
  }

  throw new ApiError(problem, response);
}

async function refreshSession() {
  if (!refreshPromise) {
    refreshPromise = send('/auth/refresh', { method: 'POST' })
      .then(async (response) => {
        if (!response.ok) {
          throw new ApiError(await parseProblem(response), response);
        }
        return parseSuccess(response, {});
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

function shouldRefresh(path, options, didRetry) {
  if (didRetry || options.skipRefresh) {
    return false;
  }
  return path !== '/me'
    && path !== '/auth/refresh'
    && path !== '/auth/login'
    && path !== '/auth/password';
}

async function send(path, options = {}) {
  const init = {
    method: options.method || 'GET',
    credentials: 'include',
    headers: new Headers(options.headers || {}),
  };

  if (options.body !== undefined) {
    if (options.body instanceof FormData) {
      init.body = options.body;
    } else {
      init.headers.set('Content-Type', 'application/json');
      init.body = JSON.stringify(options.body);
    }
  }

  return fetch(API_BASE + path, init);
}

async function parseSuccess(response, options) {
  if (options.emptyResponse || response.status === 204) {
    return null;
  }
  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

async function parseProblem(response) {
  const text = await response.text();
  if (!text) {
    return {
      status: response.status,
      title: response.statusText,
      detail: response.statusText,
    };
  }
  try {
    return JSON.parse(text);
  } catch {
    return {
      status: response.status,
      title: response.statusText,
      detail: text,
    };
  }
}
