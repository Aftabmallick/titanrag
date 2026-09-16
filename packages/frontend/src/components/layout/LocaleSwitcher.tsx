"use client";

import React, { useState, useRef, useEffect } from "react";
import { useI18n, SUPPORTED_LOCALES, Locale } from "@/lib/i18n";
import { Globe, Check } from "lucide-react";

export function LocaleSwitcher() {
  const { locale, setLocale } = useI18n();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const active = SUPPORTED_LOCALES.find((l) => l.code === locale) || SUPPORTED_LOCALES[0];

  return (
    <div className="relative inline-block" ref={ref}>
      <button
        onClick={() => setOpen((prev) => !prev)}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-xs font-medium text-slate-300 hover:text-white bg-slate-900/80 hover:bg-slate-800 border border-slate-700/60 transition-colors shadow-sm"
        title="Switch Language"
        aria-label="Switch Language"
      >
        <Globe className="w-3.5 h-3.5 text-sky-400" />
        <span className="text-xs">{active.flag}</span>
        <span className="hidden sm:inline-block font-mono text-[11px] uppercase">
          {active.code}
        </span>
      </button>

      {open && (
        <div className="absolute right-0 mt-1.5 w-36 rounded-xl border border-slate-800 bg-slate-900 shadow-2xl p-1 z-50 animate-in fade-in zoom-in-95 duration-100">
          <div className="px-2 py-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
            Language / Idioma
          </div>
          {SUPPORTED_LOCALES.map((l) => (
            <button
              key={l.code}
              onClick={() => {
                setLocale(l.code);
                setOpen(false);
              }}
              className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                locale === l.code
                  ? "bg-sky-500/10 text-sky-400 border border-sky-500/20"
                  : "text-slate-300 hover:text-white hover:bg-slate-800/80"
              }`}
            >
              <div className="flex items-center gap-2">
                <span>{l.flag}</span>
                <span>{l.name}</span>
              </div>
              {locale === l.code && <Check className="w-3.5 h-3.5 text-sky-400" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
