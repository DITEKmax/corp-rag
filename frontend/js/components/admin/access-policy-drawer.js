import { escapeHtml } from '../ui.js';
import { ACCESS_LEVELS, DOC_TYPES, checkboxList, renderDrawer } from './admin-ui.js';

export function renderAccessPolicyDrawer({ policy, roles, canCreate, canUpdate }) {
  const creating = !policy;
  const body = `
    <form class="admin-form" data-admin-form="${creating ? 'create-policy' : 'update-policy'}" data-policy-id="${escapeHtml(policy?.id || '')}">
      <label class="admin-field">
        <span>Role</span>
        ${creating ? `
          <select class="admin-input" name="roleId" required>
            ${roles.map((role) => `<option value="${escapeHtml(role.id)}">${escapeHtml(role.name)}</option>`).join('')}
          </select>
        ` : `<input class="admin-input" value="${escapeHtml(policy.roleName || policy.roleId)}" disabled>`}
      </label>
      <div class="admin-field">
        <span>Access levels</span>
        ${checkboxList('accessLevels', ACCESS_LEVELS, policy?.accessLevels || ['PUBLIC'])}
      </div>
      <label class="admin-field">
        <span>Departments</span>
        <input class="admin-input" name="departments" value="${escapeHtml((policy?.departments || []).join(', '))}" placeholder="Blank means all departments">
      </label>
      <div class="admin-field">
        <span>Document types</span>
        ${checkboxList('docTypes', DOC_TYPES, policy?.docTypes || ['POLICY'])}
      </div>
      <div class="admin-form__actions">
        <button class="button button--primary" type="submit"${creating ? (canCreate ? '' : ' disabled') : (canUpdate ? '' : ' disabled')}>${creating ? 'Create policy' : 'Save policy'}</button>
      </div>
    </form>
  `;
  return renderDrawer(creating ? 'Create access policy' : `Policy: ${policy.roleName || policy.roleId}`, body);
}
