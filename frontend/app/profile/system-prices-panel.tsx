"use client";

import { useEffect, useState } from "react";
import type { ModelPrice } from "@/lib/api";

/**
 * System-Preise-Panel (nur GOA): Modellpreise als Tabelle, je Zeile inline
 * editierbar (PUT /system/prices/{model}). „Aktualisieren" setzt die DB-Preise
 * auf die im Code gepflegten Festwerte zurück (POST /system/prices/refresh).
 * Backend ist das eigentliche Gate (nur GOA) — bei 403 zeigen wir den Hinweis.
 */
export function SystemPricesPanel() {
  const [rows, setRows] = useState<ModelPrice[]>([]);
  const [draft, setDraft] = useState<Record<string, { in: string; out: string }>>({});
  const [forbidden, setForbidden] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  function syncDraft(list: ModelPrice[]) {
    const d: Record<string, { in: string; out: string }> = {};
    list.forEach((p) => {
      d[p.model] = {
        in: String(p.input_per_million_usd),
        out: String(p.output_per_million_usd)
      };
    });
    setDraft(d);
  }

  async function load() {
    try {
      const r = await fetch("/api/proxy/system/prices", { cache: "no-store" });
      if (r.status === 403) {
        setForbidden(true);
        return;
      }
      setForbidden(false);
      if (r.ok) {
        const list = (await r.json()) as ModelPrice[];
        setRows(list);
        syncDraft(list);
      }
    } catch {
      setMsg("Netzwerkfehler.");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function refresh() {
    setBusy(true);
    setMsg(null);
    try {
      const r = await fetch("/api/proxy/system/prices/refresh", { method: "POST" });
      if (r.status === 403) {
        setForbidden(true);
        return;
      }
      if (!r.ok) {
        setMsg("Aktualisieren fehlgeschlagen.");
        return;
      }
      const list = (await r.json()) as ModelPrice[];
      setRows(list);
      syncDraft(list);
      setMsg("Auf Festwerte zurückgesetzt.");
    } catch {
      setMsg("Netzwerkfehler.");
    } finally {
      setBusy(false);
    }
  }

  async function save(model: string) {
    const d = draft[model];
    if (!d) return;
    setBusy(true);
    setMsg(null);
    try {
      const r = await fetch(`/api/proxy/system/prices/${encodeURIComponent(model)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_per_million_usd: Number(d.in),
          output_per_million_usd: Number(d.out)
        })
      });
      if (r.status === 403) {
        setForbidden(true);
        return;
      }
      if (!r.ok) {
        setMsg("Speichern fehlgeschlagen.");
        return;
      }
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
        Nur für GOA.
      </p>
    );
  }

  return (
    <section className="rounded-lg border p-4">
      <div className="mb-1 flex items-center justify-between gap-2">
        <h2 className="font-semibold">Modellpreise</h2>
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={busy}
          className="rounded border px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50"
        >
          🔄 Aktualisieren
        </button>
      </div>
      <p className="mb-3 text-xs text-muted-foreground">
        Gepflegte Festwerte, kein Live-Abruf der Provider-Preise.
      </p>

      {msg && <p className="mb-2 text-sm text-muted-foreground">{msg}</p>}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left">
              <th className="py-2">Provider</th>
              <th>Modell</th>
              <th>Input $/M</th>
              <th>Output $/M</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.model} className="border-b">
                <td className="py-2 text-xs text-muted-foreground">{p.provider}</td>
                <td className="py-2">{p.label}</td>
                <td>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={draft[p.model]?.in ?? ""}
                    onChange={(e) =>
                      setDraft((d) => ({
                        ...d,
                        [p.model]: { in: e.target.value, out: d[p.model]?.out ?? "" }
                      }))
                    }
                    className="w-24 rounded border px-2 py-1"
                    disabled={busy}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={draft[p.model]?.out ?? ""}
                    onChange={(e) =>
                      setDraft((d) => ({
                        ...d,
                        [p.model]: { in: d[p.model]?.in ?? "", out: e.target.value }
                      }))
                    }
                    className="w-24 rounded border px-2 py-1"
                    disabled={busy}
                  />
                </td>
                <td>
                  <button
                    type="button"
                    onClick={() => void save(p.model)}
                    disabled={busy}
                    className="rounded bg-black px-2 py-1 text-xs text-white disabled:opacity-50"
                  >
                    Speichern
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} className="py-3 text-sm text-muted-foreground">
                  Keine Preise hinterlegt.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
