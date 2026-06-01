import { chatApi } from '../api/chat-api.js';
import { ApiError } from '../core/api-client.js';
import { renderMessageList } from '../components/chat/message-list.js';
import { closeSourceModal, openSourceModal, renderSourceModalHost } from '../components/source-modal.js';
import { escapeHtml } from '../components/ui.js';

const CHAT_STYLE_ID = 'chat-page-styles';
let mountVersion = 0;

export function renderChatPage() {
  ensureChatStyles();
  queueMicrotask(() => mountChatPage());
  return `
    <section class="chat-page" data-chat-page>
      <div class="chat-page__loading">Loading conversations...</div>
    </section>
  `;
}

function mountChatPage() {
  const root = document.querySelector('[data-chat-page]');
  if (!root) {
    return;
  }
  const token = ++mountVersion;
  const state = {
    conversations: [],
    messages: [],
    activeConversationId: null,
    loadingConversations: false,
    loadingMessages: false,
    sending: false,
    draft: '',
    error: '',
    composerError: '',
  };

  const isActive = () => token === mountVersion && document.body.contains(root);

  root.addEventListener('click', async (event) => {
    const action = event.target?.closest?.('[data-chat-action]');
    if (!action || !isActive()) {
      return;
    }
    const name = action.dataset.chatAction;
    if (name === 'new-conversation') {
      state.activeConversationId = null;
      state.messages = [];
      state.draft = '';
      state.error = '';
      state.composerError = '';
      render();
    }
    if (name === 'select-conversation') {
      await selectConversation(action.dataset.conversationId);
    }
    if (name === 'delete-conversation') {
      await deleteConversation(action.dataset.conversationId);
    }
    if (name === 'retry-message') {
      await retryMessage(action.dataset.userMessageId);
    }
    if (name === 'open-citation') {
      openCitation(action.dataset.messageId, Number(action.dataset.citationIndex));
    }
    if (name === 'close-source') {
      closeSourceModal(root);
    }
  });

  root.addEventListener('submit', async (event) => {
    if (!event.target?.matches?.('[data-chat-composer]')) {
      return;
    }
    event.preventDefault();
    const text = state.draft.trim();
    if (text) {
      await sendMessage(text, { clearDraft: true });
    }
  });

  root.addEventListener('input', (event) => {
    if (event.target?.matches?.('[data-chat-input]')) {
      state.draft = event.target.value;
      updateComposerSubmitState(event.target, state);
    }
  });

  loadInitial();

  async function loadInitial() {
    state.loadingConversations = true;
    render();
    try {
      const page = await chatApi.listConversations();
      if (!isActive()) {
        return;
      }
      state.conversations = page.items || [];
      state.activeConversationId = state.conversations[0]?.id || null;
      state.error = '';
      state.loadingConversations = false;
      render();
      if (state.activeConversationId) {
        await loadMessages(state.activeConversationId);
      }
    } catch (error) {
      if (!isActive()) {
        return;
      }
      state.loadingConversations = false;
      state.error = describeError(error);
      render();
    }
  }

  async function loadConversations() {
    const page = await chatApi.listConversations();
    if (!isActive()) {
      return;
    }
    state.conversations = page.items || [];
    if (state.activeConversationId && !state.conversations.some((item) => item.id === state.activeConversationId)) {
      state.activeConversationId = state.conversations[0]?.id || null;
    }
  }

  async function loadMessages(conversationId) {
    state.loadingMessages = true;
    render();
    try {
      const page = await chatApi.listMessages(conversationId);
      if (!isActive()) {
        return;
      }
      state.messages = page.items || [];
      state.error = '';
    } catch (error) {
      if (!isActive()) {
        return;
      }
      state.messages = [];
      state.error = describeError(error);
    } finally {
      if (isActive()) {
        state.loadingMessages = false;
        render();
      }
    }
  }

  async function selectConversation(conversationId) {
    if (!conversationId || conversationId === state.activeConversationId || state.sending) {
      return;
    }
    state.activeConversationId = conversationId;
    state.messages = [];
    state.error = '';
    state.composerError = '';
    await loadMessages(conversationId);
  }

  async function deleteConversation(conversationId) {
    if (!conversationId || state.sending) {
      return;
    }
    const conversation = state.conversations.find((item) => item.id === conversationId);
    if (!window.confirm(`Delete "${conversation?.title || 'conversation'}"?`)) {
      return;
    }
    try {
      await chatApi.deleteConversation(conversationId);
      if (!isActive()) {
        return;
      }
      if (state.activeConversationId === conversationId) {
        state.activeConversationId = null;
        state.messages = [];
      }
      await loadConversations();
      if (state.activeConversationId) {
        await loadMessages(state.activeConversationId);
      } else {
        render();
      }
    } catch (error) {
      if (isActive()) {
        state.error = describeError(error);
        render();
      }
    }
  }

  async function retryMessage(userMessageId) {
    if (state.sending) {
      return;
    }
    const message = state.messages.find((item) => item.id === userMessageId && item.role === 'USER');
    if (!message?.content) {
      return;
    }
    await sendMessage(message.content, { clearDraft: false });
  }

  async function sendMessage(text, { clearDraft }) {
    state.sending = true;
    state.composerError = '';
    state.error = '';
    render();

    let conversationId = state.activeConversationId;
    try {
      if (!conversationId) {
        const conversation = await chatApi.createConversation();
        conversationId = conversation.id;
        state.activeConversationId = conversationId;
        state.conversations = [
          conversation,
          ...state.conversations.filter((item) => item.id !== conversation.id),
        ];
      }
      await chatApi.query({ conversationId, message: text });
      if (clearDraft) {
        state.draft = '';
      }
      await loadConversations();
      if (conversationId) {
        state.activeConversationId = conversationId;
        await loadMessages(conversationId);
      }
    } catch (error) {
      if (!isActive()) {
        return;
      }
      if (conversationId && shouldRefreshAfterQueryError(error)) {
        await Promise.allSettled([loadConversations(), loadMessages(conversationId)]);
      }
      state.composerError = composerError(error);
    } finally {
      if (isActive()) {
        state.sending = false;
        render();
      }
    }
  }

  function openCitation(messageId, index) {
    const message = state.messages.find((item) => item.id === messageId);
    const citation = message?.citations?.[index];
    openSourceModal(root, citation, index);
  }

  function render() {
    if (!isActive()) {
      return;
    }
    const activeConversation = state.conversations.find((item) => item.id === state.activeConversationId);
    root.innerHTML = `
      <aside class="chat-sidebar">
        <div class="chat-sidebar__header">
          <div>
            <h1 class="chat-sidebar__title">Conversations</h1>
            <p class="chat-sidebar__count">${state.conversations.length} active</p>
          </div>
          <button class="button button--primary" type="button" data-chat-action="new-conversation">New</button>
        </div>
        <div class="conversation-list" data-chat-conversations>
          ${renderConversations()}
        </div>
      </aside>
      <section class="chat-thread">
        <header class="chat-thread__header">
          <div>
            <h1 class="chat-thread__title">${escapeHtml(activeConversation?.title || 'New conversation')}</h1>
            <p class="chat-thread__meta">${activeConversation ? `${formatDate(activeConversation.updatedAt)} · ${activeConversation.messageCount} messages` : 'Conversation will be created when you send the first message.'}</p>
          </div>
          ${activeConversation ? `<span class="chat-thread__badge">Saved</span>` : '<span class="chat-thread__badge">Draft</span>'}
        </header>
        ${state.error ? `<div class="chat-alert">${escapeHtml(state.error)}</div>` : ''}
        <div class="chat-thread__messages" data-chat-messages>
          ${renderMessageList(state.messages, { loading: state.loadingMessages })}
        </div>
        ${renderComposer()}
      </section>
      ${renderSourceModalHost()}
    `;
  }

  function renderConversations() {
    if (state.loadingConversations) {
      return '<div class="chat-state">Loading...</div>';
    }
    if (!state.conversations.length) {
      return '<div class="chat-empty chat-empty--compact">No conversations yet.</div>';
    }
    return state.conversations.map((conversation) => `
      <div class="conversation-row${conversation.id === state.activeConversationId ? ' conversation-row--active' : ''}">
        <button class="conversation-row__main" type="button" data-chat-action="select-conversation" data-conversation-id="${escapeHtml(conversation.id)}">
          <span class="conversation-row__title">${escapeHtml(conversation.title)}</span>
          <span class="conversation-row__meta">${formatDate(conversation.updatedAt)} · ${conversation.messageCount} messages</span>
        </button>
        <button class="conversation-row__delete" type="button" data-chat-action="delete-conversation" data-conversation-id="${escapeHtml(conversation.id)}" aria-label="Delete conversation">Delete</button>
      </div>
    `).join('');
  }

  function renderComposer() {
    return `
      <form class="chat-composer" data-chat-composer>
        <label class="chat-composer__label" for="chat-message">Message</label>
        <textarea
          class="chat-composer__input"
          id="chat-message"
          name="message"
          data-chat-input
          rows="3"
          maxlength="2000"
          ${state.sending ? 'disabled' : ''}
          placeholder="Ask about your permitted documents">${escapeHtml(state.draft)}</textarea>
        <div class="chat-composer__footer">
          <div class="chat-composer__error">${escapeHtml(state.composerError)}</div>
          <button class="button button--primary" type="submit" ${state.sending || !state.draft.trim() ? 'disabled' : ''}>
            ${state.sending ? 'Sending...' : 'Send'}
          </button>
        </div>
      </form>
    `;
  }
}

function updateComposerSubmitState(input, state) {
  const submit = input.closest('[data-chat-composer]')?.querySelector('button[type="submit"]');
  if (submit) {
    submit.disabled = state.sending || !state.draft.trim();
  }
}

function ensureChatStyles() {
  if (document.getElementById(CHAT_STYLE_ID)) {
    return;
  }
  const link = document.createElement('link');
  link.id = CHAT_STYLE_ID;
  link.rel = 'stylesheet';
  link.href = '/styles/chat.css';
  document.head.appendChild(link);
}

function shouldRefreshAfterQueryError(error) {
  return error instanceof ApiError && (error.status === 422 || error.status === 503);
}

function composerError(error) {
  if (error instanceof ApiError && error.status === 429) {
    const retryAfter = error.response?.headers?.get?.('Retry-After');
    return retryAfter ? `Too many questions. Try again in ${retryAfter} seconds.` : 'Too many questions. Try again shortly.';
  }
  if (shouldRefreshAfterQueryError(error)) {
    return '';
  }
  return describeError(error);
}

function describeError(error) {
  if (error instanceof ApiError) {
    return error.message;
  }
  return 'The chat service did not respond.';
}

function formatDate(value) {
  if (!value) {
    return 'Not updated';
  }
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}
