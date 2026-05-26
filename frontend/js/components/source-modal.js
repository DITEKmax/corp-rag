import { escapeHtml } from './ui.js';

const ENTITY_MARKER = /\bentity:[^\s,.;)]+/i;

export function renderSourceModalHost() {
  return '<div class="source-modal-host" data-source-modal></div>';
}

export function openSourceModal(root, citation, index) {
  const host = root.querySelector('[data-source-modal]');
  if (!host || !citation) {
    return;
  }

  host.innerHTML = modalMarkup(citation, index);
  host.querySelector('[data-chat-action="close-source"]')?.focus();
}

export function closeSourceModal(root) {
  const host = root.querySelector('[data-source-modal]');
  if (host) {
    host.innerHTML = '';
  }
}

function modalMarkup(citation, index) {
  const citationNumber = Number.isFinite(index) ? index + 1 : 1;
  const quote = typeof citation.quote === 'string' ? citation.quote.trim() : '';
  const canShowQuote = quote && !ENTITY_MARKER.test(quote);

  return `
    <div class="source-modal" role="dialog" aria-modal="true" aria-labelledby="source-modal-title">
      <div class="source-modal__panel">
        <header class="source-modal__header">
          <div>
            <div class="source-modal__eyebrow">Source [${citationNumber}]</div>
            <h2 class="source-modal__title" id="source-modal-title">${escapeHtml(citation.documentTitle || 'Source')}</h2>
          </div>
          <button class="button button--ghost" type="button" data-chat-action="close-source">Close</button>
        </header>
        <div class="source-modal__meta">
          ${citation.sectionPath ? `<span>${escapeHtml(citation.sectionPath)}</span>` : ''}
          ${citation.pageNumber != null ? `<span>Page ${escapeHtml(citation.pageNumber)}</span>` : ''}
          ${citation.accessLevel ? `<span class="source-modal__badge">${escapeHtml(citation.accessLevel)}</span>` : ''}
        </div>
        ${canShowQuote ? `
          <blockquote class="source-modal__quote">${escapeHtml(quote)}</blockquote>
        ` : `
          <div class="source-modal__error">Source text is unavailable for this citation.</div>
        `}
      </div>
    </div>
  `;
}
