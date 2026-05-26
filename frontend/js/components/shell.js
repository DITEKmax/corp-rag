import { sessionState } from '../core/session-state.js';
import { escapeHtml } from './ui.js';

const SECTION_LABELS = {
  main: 'Workspace',
  admin: 'Admin',
};

export function renderShell(root, content, routes, activePath) {
  const session = sessionState.snapshot();
  root.innerHTML = `
    <div class="shell">
      <aside class="shell__sidebar">
        <div class="shell__brand">
          <span class="shell__brand-name">Corp RAG</span>
          <span class="shell__brand-meta">Knowledge console</span>
        </div>
        <nav class="shell__nav" aria-label="Primary">
          ${renderNav(routes, activePath)}
        </nav>
        <div class="shell__user">
          <span class="shell__user-name">${escapeHtml(session.user?.fullName || session.user?.username || 'User')}</span>
          <span class="shell__user-meta">${escapeHtml(session.user?.department || '')}</span>
          <button class="button button--ghost" type="button" data-action="logout">Log out</button>
        </div>
      </aside>
      <main class="shell__main" id="main-content">${content}</main>
    </div>
  `;
}

function renderNav(routes, activePath) {
  const visible = routes.filter((route) => route.nav?.show && canAccess(route));
  const grouped = new Map();
  for (const route of visible) {
    const section = route.nav.section || 'main';
    if (!grouped.has(section)) {
      grouped.set(section, []);
    }
    grouped.get(section).push(route);
  }

  return Array.from(grouped.entries()).map(([section, items]) => `
    <div class="shell__nav-section">
      <div class="shell__nav-title">${escapeHtml(SECTION_LABELS[section] || section)}</div>
      ${items.map((route) => `
        <a class="shell__nav-link${route.path === activePath ? ' shell__nav-link--active' : ''}" href="${route.path}">
          ${escapeHtml(route.nav.label)}
        </a>
      `).join('')}
    </div>
  `).join('');
}

function canAccess(route) {
  const session = sessionState.snapshot();
  if (sessionState.mustChangePassword() && !route.allowDuringMustChange) {
    return false;
  }
  if (route.access === 'public') {
    return false;
  }
  if (route.access === 'authed') {
    return sessionState.isAuthenticated();
  }
  return session.permissions.has(route.access);
}
