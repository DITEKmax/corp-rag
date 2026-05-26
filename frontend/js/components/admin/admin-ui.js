import { ApiError } from '../../core/api-client.js';
import { escapeHtml } from '../ui.js';

export const ACCESS_LEVELS = ['PUBLIC', 'INTERNAL', 'CONFIDENTIAL', 'RESTRICTED'];
export const DOC_TYPES = ['POLICY', 'REGULATION', 'GUIDE', 'REPORT', 'MANUAL', 'OTHER'];
export const LANGUAGES = ['ru', 'en'];

export function adminError(error) {
  if (error instanceof ApiError) {
    const existing = error.problem?.details?.existingDocumentId;
    if (existing) {
      return `Already uploaded. Existing document: ${existing}`;
    }
    return error.message;
  }
  return 'The admin service did not respond.';
}

export function notice(message, tone = 'info') {
  if (!message) {
    return '';
  }
  return `<div class="admin-notice admin-notice--${escapeHtml(tone)}">${escapeHtml(message)}</div>`;
}

export function formatDate(value) {
  if (!value) {
    return 'Not set';
  }
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

export function renderDrawer(title, body, { open = true } = {}) {
  if (!open) {
    return '';
  }
  return `
    <aside class="admin-drawer" data-admin-drawer>
      <div class="admin-drawer__panel">
        <header class="admin-drawer__header">
          <h2 class="admin-drawer__title">${escapeHtml(title)}</h2>
          <button class="button button--ghost" type="button" data-admin-action="close-drawer">Close</button>
        </header>
        ${body}
      </div>
    </aside>
  `;
}

export function options(values, selectedValue = '') {
  return values.map((value) => `<option value="${escapeHtml(value)}"${value === selectedValue ? ' selected' : ''}>${escapeHtml(value)}</option>`).join('');
}

export function checkboxList(name, values, selected = []) {
  const selectedSet = new Set(selected || []);
  return `
    <div class="admin-checks">
      ${values.map((value) => `
        <label class="admin-check">
          <input type="checkbox" name="${escapeHtml(name)}" value="${escapeHtml(value)}"${selectedSet.has(value) ? ' checked' : ''}>
          <span>${escapeHtml(value)}</span>
        </label>
      `).join('')}
    </div>
  `;
}

export function formValues(form) {
  return Object.fromEntries(new FormData(form).entries());
}

export function checkedValues(form, name) {
  return Array.from(form.querySelectorAll(`input[name="${name}"]:checked`)).map((input) => input.value);
}

export function commaValues(value) {
  return String(value || '')
    .split(',')
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean);
}

export function statusPill(value) {
  return `<span class="admin-pill admin-pill--${escapeHtml(String(value || '').toLowerCase().replaceAll('_', '-'))}">${escapeHtml(value || 'UNKNOWN')}</span>`;
}
