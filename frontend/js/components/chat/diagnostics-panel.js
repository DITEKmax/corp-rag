import { escapeHtml } from '../ui.js';

export function renderDiagnosticsPanel(meta) {
  if (!meta) {
    return '';
  }

  const warnings = Array.isArray(meta.degradationWarnings) ? meta.degradationWarnings : [];
  return `
    <details class="diagnostics">
      <summary class="diagnostics__summary">Diagnostics</summary>
      <dl class="diagnostics__grid">
        ${row('Route', meta.route)}
        ${row('Retrievers attempted', list(meta.retrieversAttempted))}
        ${row('Retrievers used', list(meta.retrieversUsed))}
        ${row('Latency', meta.latencyMs != null ? `${meta.latencyMs} ms` : '')}
        ${row('Chunks', chunkSummary(meta))}
        ${row('Reranker', meta.rerankerUsed ? 'Used' : 'Not used')}
        ${row('Model', meta.modelId)}
      </dl>
      ${warnings.length ? `
        <div class="diagnostics__warnings">
          <span class="diagnostics__label">Warnings</span>
          <ul class="diagnostics__warning-list">
            ${warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join('')}
          </ul>
        </div>
      ` : ''}
    </details>
  `;
}

function row(label, value) {
  if (value === undefined || value === null || value === '') {
    return '';
  }
  return `
    <dt>${escapeHtml(label)}</dt>
    <dd>${escapeHtml(value)}</dd>
  `;
}

function list(value) {
  return Array.isArray(value) && value.length ? value.join(', ') : '';
}

function chunkSummary(meta) {
  if (meta.chunksConsidered == null && meta.chunksReturned == null) {
    return '';
  }
  return `${meta.chunksReturned ?? 0} returned / ${meta.chunksConsidered ?? 0} considered`;
}
