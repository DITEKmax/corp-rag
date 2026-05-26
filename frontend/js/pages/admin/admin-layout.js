import { sessionState } from '../../core/session-state.js';
import { escapeHtml } from '../../components/ui.js';

const ADMIN_STYLE_ID = 'admin-page-styles';

export function renderAdminLayout({ title, subtitle, routes, activePath, body }) {
  ensureAdminStyles();
  return `
    <section class="admin-page">
      <aside class="admin-local-nav">
        <div class="admin-local-nav__title">Admin</div>
        ${renderAdminNav(routes, activePath)}
      </aside>
      <section class="admin-content">
        <header class="admin-content__header">
          <div>
            <h1 class="admin-content__title">${escapeHtml(title)}</h1>
            ${subtitle ? `<p class="admin-content__subtitle">${escapeHtml(subtitle)}</p>` : ''}
          </div>
        </header>
        ${body}
      </section>
    </section>
  `;
}

function renderAdminNav(routes, activePath) {
  const session = sessionState.snapshot();
  return routes
    .filter((route) => route.nav?.show && route.nav.section === 'admin')
    .filter((route) => route.access === 'authed' || session.permissions.has(route.access))
    .map((route) => `
      <a class="admin-local-nav__link${route.path === activePath ? ' admin-local-nav__link--active' : ''}" href="${route.path}">
        ${escapeHtml(route.nav.label)}
      </a>
    `)
    .join('');
}

function ensureAdminStyles() {
  if (document.getElementById(ADMIN_STYLE_ID)) {
    return;
  }
  const link = document.createElement('link');
  link.id = ADMIN_STYLE_ID;
  link.rel = 'stylesheet';
  link.href = '/styles/admin.css';
  document.head.appendChild(link);
}
