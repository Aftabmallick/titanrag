"use client";

import React, { useRef, useEffect, useState } from "react";
import { ArrowUp, Square, Paperclip, X, Image as ImageIcon } from "lucide-react";
import { StreamStatus } from "@/hooks/useChatStream";

export interface ChatInputProps {
  query: string;
  setQuery: (q: string) => void;
  onSend: (attachedImageBase64?: string) => void;
  onStop: () => void;
  status: StreamStatus;
  disabled?: boolean;
}

export function ChatInput({
  query,
  setQuery,
  onSend,
  onStop,
  status,
  disabled = false,
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [attachedImage, setAttachedImage] = useState<string | null>(null);
  const [imageMime, setImageMime] = useState<string>("image/png");
  const [isDragging, setIsDragging] = useState(false);

  const isStreaming = status === "retrieving" || status === "streaming";

  // Auto-resize textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        180
      )}px`;
    }
  }, [query]);

  const processFile = (file: File) => {
    if (!file.type.startsWith("image/")) return;
    setImageMime(file.type);
    const reader = new FileReader();
    reader.onload = (e) => {
      const result = e.target?.result as string;
      if (result) {
        setAttachedImage(result);
      }
    };
    reader.readAsDataURL(file);
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith("image/")) {
        const file = items[i].getAsFile();
        if (file) {
          e.preventDefault();
          processFile(file);
          break;
        }
      }
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file && file.type.startsWith("image/")) {
      processFile(file);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isStreaming && (query.trim() || attachedImage)) {
        const base64Clean = attachedImage ? attachedImage.split(",")[1] : undefined;
        onSend(base64Clean);
        setAttachedImage(null);
      }
    }
  };

  const handleSendClick = () => {
    if (!isStreaming && (query.trim() || attachedImage)) {
      const base64Clean = attachedImage ? attachedImage.split(",")[1] : undefined;
      onSend(base64Clean);
      setAttachedImage(null);
    }
  };

  return (
    <div
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      className={`relative rounded-2xl border bg-slate-900/90 shadow-2xl p-2.5 transition-all ${
        isDragging
          ? "border-sky-400 bg-sky-950/40 ring-2 ring-sky-400/40"
          : "border-slate-800 focus-within:border-sky-500/80 focus-within:ring-2 focus-within:ring-sky-500/20"
      }`}
    >
      {/* Attached Image Preview */}
      {attachedImage && (
        <div className="relative inline-block mb-2 ml-1 p-1 bg-slate-800/80 border border-slate-700 rounded-xl">
          <img
            src={attachedImage}
            alt="Uploaded diagram preview"
            className="h-20 w-auto rounded-lg object-contain"
          />
          <button
            type="button"
            onClick={() => setAttachedImage(null)}
            className="absolute -top-1.5 -right-1.5 p-0.5 rounded-full bg-slate-700 hover:bg-rose-600 text-white shadow-md transition-colors"
            title="Remove image"
          >
            <X className="w-3.5 h-3.5" />
          </button>
          <div className="flex items-center gap-1 text-[10px] text-sky-400 mt-0.5 px-1 font-mono">
            <ImageIcon className="w-3 h-3" />
            <span>Multi-modal Vision Ready</span>
          </div>
        </div>
      )}

      <textarea
        ref={textareaRef}
        rows={1}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        placeholder={
          attachedImage
            ? "Ask a question about this attached image or diagram..."
            : "Ask a question across your workspace documents (Paste/Drop images, Enter to send)..."
        }
        disabled={disabled}
        className="w-full bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none resize-none px-2 py-1 max-h-[180px] leading-relaxed disabled:opacity-50"
      />

      {/* Hidden file input for attachment */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) processFile(f);
        }}
      />

      <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 mt-1">
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-slate-800 transition-colors"
            title="Attach image or diagram for vision query"
          >
            <Paperclip className="w-4 h-4" />
          </button>
          <span className="text-[11px] text-slate-500 hidden sm:inline">
            Press <kbd className="font-mono bg-slate-800 px-1 py-0.5 rounded text-[10px]">↵ Enter</kbd> to send
          </span>
        </div>

        <div>
          {isStreaming ? (
            <button
              type="button"
              onClick={onStop}
              id="chat-stop-btn"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-md shadow-rose-600/20 transition-all cursor-pointer"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
              <span>Stop</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSendClick}
              id="chat-send-btn"
              disabled={(!query.trim() && !attachedImage) || disabled}
              className="p-2 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white disabled:opacity-40 disabled:pointer-events-none transition-all cursor-pointer shadow-md shadow-sky-500/20"
            >
              <ArrowUp className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
