import { apiClient, ApiError } from '../core/api-client.js';
import { sessionState } from '../core/session-state.js';

export function renderLoginPage(root, router) {
  root.innerHTML = `
    <main class="auth-layout">
      <section class="auth-panel">
        <p class="auth-panel__brand">Corp RAG</p>
        <h1 class="auth-panel__title">Sign in</h1>
        <form class="form" data-login-form>
          <label class="form__field">
            <span class="form__label">Username</span>
            <input class="form__input" name="username" autocomplete="username" required maxlength="64">
          </label>
          <label class="form__field">
            <span class="form__label">Password</span>
            <input class="form__input" name="password" type="password" autocomplete="current-password" required minlength="8" maxlength="200">
          </label>
          <div class="inline-error" data-form-error></div>
          <div class="form__actions">
            <button class="button button--primary" type="submit">Sign in</button>
          </div>
        </form>
      </section>
    </main>
  `;

  root.querySelector('[data-login-form]').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const error = root.querySelector('[data-form-error]');
    const submit = form.querySelector('button[type="submit"]');
    error.textContent = '';
    submit.disabled = true;
    try {
      const data = new FormData(form);
      await apiClient.login({
        username: String(data.get('username') || ''),
        password: String(data.get('password') || ''),
      });
      const user = await apiClient.getMe();
      if (user.mustChangePassword) {
        sessionState.markMustChangePassword(user);
        router.navigate('#/change-password');
        return;
      }
      sessionState.setCurrentUser(user);
      router.navigate(sessionState.consumeReturnTo());
    } catch (caught) {
      error.textContent = caught instanceof ApiError ? caught.message : 'Sign in failed.';
    } finally {
      submit.disabled = false;
    }
  });
}
