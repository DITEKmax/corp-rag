import { adminApi } from '../../api/admin-api.js';
import { adminError, checkedValues, commaValues, formValues, notice } from '../../components/admin/admin-ui.js';
import { renderAccessPolicyDrawer } from '../../components/admin/access-policy-drawer.js';
import { sessionState } from '../../core/session-state.js';
import { renderAdminLayout } from './admin-layout.js';
import { escapeHtml } from '../../components/ui.js';

let mountVersion = 0;

export function renderAccessPoliciesPage(routes, activePath) {
  queueMicrotask(() => mountAccessPoliciesPage());
  return renderAdminLayout({
    title: 'Access policies',
    subtitle: 'Create and maintain role-linked document visibility policies.',
    routes,
    activePath,
    body: '<div data-admin-policies-root></div>',
  });
}

function mountAccessPoliciesPage() {
  const root = document.querySelector('[data-admin-policies-root]');
  if (!root) {
    return;
  }
  const token = ++mountVersion;
  const state = { policies: [], roles: [], loading: true, drawer: null, message: '', error: '' };
  const permissions = sessionState.snapshot().permissions;
  const canCreate = permissions.has('access_policies.create');
  const canUpdate = permissions.has('access_policies.update');
  const canDelete = permissions.has('access_policies.delete');
  const isActive = () => token === mountVersion && document.body.contains(root);

  root.addEventListener('click', async (event) => {
    const action = event.target?.closest?.('[data-admin-action]');
    if (!action) {
      return;
    }
    if (action.dataset.adminAction === 'create-policy') {
      state.drawer = { type: 'create' };
      render();
    }
    if (action.dataset.adminAction === 'edit-policy') {
      state.drawer = { type: 'edit', policyId: action.dataset.policyId };
      render();
    }
    if (action.dataset.adminAction === 'delete-policy') {
      await deletePolicy(action.dataset.policyId);
    }
    if (action.dataset.adminAction === 'close-drawer') {
      state.drawer = null;
      render();
    }
  });

  root.addEventListener('submit', async (event) => {
    const form = event.target;
    if (!form?.matches?.('[data-admin-form]')) {
      return;
    }
    event.preventDefault();
    if (form.dataset.adminForm === 'create-policy') {
      await savePolicy(form);
    }
    if (form.dataset.adminForm === 'update-policy') {
      await savePolicy(form, state.policies.find((policy) => policy.id === form.dataset.policyId));
    }
  });

  load();

  async function load() {
    state.loading = true;
    render();
    try {
      const [policies, roles] = await Promise.all([adminApi.listAccessPolicies(), adminApi.listRoles()]);
      state.policies = policies.items || [];
      state.roles = roles.items || [];
      state.error = '';
    } catch (error) {
      state.error = adminError(error);
    } finally {
      state.loading = false;
      render();
    }
  }

  async function savePolicy(form, existingPolicy = null) {
    const values = formValues(form);
    const payload = {
      accessLevels: checkedValues(form, 'accessLevels'),
      departments: commaValues(values.departments),
      docTypes: checkedValues(form, 'docTypes'),
    };
    try {
      if (existingPolicy) {
        await adminApi.updateAccessPolicy(existingPolicy, payload);
        state.message = 'Policy updated.';
      } else {
        await adminApi.createAccessPolicy({ ...payload, roleId: values.roleId });
        state.message = 'Policy created.';
      }
      state.drawer = null;
      await load();
    } catch (error) {
      state.error = adminError(error);
      render();
    }
  }

  async function deletePolicy(policyId) {
    const policy = state.policies.find((item) => item.id === policyId);
    if (!policyId || !window.confirm(`Delete policy for "${policy?.roleName || 'role'}"?`)) {
      return;
    }
    try {
      await adminApi.deleteAccessPolicy(policyId);
      state.policies = state.policies.filter((item) => item.id !== policyId);
      state.drawer = null;
      state.message = 'Policy deleted.';
      render();
    } catch (error) {
      state.error = adminError(error);
      render();
    }
  }

  function render() {
    if (!isActive()) {
      return;
    }
    const drawerPolicy = state.drawer?.policyId ? state.policies.find((policy) => policy.id === state.drawer.policyId) : null;
    root.innerHTML = `
      ${notice(state.message, 'success')}
      ${notice(state.error, 'error')}
      <section class="admin-panel">
        <div class="admin-panel__bar">
          <h2 class="admin-section-title">Access policies</h2>
          ${canCreate ? '<button class="button button--primary" type="button" data-admin-action="create-policy">Create policy</button>' : ''}
        </div>
        ${state.loading ? '<div class="admin-empty">Loading policies...</div>' : renderPolicyTable(state.policies, { canDelete })}
      </section>
      ${state.drawer ? renderAccessPolicyDrawer({ policy: drawerPolicy, roles: state.roles, canCreate, canUpdate }) : ''}
    `;
  }
}

function renderPolicyTable(policies, { canDelete }) {
  if (!policies.length) {
    return '<div class="admin-empty">No access policies found.</div>';
  }
  return `
    <div class="admin-table-wrap">
      <table class="admin-table">
        <thead><tr><th>Role</th><th>Access</th><th>Departments</th><th>Types</th><th>Actions</th></tr></thead>
        <tbody>
          ${policies.map((policy) => `
            <tr>
              <td><strong>${escapeHtml(policy.roleName || policy.roleId)}</strong></td>
              <td>${escapeHtml((policy.accessLevels || []).join(', '))}</td>
              <td>${escapeHtml((policy.departments || []).length ? policy.departments.join(', ') : 'All')}</td>
              <td>${escapeHtml((policy.docTypes || []).join(', '))}</td>
              <td class="admin-table__actions">
                <button class="button button--ghost" type="button" data-admin-action="edit-policy" data-policy-id="${escapeHtml(policy.id)}">Open</button>
                ${canDelete ? `<button class="button button--danger" type="button" data-admin-action="delete-policy" data-policy-id="${escapeHtml(policy.id)}">Delete</button>` : ''}
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}
