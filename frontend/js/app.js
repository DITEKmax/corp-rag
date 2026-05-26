import { configureApiClient, apiClient, ApiError } from './core/api-client.js';
import { router } from './core/router.js';
import { sessionState } from './core/session-state.js';
import { loadingView, serviceUnavailableView } from './components/views.js';

const root = document.querySelector('#app');

configureApiClient({
  onAuthRequired: () => router.redirectToLogin(window.location.hash || '#/chat'),
  onMustChangeRequired: () => router.navigate('#/change-password'),
});

bootstrap();

async function bootstrap() {
  sessionState.setBooting();
  root.innerHTML = loadingView();
  try {
    const user = await apiClient.getMe();
    if (user.mustChangePassword) {
      sessionState.markMustChangePassword(user);
      ensureRouter();
      router.navigate('#/change-password');
      return;
    }
    sessionState.setCurrentUser(user);
    ensureRouter();
  } catch (caught) {
    if (caught instanceof ApiError && caught.status === 401) {
      sessionState.clearSession();
      ensureRouter();
      router.redirectToLogin(window.location.hash || '#/chat');
      return;
    }
    root.innerHTML = serviceUnavailableView();
    root.querySelector('button')?.addEventListener('click', () => bootstrap());
  }
}

let routerStarted = false;

function ensureRouter() {
  if (!routerStarted) {
    router.start(root);
    routerStarted = true;
  } else {
    router.resolve();
  }
}
