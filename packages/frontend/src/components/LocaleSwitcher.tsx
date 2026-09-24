"use client";

import React, { useState, useEffect } from "react";
import { Globe, Check } from "lucide-react";

interface LocaleOption {
  code: string;
  label: string;
  nativeName: string;
  dir: "ltr" | "rtl";
}

const LOCALES: LocaleOption[] = [
  { code: "en", label: "English", nativeName: "English", dir: "ltr" },
  { code: "ar", label: "Arabic", nativeName: "العربية", dir: "rtl" },
  { code: "ja", label: "Japanese", nativeName: "日本語", dir: "ltr" },
];

export function LocaleSwitcher() {
  const [currentLocale, setCurrentLocale] = useState("en");
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("titan_locale") || "en";
    setCurrentLocale(saved);
    applyLocale(saved);
  }, []);

  const applyLocale = (code: string) => {
    const opt = LOCALES.find((l) => l.code === code);
    if (opt) {
      document.documentElement.lang = opt.code;
      document.documentElement.dir = opt.dir;
      localStorage.setItem("titan_locale", opt.code);
    }
  };

  const handleSelect = (code: string) => {
    setCurrentLocale(code);
    applyLocale(code);
    setIsOpen(false);
  };

  const selectedOpt = LOCALES.find((l) => l.code === currentLocale) || LOCALES[0];

  return (
    <div className="relative inline-block text-left">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/80 hover:bg-slate-800 border border-slate-700/80 text-xs font-medium text-slate-200 transition-colors"
        aria-haspopup="true"
        aria-expanded={isOpen}
        aria-label="Change Language"
      >
        <Globe className="w-3.5 h-3.5 text-indigo-400" />
        <span>{selectedOpt.nativeName}</span>
      </button>

      {isOpen && (
        <div
          className="absolute right-0 mt-2 w-40 bg-slate-900 border border-slate-700/80 rounded-xl shadow-2xl py-1 z-30 animate-in fade-in zoom-in-95"
          role="menu"
        >
          {LOCALES.map((loc) => (
            <button
              key={loc.code}
              onClick={() => handleSelect(loc.code)}
              className="w-full flex items-center justify-between px-3.5 py-2 text-xs text-slate-200 hover:bg-slate-800 transition-colors"
              role="menuitem"
            >
              <div className="flex flex-col text-left">
                <span className="font-medium">{loc.nativeName}</span>
                <span className="text-[10px] text-slate-500">{loc.label}</span>
              </div>
              {loc.code === currentLocale && (
                <Check className="w-3.5 h-3.5 text-indigo-400" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
