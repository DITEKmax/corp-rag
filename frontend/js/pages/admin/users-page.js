import { adminApi } from '../../api/admin-api.js';
import { adminError, checkedValues, formValues, notice } from '../../components/admin/admin-ui.js';
import { renderUserDrawer } from '../../components/admin/user-drawer.js';
import { sessionState } from '../../core/session-state.js';
import { renderAdminLayout } from './admin-layout.js';
import { escapeHtml } from '../../components/ui.js';

let mountVersion = 0;

export function renderUsersPage(routes, activePath) {
  queueMicrotask(() => mountUsersPage(routes, activePath));
  return renderAdminLayout({
    title: 'Users',
    subtitle: 'Create users, disable accounts, reset passwords, and replace user role sets.',
    routes,
    activePath,
    body: '<div data-admin-users-root></div>',
  });
}

function mountUsersPage() {
  const root = document.querySelector('[data-admin-users-root]');
  if (!root) {
    return;
  }
  const token = ++mountVersion;
  const state = { users: [], roles: [], loading: true, drawer: null, tempPassword: '', message: '', error: '' };
  const session = sessionState.snapshot();
  const currentUserId = session.user?.id;
  const capabilities = {
    create: session.permissions.has('users.create'),
    update: session.permissions.has('users.update'),
    delete: session.permissions.has('users.delete'),
  };
  const isActive = () => token === mountVersion && document.body.contains(root);

  root.addEventListener('click', async (event) => {
    const action = event.target?.closest?.('[data-admin-action]');
    if (!action) {
      return;
    }
    const name = action.dataset.adminAction;
    if (name === 'create-user') {
      state.drawer = { type: 'create' };
      state.tempPassword = '';
      render();
    }
    if (name === 'edit-user') {
      state.drawer = { type: 'edit', userId: action.dataset.userId };
      state.tempPassword = '';
      render();
    }
    if (name === 'close-drawer') {
      state.drawer = null;
      render();
    }
    if (name === 'disable-user') {
      await disableUser(action.dataset.userId);
    }
    if (name === 'reset-password') {
      await resetPassword(action.dataset.userId);
    }
  });

  root.addEventListener('submit', async (event) => {
    const form = event.target;
    if (!form?.matches?.('[data-admin-form]')) {
      return;
    }
    event.preventDefault();
    if (form.dataset.adminForm === 'create-user') {
      await createUser(form);
    }
    if (form.dataset.adminForm === 'update-user') {
      await updateUser(form);
    }
    if (form.dataset.adminForm === 'assign-roles') {
      await assignRoles(form);
    }
  });

  load();

  async function load() {
    state.loading = true;
    render();
    try {
      const [users, roles] = await Promise.all([adminApi.listUsers(), adminApi.listRoles()]);
      state.users = users.items || [];
      state.roles = roles.items || [];
      state.error = '';
    } catch (error) {
      state.error = adminError(error);
    } finally {
      state.loading = false;
      render();
    }
  }

  async function createUser(form) {
    const values = formValues(form);
    try {
      const created = await adminApi.createUser({
        username: values.username,
        fullName: values.fullName,
        email: values.email,
        department: values.department,
        roles: checkedValues(form, 'roles'),
      });
      state.tempPassword = created.temporaryPassword;
      state.drawer = { type: 'edit', userId: created.user.id };
      state.message = 'User created.';
      await load();
    } catch (error) {
      state.error = adminError(error);
      render();
    }
  }

  async function updateUser(form) {
    const values = formValues(form);
    try {
      await adminApi.updateUser(form.dataset.userId, {
        fullName: values.fullName,
        email: values.email,
        department: values.department,
      });
      state.message = 'User updated.';
      await load();
    } catch (error) {
      state.error = adminError(error);
      render();
    }
  }

  async function assignRoles(form) {
    if (!window.confirm('Replace this user role set?')) {
      return;
    }
    try {
      await adminApi.assignUserRoles(form.dataset.userId, checkedValues(form, 'roles'));
      state.message = 'Roles updated.';
      await load();
    } catch (error) {
      state.error = adminError(error);
      render();
    }
  }

  async function disableUser(userId) {
    const user = state.users.find((item) => item.id === userId);
    if (!userId || !window.confirm(`Disable "${user?.username || 'user'}"?`)) {
      return;
    }
    try {
      await adminApi.disableUser(userId);
      state.users = state.users.filter((item) => item.id !== userId);
      state.drawer = null;
      state.message = 'User disabled.';
      render();
    } catch (error) {
      state.error = adminError(error);
      render();
    }
  }

  async function resetPassword(userId) {
    if (!userId || !window.confirm('Reset this user password?')) {
      return;
    }
    try {
      const result = await adminApi.resetPassword(userId);
      state.drawer = { type: 'edit', userId };
      state.tempPassword = result.temporaryPassword;
      state.message = 'Password reset.';
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
    const drawerUser = state.drawer?.userId ? state.users.find((user) => user.id === state.drawer.userId) : null;
    root.innerHTML = `
      ${notice(state.message, 'success')}
      ${notice(state.error, 'error')}
      <section class="admin-panel">
        <div class="admin-panel__bar">
          <h2 class="admin-section-title">Users</h2>
          ${capabilities.create ? '<button class="button button--primary" type="button" data-admin-action="create-user">Create user</button>' : ''}
        </div>
        ${state.loading ? '<div class="admin-empty">Loading users...</div>' : renderUserTable(state.users)}
      </section>
      ${state.drawer ? renderUserDrawer({ user: drawerUser, roles: state.roles, currentUserId, tempPassword: state.tempPassword, capabilities }) : ''}
    `;
  }
}

function renderUserTable(users) {
  if (!users.length) {
    return '<div class="admin-empty">No users found.</div>';
  }
  return `
    <div class="admin-table-wrap">
      <table class="admin-table">
        <thead><tr><th>User</th><th>Department</th><th>Roles</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>
          ${users.map((user) => `
            <tr>
              <td><strong>${escapeHtml(user.username)}</strong><span class="admin-muted">${escapeHtml(user.fullName)} · ${escapeHtml(user.email)}</span></td>
              <td>${escapeHtml(user.department)}</td>
              <td>${escapeHtml((user.roles || []).join(', '))}</td>
              <td>${user.active ? 'Active' : 'Disabled'}${user.mustChangePassword ? ' · must change password' : ''}</td>
              <td><button class="button button--ghost" type="button" data-admin-action="edit-user" data-user-id="${escapeHtml(user.id)}">Open</button></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}
