import { escapeHtml } from '../ui.js';
import { formatDate, statusPill } from './admin-ui.js';

export function renderDocumentTable(documents, { canDelete = false } = {}) {
  if (!documents.length) {
    return '<div class="admin-empty">No documents visible for this account.</div>';
  }
  return `
    <div class="admin-table-wrap">
      <table class="admin-table">
        <thead>
          <tr>
            <th>Title</th>
            <th>Status</th>
            <th>Access</th>
            <th>Department</th>
            <th>Type</th>
            <th>Uploaded</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${documents.map((document) => `
            <tr>
              <td>
                <strong>${escapeHtml(document.title)}</strong>
                <span class="admin-muted">${escapeHtml(document.originalFilename || '')}</span>
                ${document.failureReason ? `<span class="admin-failure">${escapeHtml(document.failureReason)}</span>` : ''}
              </td>
              <td>${statusPill(document.status)}</td>
              <td>${escapeHtml(document.accessLevel)}</td>
              <td>${escapeHtml(document.department)}</td>
              <td>${escapeHtml(document.docType)}</td>
              <td>${formatDate(document.uploadedAt)}</td>
              <td class="admin-table__actions">
                <button class="button button--ghost" type="button" data-admin-action="open-raw" data-document-id="${escapeHtml(document.id)}">Open raw</button>
                ${canDelete ? `<button class="button button--danger" type="button" data-admin-action="delete-document" data-document-id="${escapeHtml(document.id)}">Delete</button>` : ''}
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}
