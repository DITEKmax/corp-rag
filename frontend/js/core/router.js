import { renderShell } from '../components/shell.js';
import { accessDeniedView, notFoundView } from '../components/views.js';
import { sessionState } from './session-state.js';
import { routes } from './routes.js';

const DEFAULT_ROUTE = '#/chat';

let rootElement = null;

export const router = {
  start(root) {
    rootElement = root;
    window.addEventListener('hashchange', () => this.resolve());
    root.addEventListener('click', async (event) => {
      const action = event.target?.closest?.('[data-action]');
      if (!action) {
        return;
      }
      if (action.dataset.action === 'logout') {
        event.preventDefault();
        await this.logout();
      }
    });
    this.resolve();
  },

  navigate(path) {
    if (window.location.hash === path) {
      this.resolve();
      return;
    }
    window.location.hash = path;
  },

  redirectToLogin(returnTo = currentPath()) {
    sessionState.setReturnTo(returnTo);
    this.navigate('#/login');
  },

  async logout() {
    const { apiClient } = await import('./api-client.js');
    try {
      await apiClient.logout();
    } finally {
      sessionState.clearSession();
      this.navigate('#/login');
    }
  },

  resolve() {
    if (!rootElement) {
      return;
    }
    const path = currentPath();
    if (path === '#/' || path === '') {
      this.navigate(DEFAULT_ROUTE);
      return;
    }

    const route = routes.find((candidate) => candidate.path === path);
    if (!route) {
      if (!sessionState.isAuthenticated()) {
        this.redirectToLogin(path);
        return;
      }
      if (sessionState.mustChangePassword()) {
        this.navigate('#/change-password');
        return;
      }
      renderShell(rootElement, notFoundView(), routes, path);
      return;
    }

    const guard = guardRoute(route, path);
    if (guard === 'login') {
      this.redirectToLogin(path);
      return;
    }
    if (guard === 'change-password') {
      this.navigate('#/change-password');
      return;
    }
    if (guard === 'default') {
      this.navigate(DEFAULT_ROUTE);
      return;
    }
    if (guard === 'denied') {
      renderShell(rootElement, accessDeniedView(), routes, path);
      return;
    }

    const rendered = route.render({ root: rootElement, router: this });
    if (typeof rendered === 'string') {
      if (route.access === 'public' || route.path === '#/change-password') {
        rootElement.innerHTML = rendered;
      } else {
        renderShell(rootElement, rendered, routes, path);
      }
    }
  },
};

function guardRoute(route, path) {
  if (route.access === 'public') {
    if (sessionState.isAuthenticated()) {
      return sessionState.mustChangePassword() ? 'change-password' : 'default';
    }
    return 'allow';
  }
  if (!sessionState.isAuthenticated()) {
    sessionState.setReturnTo(path);
    return 'login';
  }
  if (sessionState.mustChangePassword() && !route.allowDuringMustChange) {
    return 'change-password';
  }
  if (route.access === 'authed') {
    return 'allow';
  }
  return sessionState.hasPermission(route.access) ? 'allow' : 'denied';
}

function currentPath() {
  return window.location.hash || DEFAULT_ROUTE;
}
