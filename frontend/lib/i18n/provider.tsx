"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { translate, type Lang, type MsgKey } from "./dict";

type I18n = {
  lang: Lang;
  t: (key: MsgKey, vars?: Record<string, string | number>) => string;
  setLang: (l: Lang) => void;
};

const Ctx = createContext<I18n>({ lang: "de", t: (k) => k, setLang: () => {} });

export function LanguageProvider({
  initialLang = "de",
  children
}: {
  initialLang?: Lang;
  children: ReactNode;
}) {
  const [lang, setLangState] = useState<Lang>(initialLang);

  // Beim Mount mit localStorage abgleichen (instantes Umschalten ohne Reload).
  useEffect(() => {
    const saved = window.localStorage.getItem("aw_lang");
    if (saved === "de" || saved === "en") setLangState(saved);
  }, []);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    window.localStorage.setItem("aw_lang", l);
    document.cookie = `aw_lang=${l}; path=/; max-age=31536000`;
    // Persistieren am Nutzerprofil (best effort).
    void fetch("/api/proxy/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ language: l })
    });
  }, []);

  const t = useCallback(
    (key: MsgKey, vars?: Record<string, string | number>) => translate(lang, key, vars),
    [lang]
  );

  return <Ctx.Provider value={{ lang, t, setLang }}>{children}</Ctx.Provider>;
}

export function useI18n(): I18n {
  return useContext(Ctx);
}
