import { escapeHtml } from '../ui.js';

const CITATION_REF = /\[(\d+)]/g;

export function renderAnswerText(text, citations, messageId) {
  if (!text) {
    return '';
  }

  let html = '';
  let offset = 0;
  for (const match of text.matchAll(CITATION_REF)) {
    const index = Number(match[1]) - 1;
    html += textSegment(text.slice(offset, match.index));
    html += renderInlineReference(match[0], citations?.[index], index, messageId);
    offset = match.index + match[0].length;
  }
  html += textSegment(text.slice(offset));
  return html;
}

export function renderCitationChips(citations, messageId) {
  if (!Array.isArray(citations) || citations.length === 0) {
    return '';
  }

  return `
    <div class="citation-list" aria-label="Sources">
      ${citations.map((citation, index) => `
        <button
          class="citation-chip"
          type="button"
          data-chat-action="open-citation"
          data-message-id="${escapeHtml(messageId)}"
          data-citation-index="${index}">
          <span class="citation-chip__index">[${index + 1}]</span>
          <span class="citation-chip__title">${escapeHtml(citation.documentTitle || 'Source')}</span>
          ${citation.snippet ? `<span class="citation-chip__snippet">${escapeHtml(citation.snippet)}</span>` : ''}
        </button>
      `).join('')}
    </div>
  `;
}

function renderInlineReference(label, citation, index, messageId) {
  if (!citation) {
    return escapeHtml(label);
  }

  return `<button
    class="citation-ref"
    type="button"
    title="${escapeHtml(citation.snippet || citation.quote || citation.documentTitle || 'Source')}"
    data-chat-action="open-citation"
    data-message-id="${escapeHtml(messageId)}"
    data-citation-index="${index}">${escapeHtml(label)}</button>`;
}

function textSegment(value) {
  return escapeHtml(value).replace(/\n/g, '<br>');
}
