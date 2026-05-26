import { renderMessageBubble } from './message-bubble.js';

export function renderMessageList(messages, { loading = false } = {}) {
  if (loading) {
    return `
      <div class="chat-state" aria-busy="true">
        <div class="chat-state__line"></div>
        <div class="chat-state__line chat-state__line--short"></div>
      </div>
    `;
  }

  if (!messages.length) {
    return `
      <section class="chat-empty">
        <h2 class="chat-empty__title">No messages yet</h2>
        <p class="chat-empty__body">Ask a question to start this conversation.</p>
      </section>
    `;
  }

  let previousUser = null;
  return `
    <div class="message-list">
      ${messages.map((message) => {
        if (message.role === 'USER') {
          previousUser = message;
          return renderMessageBubble(message);
        }
        const rendered = renderMessageBubble(message, { previousUserId: previousUser?.id });
        previousUser = null;
        return rendered;
      }).join('')}
    </div>
  `;
}
