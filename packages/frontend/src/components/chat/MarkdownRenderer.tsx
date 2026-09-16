"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CodeBlock } from "./CodeBlock";
import { CitationPill } from "./CitationPill";
import { CitationPayload } from "@/lib/api";

export interface MarkdownRendererProps {
  content: string;
  citations?: CitationPayload[];
  onCitationClick?: (citation: CitationPayload) => void;
}

export function MarkdownRenderer({
  content,
  citations = [],
  onCitationClick,
}: MarkdownRendererProps) {
  // Map citations by source_index
  const citationMap = new Map<number, CitationPayload>();
  citations.forEach((c) => citationMap.set(c.source_index, c));

  // Helper to render text with inline citation pill replacements
  const renderTextWithCitations = (text: string) => {
    // Regex matching [^1] or [Source 1]
    const regex = /\[(?:\^|Source\s+)(\d+)\]/g;
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(text)) !== null) {
      const idx = parseInt(match[1], 10);
      if (match.index > lastIndex) {
        parts.push(text.substring(lastIndex, match.index));
      }

      const citation = citationMap.get(idx);
      parts.push(
        <CitationPill
          key={`${match.index}-${idx}`}
          sourceIndex={idx}
          citation={citation}
          onClick={(c) => onCitationClick && onCitationClick(c)}
        />
      );
      lastIndex = regex.lastIndex;
    }

    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex));
    }

    return parts;
  };

  return (
    <div className="prose prose-invert prose-sm max-w-none space-y-2 leading-relaxed text-slate-200">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || "");
            const codeString = String(children).replace(/\n$/, "");
            if (match) {
              return <CodeBlock language={match[1]} value={codeString} />;
            }
            return (
              <code
                className="bg-slate-800/80 text-sky-300 px-1.5 py-0.5 rounded font-mono text-xs border border-slate-700/60"
                {...props}
              >
                {children}
              </code>
            );
          },
          p({ children }) {
            if (typeof children === "string") {
              return <p className="mb-2 leading-relaxed">{renderTextWithCitations(children)}</p>;
            }
            return <p className="mb-2 leading-relaxed">{children}</p>;
          },
          table({ children }) {
            return (
              <div className="my-3 overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/50">
                <table className="w-full text-left text-xs text-slate-300">{children}</table>
              </div>
            );
          },
          th({ children }) {
            return (
              <th className="border-b border-slate-800 bg-slate-800/40 p-2.5 font-bold text-slate-200">
                {children}
              </th>
            );
          },
          td({ children }) {
            return <td className="border-b border-slate-800/50 p-2.5">{children}</td>;
          },
          ul({ children }) {
            return <ul className="list-disc pl-5 space-y-1 mb-2">{children}</ul>;
          },
          ol({ children }) {
            return <ol className="list-decimal pl-5 space-y-1 mb-2">{children}</ol>;
          },
          li({ children }) {
            return <li className="text-slate-300">{children}</li>;
          },
          blockquote({ children }) {
            return (
              <blockquote className="border-l-2 border-sky-500 pl-3 italic text-slate-400 my-2">
                {children}
              </blockquote>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
