"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import enMessages from "../messages/en.json";
import esMessages from "../messages/es.json";
import deMessages from "../messages/de.json";

export type Locale = "en" | "es" | "de";

export const SUPPORTED_LOCALES: { code: Locale; name: string; flag: string }[] = [
  { code: "en", name: "English", flag: "🇺🇸" },
  { code: "es", name: "Español", flag: "🇪🇸" },
  { code: "de", name: "Deutsch", flag: "🇩🇪" },
];

const dictionaries: Record<Locale, any> = {
  en: enMessages,
  es: esMessages,
  de: deMessages,
};

interface I18nContextType {
  locale: Locale;
  setLocale: (loc: Locale) => void;
  t: (keyPath: string, fallback?: string) => string;
}

const I18nContext = createContext<I18nContextType | undefined>(undefined);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");

  useEffect(() => {
    const saved = localStorage.getItem("titan_locale") as Locale;
    if (saved && (saved === "en" || saved === "es" || saved === "de")) {
      setLocaleState(saved);
    }
  }, []);

  const setLocale = useCallback((newLocale: Locale) => {
    setLocaleState(newLocale);
    localStorage.setItem("titan_locale", newLocale);
    document.documentElement.lang = newLocale;
  }, []);

  const t = useCallback(
    (keyPath: string, fallback?: string): string => {
      const dict = dictionaries[locale] || dictionaries.en;
      const keys = keyPath.split(".");
      let cur = dict;

      for (const k of keys) {
        if (cur && typeof cur === "object" && k in cur) {
          cur = cur[k];
        } else {
          // fallback to en
          let enCur = dictionaries.en;
          for (const ek of keys) {
            if (enCur && typeof enCur === "object" && ek in enCur) {
              enCur = enCur[ek];
            } else {
              return fallback || keyPath;
            }
          }
          return typeof enCur === "string" ? enCur : fallback || keyPath;
        }
      }

      return typeof cur === "string" ? cur : fallback || keyPath;
    },
    [locale]
  );

  return (
    <I18nContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error("useI18n must be used within an I18nProvider");
  }
  return ctx;
}
