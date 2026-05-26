import { escapeHtml } from '../ui.js';
import { renderDrawer } from './admin-ui.js';

export function renderUserDrawer({ user, roles, currentUserId, tempPassword, capabilities }) {
  const creating = !user;
  const assigned = new Set(user?.roles || ['EMPLOYEE']);
  const self = user?.id === currentUserId;
  const body = `
    ${tempPassword ? `<div class="admin-notice admin-notice--success">Temporary password: ${escapeHtml(tempPassword)}</div>` : ''}
    ${self ? '<div class="admin-notice">This is your account. Server-side protections block self-disable and self-role changes.</div>' : ''}
    <form class="admin-form" data-admin-form="${creating ? 'create-user' : 'update-user'}" data-user-id="${escapeHtml(user?.id || '')}">
      ${field('Username', 'username', user?.username || '', creating)}
      ${field('Full name', 'fullName', user?.fullName || '', true)}
      ${field('Email', 'email', user?.email || '', true, 'email')}
      ${field('Department', 'department', user?.department || 'IT', true)}
      ${creating ? renderRoleChecks(roles, assigned) : ''}
      <div class="admin-form__actions">
        <button class="button button--primary" type="submit"${creating ? (capabilities.create ? '' : ' disabled') : (capabilities.update ? '' : ' disabled')}>${creating ? 'Create user' : 'Save profile'}</button>
      </div>
    </form>
    ${creating ? '' : `
      <section class="admin-drawer__section">
        <h3>Roles</h3>
        <form class="admin-form" data-admin-form="assign-roles" data-user-id="${escapeHtml(user.id)}">
          ${renderRoleChecks(roles, assigned)}
          <div class="admin-form__actions">
            <button class="button button--primary" type="submit"${self || !capabilities.update ? ' disabled' : ''}>Save roles</button>
          </div>
        </form>
      </section>
      <section class="admin-drawer__section">
        <h3>Sensitive actions</h3>
        <div class="admin-inline-actions">
          ${capabilities.update ? `<button class="button button--ghost" type="button" data-admin-action="reset-password" data-user-id="${escapeHtml(user.id)}">Reset password</button>` : ''}
          ${capabilities.delete ? `<button class="button button--danger" type="button" data-admin-action="disable-user" data-user-id="${escapeHtml(user.id)}"${self ? ' disabled' : ''}>Disable</button>` : ''}
        </div>
      </section>
    `}
  `;
  return renderDrawer(creating ? 'Create user' : `User: ${user.username}`, body);
}

function field(label, name, value, enabled, type = 'text') {
  return `
    <label class="admin-field">
      <span>${escapeHtml(label)}</span>
      <input class="admin-input" type="${escapeHtml(type)}" name="${escapeHtml(name)}" value="${escapeHtml(value)}"${enabled ? '' : ' disabled'} required>
    </label>
  `;
}

function renderRoleChecks(roles, assigned) {
  return `
    <div class="admin-checks">
      ${roles.map((role) => `
        <label class="admin-check">
          <input type="checkbox" name="roles" value="${escapeHtml(role.name)}"${assigned.has(role.name) ? ' checked' : ''}>
          <span>${escapeHtml(role.name)}</span>
        </label>
      `).join('')}
    </div>
  `;
}
