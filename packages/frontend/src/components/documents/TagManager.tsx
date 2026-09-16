"use client";

import React, { useState } from "react";
import { Tag, Plus, X } from "lucide-react";

export interface TagManagerProps {
  tags: string[];
  onChange: (tags: string[]) => void;
  availableTags?: string[];
  readOnly?: boolean;
}

export function TagManager({
  tags,
  onChange,
  availableTags = ["confidential", "2024", "nda", "audit", "technical", "public", "finance"],
  readOnly = false,
}: TagManagerProps) {
  const [inputVal, setInputVal] = useState("");

  const handleAddTag = (newTag: string) => {
    const clean = newTag.trim().toLowerCase();
    if (!clean || tags.includes(clean)) return;
    onChange([...tags, clean]);
    setInputVal("");
  };

  const handleRemoveTag = (tagToRemove: string) => {
    onChange(tags.filter((t) => t !== tagToRemove));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      handleAddTag(inputVal);
    }
  };

  const unselectedSuggestions = availableTags.filter(
    (at) => !tags.includes(at) && at.includes(inputVal.toLowerCase())
  );

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-1.5 min-h-[32px]">
        {tags.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg bg-sky-500/10 border border-sky-500/20 text-sky-400 text-xs font-mono font-medium"
          >
            <span>#{tag}</span>
            {!readOnly && (
              <button
                type="button"
                onClick={() => handleRemoveTag(tag)}
                className="hover:text-rose-400 p-0.5"
                title={`Remove #${tag}`}
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </span>
        ))}

        {!readOnly && (
          <div className="inline-flex items-center gap-1">
            <input
              type="text"
              placeholder="Add tag..."
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              onKeyDown={handleKeyDown}
              className="px-2 py-0.5 text-xs rounded-lg bg-slate-900 border border-slate-800 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500 w-24 font-mono"
            />
            {inputVal && (
              <button
                type="button"
                onClick={() => handleAddTag(inputVal)}
                className="p-1 rounded-lg bg-sky-500/20 text-sky-400 hover:bg-sky-500/30"
              >
                <Plus className="w-3 h-3" />
              </button>
            )}
          </div>
        )}
      </div>

      {!readOnly && inputVal && unselectedSuggestions.length > 0 && (
        <div className="flex flex-wrap gap-1 text-[11px] text-slate-400 items-center">
          <span>Suggestions:</span>
          {unselectedSuggestions.slice(0, 5).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => handleAddTag(s)}
              className="px-1.5 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono"
            >
              +{s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
