const listeners = new Set();

const state = {
  status: 'booting',
  user: null,
  permissions: new Set(),
  returnTo: '#/chat',
};

export const sessionState = {
  subscribe(listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },

  snapshot() {
    return {
      status: state.status,
      user: state.user,
      permissions: new Set(state.permissions),
      returnTo: state.returnTo,
    };
  },

  setBooting() {
    state.status = 'booting';
    emit();
  },

  setCurrentUser(user) {
    state.status = 'ready';
    state.user = user;
    state.permissions = new Set(user?.permissions || []);
    emit();
  },

  clearSession() {
    state.status = 'anonymous';
    state.user = null;
    state.permissions = new Set();
    emit();
  },

  markMustChangePassword(user = state.user) {
    state.status = 'must-change-password';
    state.user = user;
    state.permissions = new Set(user?.permissions || []);
    emit();
  },

  isAuthenticated() {
    return Boolean(state.user);
  },

  mustChangePassword() {
    return state.status === 'must-change-password' || Boolean(state.user?.mustChangePassword);
  },

  hasPermission(permission) {
    return state.permissions.has(permission);
  },

  setReturnTo(hash) {
    if (hash && hash !== '#/login' && hash !== '#/change-password') {
      state.returnTo = hash;
    }
  },

  consumeReturnTo() {
    const target = state.returnTo || '#/chat';
    state.returnTo = '#/chat';
    return target;
  },
};

function emit() {
  const snapshot = sessionState.snapshot();
  for (const listener of listeners) {
    listener(snapshot);
  }
}
