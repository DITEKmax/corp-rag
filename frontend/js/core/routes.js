import { placeholderPage } from '../components/views.js';
import { renderChatPage } from '../pages/chat-page.js';
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
    render: () => placeholderPage('Documents', 'Operational document management'),
    nav: { show: true, label: 'Documents', section: 'admin' },
  },
  {
    path: '#/admin/users',
    access: 'users.read',
    render: () => placeholderPage('Users', 'User and role assignment operations'),
    nav: { show: true, label: 'Users', section: 'admin' },
  },
  {
    path: '#/admin/roles',
    access: 'roles.read',
    render: () => placeholderPage('Roles', 'Permission-set management'),
    nav: { show: true, label: 'Roles', section: 'admin' },
  },
  {
    path: '#/admin/access-policies',
    access: 'access_policies.read',
    render: () => placeholderPage('Access policies', 'Role-linked document access rules'),
    nav: { show: true, label: 'Access policies', section: 'admin' },
  },
];
