export interface WidgetCitation {
  id?: string;
  document_id?: string;
  filename?: string;
  page?: number;
  snippet?: string;
}

export interface StreamCallbacks {
  onStatus?: (status: string, message: string) => void;
  onToken: (token: string) => void;
  onCitation: (citation: WidgetCitation) => void;
  onDone: (fullAnswer: string, followUps: string[], sessionId?: string) => void;
  onError: (error: string) => void;
}

export class ChatEngine {
  private baseUrl: string;
  private workspaceId: string;
  private apiKey: string;
  private sessionId?: string;
  private abortController?: AbortController;

  constructor(options: { baseUrl: string; workspaceId: string; apiKey: string; sessionId?: string }) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.workspaceId = options.workspaceId;
    this.apiKey = options.apiKey;
    this.sessionId = options.sessionId;
  }

  public async sendMessage(query: string, callbacks: StreamCallbacks): Promise<void> {
    this.abort();
    this.abortController = new AbortController();

    const url = `${this.baseUrl}/api/v1/workspaces/${this.workspaceId}/chat/stream`;
    const payload: Record<string, any> = {
      query,
      grounding_mode: "Balanced",
    };
    if (this.sessionId) {
      payload.session_id = this.sessionId;
    }

    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "text/event-stream",
          "X-API-Key": this.apiKey,
        },
        body: json_stringify(payload),
        signal: this.abortController.signal,
      });

      if (!response.ok) {
        let errMsg = `HTTP error ${response.status}`;
        try {
          const errData = await response.json();
          errMsg = errData.error?.message || errMsg;
        } catch {
          // ignore json parse error
        }
        callbacks.onError(errMsg);
        return;
      }

      if (!response.body) {
        callbacks.onError("ReadableStream not supported by server");
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let fullAnswer = "";
      let followUps: string[] = [];

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || trimmed.startsWith(":") || trimmed === "data: [DONE]") {
            continue;
          }

          if (trimmed.startsWith("data:")) {
            const dataStr = trimmed.slice(5).trim();
            try {
              const data = JSON.parse(dataStr);
              const type = data.type || "token";

              if (type === "token") {
                const token = data.token ?? data.content ?? "";
                fullAnswer += token;
                callbacks.onToken(token);
              } else if (type === "citation") {
                const rawCite = data.citation || data;
                callbacks.onCitation({
                  id: rawCite.id || rawCite.citation_id,
                  document_id: rawCite.document_id,
                  filename: rawCite.filename || rawCite.document_name,
                  page: rawCite.page || 1,
                  snippet: rawCite.snippet || rawCite.text || "",
                });
              } else if (type === "status") {
                callbacks.onStatus?.(data.status || "", data.message || "");
              } else if (type === "done") {
                if (data.session_id) this.sessionId = data.session_id;
                followUps = data.follow_up_questions || [];
              } else if (type === "error") {
                callbacks.onError(data.error || "Streaming error");
              }
            } catch {
              // Raw text chunk fallback
              fullAnswer += dataStr;
              callbacks.onToken(dataStr);
            }
          }
        }
      }

      callbacks.onDone(fullAnswer, followUps, this.sessionId);
    } catch (err: any) {
      if (err.name === "AbortError") return;
      callbacks.onError(err.message || "Network request failed");
    } finally {
      this.abortController = undefined;
    }
  }

  public abort(): void {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = undefined;
    }
  }

  public getSessionId(): string | undefined {
    return this.sessionId;
  }
}

function json_stringify(val: any): string {
  return JSON.stringify(val);
}
