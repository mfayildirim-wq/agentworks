"use client";

import { useEffect, useState } from "react";

type Provider = "anthropic" | "openai" | "deepseek";
type Status = Record<Provider, boolean>;

const PROVIDERS: { key: Provider; label: string; placeholder: string }[] = [
  { key: "anthropic", label: "Anthropic (Claude)", placeholder: "sk-ant-…" },
  { key: "openai", label: "OpenAI", placeholder: "sk-…" },
  { key: "deepseek", label: "DeepSeek", placeholder: "sk-…" }
];

/**
 * System-Keys-Panel (nur GOA): zeigt je Provider „gesetzt"/„nicht gesetzt"
 * und erlaubt das Setzen plattformweiter Schlüssel. Backend ist das eigentliche
 * Gate (nur GOA) — bei 403 zeigen wir den Hinweis. Klartext wird nie geladen.
 */
export function SystemKeysPanel() {
  const [status, setStatus] = useState<Status | null>(null);
  const [values, setValues] = useState<Record<Provider, string>>({
    anthropic: "",
    openai: "",
    deepseek: ""
  });
  const [forbidden, setForbidden] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function load() {
    const r = await fetch("/api/proxy/system/keys", { cache: "no-store" });
    if (r.status === 403) {
      setForbidden(true);
      return;
    }
    setForbidden(false);
    if (r.ok) setStatus((await r.json()) as Status);
  }

  useEffect(() => {
    void load();
  }, []);

  async function save() {
    setBusy(true);
    setMsg(null);
    const body: Partial<Record<Provider, string>> = {};
    (Object.keys(values) as Provider[]).forEach((p) => {
      if (values[p] !== "") body[p] = values[p];
    });
    try {
      const r = await fetch("/api/proxy/system/keys", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      if (r.status === 403) {
        setForbidden(true);
        return;
      }
      if (!r.ok) {
        setMsg((await r.text()) || "Speichern fehlgeschlagen.");
        return;
      }
      setValues({ anthropic: "", openai: "", deepseek: "" });
      await load();
      setMsg("Gespeichert.");
    } catch {
      setMsg("Netzwerkfehler.");
    } finally {
      setBusy(false);
    }
  }

  if (forbidden) {
    return (
      <p className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800">
        Nur für Systemadmin.
      </p>
    );
  }

  return (
    <section className="rounded-lg border p-4">
      <h2 className="mb-1 font-semibold">System-Keys</h2>
      <p className="mb-3 text-xs text-muted-foreground">
        Diese Schlüssel gelten plattformweit (System). Leer lassen = unverändert.
      </p>

      {PROVIDERS.map((p) => (
        <label key={p.key} className="mt-3 block text-sm first:mt-0">
          {p.label}{" "}
          {status?.[p.key] ? (
            <span className="text-xs text-green-700">● gesetzt ✓</span>
          ) : (
            <span className="text-xs text-muted-foreground">● nicht gesetzt</span>
          )}
          <input
            type="password"
            autoComplete="off"
            className="mt-1 w-full rounded border px-3 py-2 font-mono text-sm"
            placeholder={status?.[p.key] ? "•••••• (gesetzt)" : p.placeholder}
            value={values[p.key]}
            onChange={(e) =>
              setValues((v) => ({ ...v, [p.key]: e.target.value }))
            }
            disabled={busy}
          />
        </label>
      ))}

      {msg && <p className="mt-3 text-sm text-muted-foreground">{msg}</p>}

      <button
        type="button"
        onClick={() => void save()}
        disabled={busy}
        className="mt-4 rounded bg-black px-4 py-2 text-sm text-white disabled:opacity-50"
      >
        {busy ? "Speichert…" : "Speichern"}
      </button>
    </section>
  );
}
