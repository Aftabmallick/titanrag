import { ChatEngine, WidgetCitation } from "./chat-engine";
import { renderMarkdown } from "./markdown-renderer";
import { WIDGET_CSS } from "./styles";

interface ChatMessage {
  role: "user" | "bot";
  content: string;
  citations?: WidgetCitation[];
  followUps?: string[];
  isStreaming?: boolean;
}

export class TitanChatElement extends HTMLElement {
  private shadow: ShadowRoot;
  private engine?: ChatEngine;
  private messages: ChatMessage[] = [];
  private isOpen: boolean = false;

  // DOM elements inside Shadow DOM
  private windowEl!: HTMLElement;
  private launcherBtn!: HTMLElement;
  private messagesEl!: HTMLElement;
  private inputEl!: HTMLInputElement;
  private sendBtn!: HTMLButtonElement;

  static get observedAttributes() {
    return ["workspace", "api-key", "base-url", "theme", "position", "accent-color", "bot-name"];
  }

  constructor() {
    super();
    this.shadow = this.attachShadow({ mode: "open" });
  }

  connectedCallback() {
    this.initDOM();
    this.initEngine();
    this.applyTheme();
  }

  attributeChangedCallback(name: string, oldValue: string, newValue: string) {
    if (oldValue === newValue) return;
    if (name === "workspace" || name === "api-key" || name === "base-url") {
      this.initEngine();
    } else if (name === "theme" || name === "accent-color") {
      this.applyTheme();
    }
  }

  private initEngine() {
    const workspace = this.getAttribute("workspace") || "";
    const apiKey = this.getAttribute("api-key") || "";
    const baseUrl = this.getAttribute("base-url") || window.location.origin;

    if (workspace && apiKey) {
      this.engine = new ChatEngine({
        workspaceId: workspace,
        apiKey: apiKey,
        baseUrl: baseUrl,
      });
    }
  }

  private applyTheme() {
    const theme = this.getAttribute("theme") || "dark";
    if (theme === "light") {
      this.classList.add("theme-light");
    } else {
      this.classList.remove("theme-light");
    }

    const accent = this.getAttribute("accent-color");
    if (accent) {
      this.style.setProperty("--titan-primary", accent);
    }
  }

  private initDOM() {
    const botName = this.getAttribute("bot-name") || "Titan Assistant";

    this.shadow.innerHTML = `
      <style>${WIDGET_CSS}</style>
      <button class="launcher-btn" aria-label="Open Chat">
        <svg viewBox="0 0 24 24">
          <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/>
        </svg>
      </button>

      <div class="chat-window" role="dialog">
        <div class="chat-header">
          <div class="header-brand">
            <div class="bot-avatar">TR</div>
            <div class="header-title">${escapeHtml(botName)}<span class="status-badge" title="Online"></span></div>
          </div>
          <button class="close-btn" aria-label="Close Chat">✕</button>
        </div>

        <div class="messages-container">
          <div class="message-row bot">
            <div class="message-bubble">
              <p>Hello! How can I assist you with this workspace today?</p>
            </div>
          </div>
        </div>

        <div class="chat-input-area">
          <input type="text" class="chat-input" placeholder="Ask a question..." />
          <button class="send-btn" aria-label="Send Message">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
            </svg>
          </button>
        </div>
      </div>
    `;

    this.windowEl = this.shadow.querySelector(".chat-window") as HTMLElement;
    this.launcherBtn = this.shadow.querySelector(".launcher-btn") as HTMLElement;
    this.messagesEl = this.shadow.querySelector(".messages-container") as HTMLElement;
    this.inputEl = this.shadow.querySelector(".chat-input") as HTMLInputElement;
    this.sendBtn = this.shadow.querySelector(".send-btn") as HTMLButtonElement;

    // Event listeners
    this.launcherBtn.addEventListener("click", () => this.toggleChat());
    this.shadow.querySelector(".close-btn")?.addEventListener("click", () => this.toggleChat(false));

    this.inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        this.handleSend();
      }
    });

    this.sendBtn.addEventListener("click", () => this.handleSend());

    // Delegate copy and follow-up clicks inside message container
    this.messagesEl.addEventListener("click", (e) => {
      const target = e.target as HTMLElement;
      if (target.classList.contains("copy-btn")) {
        const code = target.getAttribute("data-code") || "";
        navigator.clipboard.writeText(code).then(() => {
          target.innerText = "Copied!";
          setTimeout(() => (target.innerText = "Copy"), 2000);
        });
      } else if (target.classList.contains("followup-btn")) {
        const query = target.innerText.trim();
        this.inputEl.value = query;
        this.handleSend();
      }
    });
  }

  public toggleChat(open?: boolean) {
    this.isOpen = open !== undefined ? open : !this.isOpen;
    if (this.isOpen) {
      this.windowEl.classList.add("open");
      setTimeout(() => this.inputEl.focus(), 150);
    } else {
      this.windowEl.classList.remove("open");
    }
  }

  private async handleSend() {
    const text = this.inputEl.value.trim();
    if (!text) return;

    if (!this.engine) {
      this.appendMessage({
        role: "bot",
        content: "Error: Missing workspace or API key attribute on <titan-chat>.",
      });
      return;
    }

    this.inputEl.value = "";
    this.sendBtn.disabled = true;

    // Append user message
    this.appendMessage({ role: "user", content: text });

    // Prepare bot message placeholder for streaming
    const botMsg: ChatMessage = {
      role: "bot",
      content: "",
      citations: [],
      isStreaming: true,
    };
    this.messages.push(botMsg);
    const botMsgRow = this.createMessageElement(botMsg);
    this.messagesEl.appendChild(botMsgRow);
    this.scrollToBottom();

    const bubbleEl = botMsgRow.querySelector(".message-bubble") as HTMLElement;

    await this.engine.sendMessage(text, {
      onToken: (token) => {
        botMsg.content += token;
        bubbleEl.innerHTML = renderMarkdown(botMsg.content);
        this.scrollToBottom();
      },
      onCitation: (citation) => {
        if (!botMsg.citations) botMsg.citations = [];
        botMsg.citations.push(citation);
      },
      onDone: (fullAnswer, followUps) => {
        botMsg.isStreaming = false;
        botMsg.followUps = followUps;
        this.renderFinalBotMessage(botMsgRow, botMsg);
        this.sendBtn.disabled = false;
        this.scrollToBottom();
      },
      onError: (errMsg) => {
        botMsg.isStreaming = false;
        bubbleEl.innerHTML = `<span style="color:#ef4444;">Error: ${escapeHtml(errMsg)}</span>`;
        this.sendBtn.disabled = false;
        this.scrollToBottom();
      },
    });
  }

  private appendMessage(msg: ChatMessage) {
    this.messages.push(msg);
    const el = this.createMessageElement(msg);
    this.messagesEl.appendChild(el);
    this.scrollToBottom();
  }

  private createMessageElement(msg: ChatMessage): HTMLElement {
    const row = document.createElement("div");
    row.className = `message-row ${msg.role}`;
    row.innerHTML = `<div class="message-bubble">${renderMarkdown(msg.content)}</div>`;
    return row;
  }

  private renderFinalBotMessage(row: HTMLElement, msg: ChatMessage) {
    const bubble = row.querySelector(".message-bubble") as HTMLElement;
    bubble.innerHTML = renderMarkdown(msg.content);

    // Render citations sheet if any citations exist
    if (msg.citations && msg.citations.length > 0) {
      const citeSheet = document.createElement("div");
      citeSheet.className = "citations-sheet";
      citeSheet.innerHTML = `
        <div class="citations-title">Sources & References (${msg.citations.length})</div>
        ${msg.citations
          .map(
            (c, idx) => `
          <div class="citation-item">
            [${idx + 1}] <strong>${escapeHtml(c.filename || "Document")}</strong> (Page ${c.page || 1}):
            <em>"${escapeHtml((c.snippet || "").slice(0, 100))}..."</em>
          </div>
        `
          )
          .join("")}
      `;
      bubble.appendChild(citeSheet);
    }

    // Render follow-ups
    if (msg.followUps && msg.followUps.length > 0) {
      const followupsEl = document.createElement("div");
      followupsEl.className = "followups-container";
      followupsEl.innerHTML = msg.followUps
        .map((f) => `<button class="followup-btn">${escapeHtml(f)}</button>`)
        .join("");
      row.appendChild(followupsEl);
    }
  }

  private scrollToBottom() {
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
  }
}

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, "");
}

// Auto-register Custom Element
if (typeof window !== "undefined" && !customElements.get("titan-chat")) {
  customElements.define("titan-chat", TitanChatElement);
}
