import { cookies } from "next/headers";
import { translate, type Lang, type MsgKey } from "./dict";

/** UI-Sprache für Server-Komponenten (aus dem aw_lang-Cookie). */
export function getLang(): Lang {
  return cookies().get("aw_lang")?.value === "en" ? "en" : "de";
}

/** Server-seitige Übersetzung (Server-Komponenten ohne React-Context). */
export function getT(): (key: MsgKey, vars?: Record<string, string | number>) => string {
  const lang = getLang();
  return (key, vars) => translate(lang, key, vars);
}
