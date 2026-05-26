import { PERMISSION_CODES, PERMISSION_LABELS } from '../../generated/permission-codes.js';
import { escapeHtml } from '../ui.js';
import { checkboxList, renderDrawer } from './admin-ui.js';

export function renderRoleDrawer({ role, canCreate, canUpdate }) {
  const creating = !role;
  const system = Boolean(role?.system);
  const body = `
    ${system ? '<div class="admin-notice">System roles are read-only.</div>' : ''}
    <form class="admin-form" data-admin-form="${creating ? 'create-role' : 'update-role'}" data-role-id="${escapeHtml(role?.id || '')}">
      <label class="admin-field">
        <span>Name</span>
        <input class="admin-input" name="name" value="${escapeHtml(role?.name || '')}" required ${system ? 'disabled' : ''}>
      </label>
      <label class="admin-field">
        <span>Description</span>
        <textarea class="admin-input" name="description" rows="3" ${system ? 'disabled' : ''}>${escapeHtml(role?.description || '')}</textarea>
      </label>
      <div class="admin-field">
        <span>Permissions</span>
        ${renderPermissionChecks(role?.permissions || [], system)}
      </div>
      <div class="admin-form__actions">
        <button class="button button--primary" type="submit" ${system || (creating ? !canCreate : !canUpdate) ? 'disabled' : ''}>${creating ? 'Create role' : 'Save role'}</button>
      </div>
    </form>
  `;
  return renderDrawer(creating ? 'Create role' : `Role: ${role.name}`, body);
}

function renderPermissionChecks(selected, disabled) {
  const selectedSet = new Set(selected || []);
  return `
    <div class="admin-checks admin-checks--columns">
      ${PERMISSION_CODES.map((code) => `
        <label class="admin-check">
          <input type="checkbox" name="permissions" value="${escapeHtml(code)}"${selectedSet.has(code) ? ' checked' : ''}${disabled ? ' disabled' : ''}>
          <span>${escapeHtml(PERMISSION_LABELS[code] || code)}</span>
        </label>
      `).join('')}
    </div>
  `;
}
