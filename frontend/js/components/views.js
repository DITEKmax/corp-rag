import { button, escapeHtml } from './ui.js';

export function loadingView() {
  return `
    <main class="boot" aria-busy="true">
      <div class="boot__mark"></div>
      <div class="boot__lines">
        <span class="boot__line"></span>
        <span class="boot__line boot__line--short"></span>
      </div>
    </main>
  `;
}

export function accessDeniedView() {
  return `
    <section class="state">
      <h1 class="state__title">Access denied</h1>
      <p class="state__body">Your account does not have permission for this screen.</p>
    </section>
  `;
}

export function notFoundView() {
  return `
    <section class="state">
      <h1 class="state__title">Not found</h1>
      <p class="state__body">This route is not available.</p>
    </section>
  `;
}

export function serviceUnavailableView() {
  return `
    <main class="auth-layout">
      <section class="auth-panel">
        <p class="auth-panel__brand">Corp RAG</p>
        <h1 class="auth-panel__title">Service unavailable</h1>
        <p class="state__body">The backend did not respond. Try again when the service is ready.</p>
        <div class="form__actions">
          ${button('Retry', { variant: 'primary' })}
        </div>
      </section>
    </main>
  `;
}

export function placeholderPage(title, subtitle = '') {
  return `
    <section class="page">
      <header class="page__header">
        <div>
          <h1 class="page__title">${escapeHtml(title)}</h1>
          ${subtitle ? `<p class="page__subtitle">${escapeHtml(subtitle)}</p>` : ''}
        </div>
      </header>
    </section>
  `;
}
