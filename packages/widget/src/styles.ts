/**
 * Encapsulated Shadow DOM CSS for <titan-chat>.
 * Ensures complete styling isolation from host document.
 */

export const WIDGET_CSS = `
:host {
  --titan-primary: #3b82f6;
  --titan-primary-hover: #2563eb;
  --titan-bg: #0f172a;
  --titan-card-bg: #1e293b;
  --titan-text: #f8fafc;
  --titan-text-muted: #94a3b8;
  --titan-border: rgba(255, 255, 255, 0.1);
  --titan-user-bubble: #2563eb;
  --titan-bot-bubble: #1e293b;
  --titan-radius: 16px;
  --titan-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  color: var(--titan-text);
  box-sizing: border-box;
}

:host(.theme-light) {
  --titan-bg: #ffffff;
  --titan-card-bg: #f8fafc;
  --titan-text: #0f172a;
  --titan-text-muted: #64748b;
  --titan-border: rgba(0, 0, 0, 0.1);
  --titan-user-bubble: #2563eb;
  --titan-bot-bubble: #f1f5f9;
  --titan-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
}

*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

/* Floating Launcher Button */
.launcher-btn {
  position: fixed;
  bottom: 24px;
  right: 24px;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--titan-primary);
  color: #ffffff;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 10px 15px -3px rgba(37, 99, 235, 0.4);
  transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), background-color 0.2s;
  z-index: 999999;
}

:host([position="bottom-left"]) .launcher-btn {
  right: auto;
  left: 24px;
}

:host([position="inline"]) {
  display: block;
  position: relative;
  width: 100%;
  height: 100%;
}

:host([position="inline"]) .launcher-btn {
  display: none !important;
}

:host([position="inline"]) .chat-window {
  position: relative;
  bottom: auto;
  right: auto;
  left: auto;
  width: 100%;
  height: 100%;
  max-width: 100%;
  max-height: 100%;
  opacity: 1;
  transform: none;
  pointer-events: auto;
  border-radius: var(--titan-radius);
}

.launcher-btn:hover {
  transform: scale(1.08);
  background: var(--titan-primary-hover);
}

.launcher-btn svg {
  width: 28px;
  height: 28px;
  fill: currentColor;
}

/* Chat Window Container */
.chat-window {
  position: fixed;
  bottom: 96px;
  right: 24px;
  width: 380px;
  height: 580px;
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 120px);
  background: var(--titan-bg);
  border: 1px solid var(--titan-border);
  border-radius: var(--titan-radius);
  box-shadow: var(--titan-shadow);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  z-index: 999999;
  opacity: 0;
  transform: translateY(16px) scale(0.95);
  pointer-events: none;
  transition: opacity 0.25s cubic-bezier(0.4, 0, 0.2, 1), transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

:host([position="bottom-left"]) .chat-window {
  right: auto;
  left: 24px;
}

.chat-window.open {
  opacity: 1;
  transform: translateY(0) scale(1);
  pointer-events: auto;
}

/* Header */
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  background: var(--titan-card-bg);
  border-bottom: 1px solid var(--titan-border);
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.bot-avatar {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--titan-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: bold;
  font-size: 14px;
}

.header-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--titan-text);
}

.status-badge {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  margin-left: 6px;
}

.close-btn {
  background: transparent;
  border: none;
  color: var(--titan-text-muted);
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  transition: background 0.15s;
}

.close-btn:hover {
  background: var(--titan-border);
  color: var(--titan-text);
}

/* Message Stream Area */
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.message-row {
  display: flex;
  flex-direction: column;
  max-width: 86%;
}

.message-row.user {
  align-self: flex-end;
}

.message-row.bot {
  align-self: flex-start;
}

.message-bubble {
  padding: 12px 14px;
  border-radius: 14px;
  word-break: break-word;
  box-shadow: 0 1px 2px rgba(0,0,0,0.1);
}

.message-row.user .message-bubble {
  background: var(--titan-user-bubble);
  color: #ffffff;
  border-bottom-right-radius: 2px;
}

.message-row.bot .message-bubble {
  background: var(--titan-bot-bubble);
  color: var(--titan-text);
  border: 1px solid var(--titan-border);
  border-bottom-left-radius: 2px;
}

/* Citations & Sources */
.cite-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 6px;
  margin: 0 2px;
  font-size: 11px;
  font-weight: 600;
  border-radius: 4px;
  background: rgba(59, 130, 246, 0.2);
  color: var(--titan-primary);
  border: 1px solid rgba(59, 130, 246, 0.3);
  cursor: pointer;
  transition: all 0.15s;
}

.cite-pill:hover {
  background: var(--titan-primary);
  color: #ffffff;
}

.citations-sheet {
  margin-top: 10px;
  padding: 10px;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--titan-border);
  border-radius: 8px;
  font-size: 12px;
}

.citations-title {
  font-weight: 600;
  color: var(--titan-text-muted);
  margin-bottom: 6px;
}

.citation-item {
  margin-bottom: 6px;
  color: var(--titan-text-muted);
}

.citation-item strong {
  color: var(--titan-text);
}

/* Follow-up Prompts */
.followups-container {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.followup-btn {
  padding: 6px 10px;
  background: var(--titan-card-bg);
  border: 1px solid var(--titan-border);
  border-radius: 20px;
  color: var(--titan-text);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.followup-btn:hover {
  border-color: var(--titan-primary);
  color: var(--titan-primary);
}

/* Code Blocks */
.code-block {
  background: #000000;
  border-radius: 8px;
  margin: 8px 0;
  overflow-x: auto;
}

.code-header {
  display: flex;
  justify-content: space-between;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.05);
  font-size: 11px;
  color: var(--titan-text-muted);
  border-bottom: 1px solid var(--titan-border);
}

.copy-btn {
  background: transparent;
  border: none;
  color: var(--titan-text-muted);
  font-size: 11px;
  cursor: pointer;
}

.code-block code {
  display: block;
  padding: 10px;
  font-family: monospace;
  font-size: 12px;
  color: #38bdf8;
}

.inline-code {
  background: rgba(0, 0, 0, 0.3);
  padding: 2px 4px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 12px;
}

/* Input Area */
.chat-input-area {
  padding: 12px;
  background: var(--titan-card-bg);
  border-top: 1px solid var(--titan-border);
  display: flex;
  gap: 8px;
}

.chat-input {
  flex: 1;
  background: var(--titan-bg);
  border: 1px solid var(--titan-border);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
  color: var(--titan-text);
  outline: none;
  resize: none;
  height: 40px;
  max-height: 100px;
}

.chat-input:focus {
  border-color: var(--titan-primary);
}

.send-btn {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: var(--titan-primary);
  border: none;
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}

.send-btn:hover {
  background: var(--titan-primary-hover);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
`;
