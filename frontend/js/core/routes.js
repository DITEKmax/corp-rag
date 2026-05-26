import { renderChatPage } from '../pages/chat-page.js';
import { renderAccessPoliciesPage } from '../pages/admin/access-policies-page.js';
import { renderDocumentsPage } from '../pages/admin/documents-page.js';
import { renderRolesPage } from '../pages/admin/roles-page.js';
import { renderUsersPage } from '../pages/admin/users-page.js';
import { renderChangePasswordPage } from '../pages/change-password-page.js';
import { renderLoginPage } from '../pages/login-page.js';

export const routes = [
  {
    path: '#/login',
    access: 'public',
    render: ({ root, router }) => renderLoginPage(root, router),
    nav: { show: false },
  },
  {
    path: '#/change-password',
    access: 'authed',
    allowDuringMustChange: true,
    render: ({ root, router }) => renderChangePasswordPage(root, router),
    nav: { show: false },
  },
  {
    path: '#/chat',
    access: 'chat.query',
    render: () => renderChatPage(),
    nav: { show: true, label: 'Chat', section: 'main' },
  },
  {
    path: '#/admin/documents',
    access: 'documents.read',
    render: () => renderDocumentsPage(routes, '#/admin/documents'),
    nav: { show: true, label: 'Documents', section: 'admin' },
  },
  {
    path: '#/admin/users',
    access: 'users.read',
    render: () => renderUsersPage(routes, '#/admin/users'),
    nav: { show: true, label: 'Users', section: 'admin' },
  },
  {
    path: '#/admin/roles',
    access: 'roles.read',
    render: () => renderRolesPage(routes, '#/admin/roles'),
    nav: { show: true, label: 'Roles', section: 'admin' },
  },
  {
    path: '#/admin/access-policies',
    access: 'access_policies.read',
    render: () => renderAccessPoliciesPage(routes, '#/admin/access-policies'),
    nav: { show: true, label: 'Access policies', section: 'admin' },
  },
];
