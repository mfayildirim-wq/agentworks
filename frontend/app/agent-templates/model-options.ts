import { api } from "@/lib/api";
import type { ModelOption } from "./create/form";

/**
 * Abrechenbare Modelle (Claude/OpenAI) aus der Plattform-Preis-Tabelle.
 * Instanz-Läufe laufen über die Plattform-Keys; keine eigenen Keys mehr nötig.
 * Server-seitig nutzbar (kein React/Client-Code).
 */
export async function loadModelOptions(): Promise<{
  options: ModelOption[];
  hasOwnKeys: boolean;
}> {
  let options: ModelOption[] = [];
  try {
    options = await api.models.list();
  } catch {}
  return { options, hasOwnKeys: false };
}
