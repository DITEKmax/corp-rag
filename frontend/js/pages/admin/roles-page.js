import { adminApi } from '../../api/admin-api.js';
import { adminError, checkedValues, formValues, notice } from '../../components/admin/admin-ui.js';
import { renderRoleDrawer } from '../../components/admin/role-drawer.js';
import { sessionState } from '../../core/session-state.js';
import { renderAdminLayout } from './admin-layout.js';
import { escapeHtml } from '../../components/ui.js';

let mountVersion = 0;

export function renderRolesPage(routes, activePath) {
  queueMicrotask(() => mountRolesPage());
  return renderAdminLayout({
    title: 'Roles',
    subtitle: 'Create roles and edit permission sets from the contract-derived permission list.',
    routes,
    activePath,
    body: '<div data-admin-roles-root></div>',
  });
}

function mountRolesPage() {
  const root = document.querySelector('[data-admin-roles-root]');
  if (!root) {
    return;
  }
  const token = ++mountVersion;
  const state = { roles: [], loading: true, drawer: null, message: '', error: '' };
  const permissions = sessionState.snapshot().permissions;
  const canCreate = permissions.has('roles.create');
  const canUpdate = permissions.has('roles.update');
  const isActive = () => token === mountVersion && document.body.contains(root);

  root.addEventListener('click', (event) => {
    const action = event.target?.closest?.('[data-admin-action]');
    if (!action) {
      return;
    }
    if (action.dataset.adminAction === 'create-role') {
      state.drawer = { type: 'create' };
      render();
    }
    if (action.dataset.adminAction === 'edit-role') {
      state.drawer = { type: 'edit', roleId: action.dataset.roleId };
      render();
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
    if (form.dataset.adminForm === 'create-role') {
      await saveRole(form);
    }
    if (form.dataset.adminForm === 'update-role') {
      await saveRole(form, state.roles.find((role) => role.id === form.dataset.roleId));
    }
  });

  load();

  async function load() {
    state.loading = true;
    render();
    try {
      const page = await adminApi.listRoles();
      state.roles = page.items || [];
      state.error = '';
    } catch (error) {
      state.error = adminError(error);
    } finally {
      state.loading = false;
      render();
    }
  }

  async function saveRole(form, existingRole = null) {
    const values = formValues(form);
    const payload = {
      name: String(values.name || '').toUpperCase(),
      description: values.description || '',
      permissions: checkedValues(form, 'permissions'),
    };
    try {
      if (existingRole) {
        await adminApi.updateRole(existingRole, payload);
        state.message = 'Role updated.';
      } else {
        await adminApi.createRole(payload);
        state.message = 'Role created.';
      }
      state.drawer = null;
      await load();
    } catch (error) {
      state.error = adminError(error);
      render();
    }
  }

  function render() {
    if (!isActive()) {
      return;
    }
    const drawerRole = state.drawer?.roleId ? state.roles.find((role) => role.id === state.drawer.roleId) : null;
    root.innerHTML = `
      ${notice(state.message, 'success')}
      ${notice(state.error, 'error')}
      <section class="admin-panel">
        <div class="admin-panel__bar">
          <h2 class="admin-section-title">Roles</h2>
          ${canCreate ? '<button class="button button--primary" type="button" data-admin-action="create-role">Create role</button>' : ''}
        </div>
        ${state.loading ? '<div class="admin-empty">Loading roles...</div>' : renderRoleTable(state.roles)}
      </section>
      ${state.drawer ? renderRoleDrawer({ role: drawerRole, canCreate, canUpdate }) : ''}
    `;
  }
}

function renderRoleTable(roles) {
  if (!roles.length) {
    return '<div class="admin-empty">No roles found.</div>';
  }
  return `
    <div class="admin-table-wrap">
      <table class="admin-table">
        <thead><tr><th>Name</th><th>Description</th><th>Permissions</th><th>System</th><th>Actions</th></tr></thead>
        <tbody>
          ${roles.map((role) => `
            <tr>
              <td><strong>${escapeHtml(role.name)}</strong></td>
              <td>${escapeHtml(role.description || '')}</td>
              <td>${escapeHtml((role.permissions || []).join(', '))}</td>
              <td>${role.system ? 'Yes' : 'No'}</td>
              <td><button class="button button--ghost" type="button" data-admin-action="edit-role" data-role-id="${escapeHtml(role.id)}">Open</button></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}
