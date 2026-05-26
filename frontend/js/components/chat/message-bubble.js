import { renderCitationChips, renderAnswerText } from './citation-chip.js';
import { renderDiagnosticsPanel } from './diagnostics-panel.js';
import { escapeHtml } from '../ui.js';

const RETRYABLE = new Set(['DEGRADED', 'TIMEOUT', 'AI_UNAVAILABLE']);

const STATUS_COPY = {
  REFUSED_GUARD: {
    title: 'Request refused',
    body: 'I cannot process that request because it conflicts with the workspace safety rules.',
  },
  NO_EVIDENCE: {
    title: 'No supported answer',
    body: 'No supported answer was found in the documents available to you.',
  },
  DEGRADED: {
    title: 'Answer needs source references',
    body: 'The answer could not be formatted with proper source references. Try asking again.',
  },
  TIMEOUT: {
    title: 'Service timed out',
    body: 'The AI service did not respond in time. Retry the question when the service is ready.',
  },
  AI_UNAVAILABLE: {
    title: 'AI service unavailable',
    body: 'The AI service is temporarily unavailable. Retry the question in a moment.',
  },
};

export function renderMessageBubble(message, context = {}) {
  if (message.role === 'USER') {
    return `
      <article class="message message--user" data-message-id="${escapeHtml(message.id)}">
        <div class="message__meta">You</div>
        <div class="message__body">${formatText(message.content || '')}</div>
      </article>
    `;
  }

  if (message.status === 'ANSWERED') {
    return renderAnswered(message);
  }
  return renderOutcome(message, context);
}

export function isRetryableStatus(status) {
  return RETRYABLE.has(status);
}

function renderAnswered(message) {
  const citations = Array.isArray(message.citations) ? message.citations : [];
  return `
    <article class="message message--assistant" data-message-id="${escapeHtml(message.id)}">
      <div class="message__meta">Assistant</div>
      <div class="message__body message__body--answer">
        ${renderAnswerText(message.content || '', citations, message.id)}
      </div>
      ${renderConfidence(message.confidence)}
      ${renderCitationChips(citations, message.id)}
      ${renderDiagnosticsPanel(message.retrievalMeta)}
    </article>
  `;
}

function renderOutcome(message, context) {
  const copy = STATUS_COPY[message.status] || {
    title: 'Response unavailable',
    body: 'The assistant response is unavailable for this turn.',
  };
  const retry = RETRYABLE.has(message.status) && context.previousUserId ? `
    <button
      class="button button--primary message__retry"
      type="button"
      data-chat-action="retry-message"
      data-user-message-id="${escapeHtml(context.previousUserId)}">
      Retry
    </button>
  ` : '';

  return `
    <article class="message message--assistant message--${escapeHtml(String(message.status || 'unknown').toLowerCase().replaceAll('_', '-'))}" data-message-id="${escapeHtml(message.id)}">
      <div class="message__meta">Assistant</div>
      <div class="message__status">
        <h2 class="message__status-title">${escapeHtml(copy.title)}</h2>
        <p class="message__status-body">${escapeHtml(copy.body)}</p>
        ${retry ? `<div class="message__actions">${retry}</div>` : ''}
      </div>
      ${renderDiagnosticsPanel(message.retrievalMeta)}
    </article>
  `;
}

function renderConfidence(value) {
  if (value === undefined || value === null) {
    return '';
  }
  return `<div class="confidence confidence--${confidenceTone(value)}">Confidence: ${confidenceLabel(value)}</div>`;
}

function confidenceLabel(value) {
  if (value >= 0.75) {
    return 'High';
  }
  if (value >= 0.45) {
    return 'Moderate';
  }
  return 'Low';
}

function confidenceTone(value) {
  if (value >= 0.75) {
    return 'high';
  }
  if (value >= 0.45) {
    return 'medium';
  }
  return 'low';
}

function formatText(value) {
  return escapeHtml(value).replace(/\n/g, '<br>');
}
