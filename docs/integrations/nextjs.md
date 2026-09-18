# Next.js 14 App Router Integration: TitanRAG

This guide demonstrates how to build a real-time AI knowledge assistant in **Next.js 14 (App Router)** powered by **TitanRAG**.

---

## 1. Architecture Overview

- **Route Handler (`/api/chat/route.ts`)**: Proxies client requests to TitanRAG's SSE chat endpoint, keeping your enterprise `TITANRAG_API_KEY` secure on the server.
- **Client Component (`ChatWindow.tsx`)**: Reads the streamed tokens and updates state with zero lag.
- **Embeddable Option**: Alternatively, mount `<titan-chat>` via our shadow DOM script.

---

## 2. Environment Configuration

Add your credentials to `.env.local`:

```env
TITANRAG_API_URL=http://localhost:8000
TITANRAG_API_KEY=titankey_live_xxxxxxxxxxxxxxxxxxxxxxxx
TITANRAG_WORKSPACE_ID=a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## 3. Streaming API Route Handler (`app/api/chat/route.ts`)

```typescript
import { NextRequest, NextResponse } from "next/server";

export const runtime = "edge"; // Edge runtime for ultra-low latency streaming

export async function POST(req: NextRequest) {
  try {
    const { message, history } = await req.json();

    const titanUrl = process.env.TITANRAG_API_URL || "http://localhost:8000";
    const workspaceId = process.env.TITANRAG_WORKSPACE_ID;
    const apiKey = process.env.TITANRAG_API_KEY;

    if (!workspaceId || !apiKey) {
      return NextResponse.json(
        { error: "Server missing TitanRAG configuration." },
        { status: 500 }
      );
    }

    const upstreamResponse = await fetch(
      `${titanUrl}/api/v1/workspaces/${workspaceId}/chat/stream`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${apiKey}`,
          Accept: "text/event-stream",
        },
        body: JSON.stringify({
          message,
          history: history || [],
          stream: true,
        }),
      }
    );

    if (!upstreamResponse.ok || !upstreamResponse.body) {
      const errorText = await upstreamResponse.text();
      return NextResponse.json(
        { error: `TitanRAG error: ${errorText}` },
        { status: upstreamResponse.status }
      );
    }

    // Forward the SSE stream directly to the browser
    return new Response(upstreamResponse.body, {
      headers: {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
      },
    });
  } catch (error: any) {
    return NextResponse.json(
      { error: error?.message || "Internal server error" },
      { status: 500 }
    );
  }
}
```

---

## 4. React Client Component (`components/ChatWindow.tsx`)

```tsx
"use client";

import React, { useState } from "react";

interface Citation {
  title: string;
  url?: string;
  score: number;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
}

export function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsg: Message = { role: "user", content: input.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    const assistantMsg: Message = { role: "assistant", content: "", citations: [] };
    setMessages((prev) => [...prev, assistantMsg]);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMsg.content }),
      });

      if (!res.body) throw new Error("No response stream");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith("data:")) continue;
          const jsonStr = trimmed.slice(5).trim();
          if (jsonStr === "[DONE]") break;

          try {
            const event = JSON.parse(jsonStr);
            if (event.type === "token" || event.delta) {
              const chunk = event.content || event.delta || "";
              setMessages((prev) => {
                const updated = [...prev];
                const last = { ...updated[updated.length - 1] };
                last.content += chunk;
                updated[updated.length - 1] = last;
                return updated;
              });
            } else if (event.type === "citation") {
              setMessages((prev) => {
                const updated = [...prev];
                const last = { ...updated[updated.length - 1] };
                last.citations = [...(last.citations || []), event];
                updated[updated.length - 1] = last;
                return updated;
              });
            }
          } catch (e) {
            // raw text token fallback
            setMessages((prev) => {
              const updated = [...prev];
              const last = { ...updated[updated.length - 1] };
              last.content += jsonStr;
              updated[updated.length - 1] = last;
              return updated;
            });
          }
        }
      }
    } catch (err: any) {
      console.error("Stream failed:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[600px] w-full max-w-2xl border rounded-xl overflow-hidden bg-white dark:bg-zinc-900 shadow-xl">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`p-3 rounded-lg text-sm ${
              msg.role === "user"
                ? "bg-indigo-600 text-white ml-auto max-w-[80%]"
                : "bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 mr-auto max-w-[85%]"
            }`}
          >
            <p className="whitespace-pre-wrap">{msg.content}</p>
            {msg.citations && msg.citations.length > 0 && (
              <div className="mt-2 pt-2 border-t border-zinc-200 dark:border-zinc-700 text-xs text-zinc-500">
                <span className="font-semibold">Sources:</span>
                <ul className="list-disc pl-4 mt-1">
                  {msg.citations.map((c, ci) => (
                    <li key={ci}>{c.title} (relevance: {Math.round(c.score * 100)}%)</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>
      <form onSubmit={sendMessage} className="p-3 border-t flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question..."
          className="flex-1 px-3 py-2 border rounded-lg dark:bg-zinc-800 dark:border-zinc-700"
        />
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 bg-indigo-600 text-white font-medium rounded-lg disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}
```
