/**
 * @titanrag/widget - Zero-dependency Shadow DOM embeddable chat widget for TitanRAG
 */

export interface WidgetCitation {
  id?: string;
  document_id?: string;
  filename?: string;
  page?: number;
  snippet?: string;
}

export interface ChatMessage {
  role: "user" | "bot";
  content: string;
  citations?: WidgetCitation[];
  followUps?: string[];
  isStreaming?: boolean;
}

export declare class TitanChatElement extends HTMLElement {
  static get observedAttributes(): string[];
  connectedCallback(): void;
  disconnectedCallback(): void;
  attributeChangedCallback(name: string, oldValue: string | null, newValue: string | null): void;
  toggleChat(forceOpen?: boolean): void;
}

declare global {
  interface HTMLElementTagNameMap {
    "titan-chat": TitanChatElement;
  }
}
