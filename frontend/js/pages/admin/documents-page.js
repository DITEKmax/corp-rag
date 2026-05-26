import { adminApi } from '../../api/admin-api.js';
import { ACCESS_LEVELS, DOC_TYPES, LANGUAGES, adminError, notice, options } from '../../components/admin/admin-ui.js';
import { renderDocumentTable } from '../../components/admin/document-table.js';
import { sessionState } from '../../core/session-state.js';
import { renderAdminLayout } from './admin-layout.js';

let mountVersion = 0;

export function renderDocumentsPage(routes, activePath) {
  queueMicrotask(() => mountDocumentsPage(routes, activePath));
  return renderAdminLayout({
    title: 'Documents',
    subtitle: 'Upload, inspect indexing status, open raw files, and delete documents.',
    routes,
    activePath,
    body: '<div data-admin-documents-root></div>',
  });
}

function mountDocumentsPage(routes, activePath) {
  const root = document.querySelector('[data-admin-documents-root]');
  if (!root) {
    return;
  }
  const token = ++mountVersion;
  const state = { documents: [], loading: true, message: '', error: '' };
  const permissions = sessionState.snapshot().permissions;
  const canUpload = permissions.has('documents.upload');
  const canDelete = permissions.has('documents.delete');
  const isActive = () => token === mountVersion && document.body.contains(root);

  root.addEventListener('submit', async (event) => {
    if (!event.target?.matches?.('[data-admin-form="upload-document"]')) {
      return;
    }
    event.preventDefault();
    await upload(event.target);
  });

  root.addEventListener('click', async (event) => {
    const action = event.target?.closest?.('[data-admin-action]');
    if (!action) {
      return;
    }
    if (action.dataset.adminAction === 'delete-document') {
      await deleteDocument(action.dataset.documentId);
    }
    if (action.dataset.adminAction === 'open-raw') {
      await openRaw(action.dataset.documentId);
    }
  });

  load();

  async function load() {
    state.loading = true;
    render();
    try {
      const page = await adminApi.listDocuments();
      if (!isActive()) {
        return;
      }
      state.documents = page.items || [];
      state.error = '';
    } catch (error) {
      state.error = adminError(error);
    } finally {
      state.loading = false;
      render();
    }
  }

  async function upload(form) {
    state.error = '';
    state.message = '';
    render();
    try {
      await adminApi.uploadDocument(new FormData(form));
      form.reset();
      state.message = 'Upload accepted.';
      await load();
    } catch (error) {
      state.error = adminError(error);
      render();
    }
  }

  async function deleteDocument(documentId) {
    const document = state.documents.find((item) => item.id === documentId);
    if (!documentId || !window.confirm(`Delete "${document?.title || 'document'}"?`)) {
      return;
    }
    try {
      await adminApi.deleteDocument(documentId);
      state.documents = state.documents.filter((item) => item.id !== documentId);
      state.message = 'Document deleted.';
      state.error = '';
      render();
    } catch (error) {
      state.error = adminError(error);
      render();
    }
  }

  async function openRaw(documentId) {
    try {
      const raw = await adminApi.getDocumentRaw(documentId);
      if (raw?.url) {
        window.open(raw.url, '_blank', 'noopener');
      }
    } catch (error) {
      state.error = adminError(error);
      render();
    }
  }

  function render() {
    if (!isActive()) {
      return;
    }
    root.innerHTML = `
      ${notice(state.message, 'success')}
      ${notice(state.error, 'error')}
      ${canUpload ? `<form class="admin-panel admin-form admin-form--inline" data-admin-form="upload-document">
        <label class="admin-field">
          <span>File</span>
          <input class="admin-input" type="file" name="file" required>
        </label>
        <label class="admin-field">
          <span>Title</span>
          <input class="admin-input" name="title" maxlength="512" required>
        </label>
        <label class="admin-field">
          <span>Access</span>
          <select class="admin-input" name="accessLevel">${options(ACCESS_LEVELS, 'INTERNAL')}</select>
        </label>
        <label class="admin-field">
          <span>Department</span>
          <input class="admin-input" name="department" value="IT" required>
        </label>
        <label class="admin-field">
          <span>Type</span>
          <select class="admin-input" name="docType">${options(DOC_TYPES, 'POLICY')}</select>
        </label>
        <label class="admin-field">
          <span>Language</span>
          <select class="admin-input" name="language">${options(LANGUAGES, 'en')}</select>
        </label>
        <label class="admin-field admin-field--wide">
          <span>Description</span>
          <input class="admin-input" name="description" maxlength="1000">
        </label>
        <div class="admin-form__actions">
          <button class="button button--primary" type="submit">Upload</button>
        </div>
      </form>` : ''}
      <section class="admin-panel">
        <h2 class="admin-section-title">Documents</h2>
        ${state.loading ? '<div class="admin-empty">Loading documents...</div>' : renderDocumentTable(state.documents, { canDelete })}
      </section>
    `;
  }
}
