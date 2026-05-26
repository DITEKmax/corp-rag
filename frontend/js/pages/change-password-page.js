import { apiClient, ApiError } from '../core/api-client.js';
import { sessionState } from '../core/session-state.js';

export function renderChangePasswordPage(root, router) {
  root.innerHTML = `
    <main class="auth-layout">
      <section class="auth-panel">
        <p class="auth-panel__brand">Corp RAG</p>
        <h1 class="auth-panel__title">Change password</h1>
        <form class="form" data-password-form>
          <label class="form__field">
            <span class="form__label">Current password</span>
            <input class="form__input" name="currentPassword" type="password" autocomplete="current-password" required maxlength="200">
          </label>
          <label class="form__field">
            <span class="form__label">New password</span>
            <input class="form__input" name="newPassword" type="password" autocomplete="new-password" required minlength="12" maxlength="200">
          </label>
          <div class="inline-error" data-form-error></div>
          <div class="form__actions">
            <button class="button button--primary" type="submit">Update password</button>
          </div>
        </form>
      </section>
    </main>
  `;

  root.querySelector('[data-password-form]').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const error = root.querySelector('[data-form-error]');
    const submit = form.querySelector('button[type="submit"]');
    error.textContent = '';
    submit.disabled = true;
    try {
      const data = new FormData(form);
      await apiClient.changePassword({
        currentPassword: String(data.get('currentPassword') || ''),
        newPassword: String(data.get('newPassword') || ''),
      });
      const user = await apiClient.getMe();
      sessionState.setCurrentUser(user);
      router.navigate(sessionState.consumeReturnTo());
    } catch (caught) {
      error.textContent = caught instanceof ApiError ? caught.message : 'Password update failed.';
    } finally {
      submit.disabled = false;
    }
  });
}
