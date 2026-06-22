"use client";

import { useEffect, useState } from "react";
import type { ModelPrice } from "@/lib/api";

export function PricingEditor() {
  const [rows, setRows] = useState<ModelPrice[]>([]);
  const [msg, setMsg] = useState<string>("");

  async function load() {
    const r = await fetch("/api/proxy/pricing");
    if (r.ok) setRows(await r.json());
  }
  useEffect(() => {
    void load();
  }, []);

  async function save(m: string, pin: string, pout: string) {
    const r = await fetch(`/api/proxy/pricing/${m}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        input_per_million_usd: Number(pin),
        output_per_million_usd: Number(pout)
      })
    });
    setMsg(r.ok ? "Gespeichert." : "Fehler (nur Admin).");
    if (r.ok) void load();
  }

  async function refresh() {
    const r = await fetch("/api/proxy/pricing/refresh", { method: "POST" });
    setMsg(r.ok ? "Vorschläge geladen (siehe Konsole)." : "Keine Quelle/Fehler.");
    if (r.ok) console.log(await r.json());
  }

  return (
    <div>
      <button
        onClick={() => void refresh()}
        className="mb-3 rounded border px-3 py-1.5 text-sm"
      >
        Preise abrufen
      </button>
      {msg && <p className="mb-2 text-sm text-gray-600">{msg}</p>}
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left">
            <th className="py-2">Modell</th>
            <th>Input / 1M</th>
            <th>Output / 1M</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.model} className="border-b">
              <td className="py-2">{p.label}</td>
              <td>
                <input
                  id={`in-${p.model}`}
                  defaultValue={p.input_per_million_usd}
                  className="w-24 rounded border px-2 py-1"
                />
              </td>
              <td>
                <input
                  id={`out-${p.model}`}
                  defaultValue={p.output_per_million_usd}
                  className="w-24 rounded border px-2 py-1"
                />
              </td>
              <td>
                <button
                  className="rounded bg-black px-2 py-1 text-xs text-white"
                  onClick={() =>
                    save(
                      p.model,
                      (document.getElementById(`in-${p.model}`) as HTMLInputElement).value,
                      (document.getElementById(`out-${p.model}`) as HTMLInputElement).value
                    )
                  }
                >
                  Speichern
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
