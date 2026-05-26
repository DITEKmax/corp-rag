export function button(label, options = {}) {
  const variant = options.variant ? ` button--${options.variant}` : '';
  return `<button class="button${variant}" type="${options.type || 'button'}"${options.disabled ? ' disabled' : ''}>${escapeHtml(label)}</button>`;
}

export function emptyState(title, body = '') {
  return `
    <section class="empty-state">
      <h2 class="state__title">${escapeHtml(title)}</h2>
      ${body ? `<p class="state__body">${escapeHtml(body)}</p>` : ''}
    </section>
  `;
}

export function errorState(title, body = '') {
  return `
    <section class="error-state">
      <h2 class="state__title">${escapeHtml(title)}</h2>
      ${body ? `<p class="state__body">${escapeHtml(body)}</p>` : ''}
    </section>
  `;
}

export function drawer(id, body = '') {
  return `
    <aside class="drawer" id="${escapeHtml(id)}" aria-hidden="true">
      <div class="drawer__panel">${body}</div>
    </aside>
  `;
}

export function modal(id, body = '') {
  return `
    <div class="modal" id="${escapeHtml(id)}" aria-hidden="true">
      <div class="modal__panel">${body}</div>
    </div>
  `;
}

export function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}
