"use client";

import { useEffect, useState } from "react";
import type { BillingRow, BillingSummary } from "@/lib/api";

const fmtUsd = (v: string | number) => {
  const n = typeof v === "number" ? v : Number(v);
  return `$${n.toLocaleString("de-DE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4
  })}`;
};

const fmtTokens = (n: number) => n.toLocaleString("de-DE");

/**
 * System-Abrechnungs-Panel (nur GOA): je Modell Läufe, Tokens (in/out),
 * Einkauf, Verkauf, Gewinn + fette Gesamtzeile (GET /system/billing/summary).
 * Backend ist das eigentliche Gate (nur GOA) — bei 403 zeigen wir den Hinweis.
 */
export function SystemBillingPanel() {
  const [summary, setSummary] = useState<BillingSummary | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const r = await fetch("/api/proxy/system/billing/summary", { cache: "no-store" });
        if (r.status === 403) {
          if (active) setForbidden(true);
          return;
        }
        if (active) setForbidden(false);
        if (r.ok && active) setSummary((await r.json()) as BillingSummary);
      } catch {
        if (active) setMsg("Netzwerkfehler.");
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  if (forbidden) {
    return (
      <p className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800">
        Nur für GOA.
      </p>
    );
  }

  const row = (r: BillingRow, total: boolean) => (
    <tr
      key={total ? "__total__" : r.model ?? "—"}
      className={total ? "border-t-2 font-semibold" : "border-b"}
    >
      <td className="py-2">{total ? "Gesamt" : r.model ?? "—"}</td>
      <td className="text-right">{fmtTokens(r.runs)}</td>
      <td className="text-right">{fmtTokens(r.tokens_in)}</td>
      <td className="text-right">{fmtTokens(r.tokens_out)}</td>
      <td className="text-right">{fmtUsd(r.einkauf_usd)}</td>
      <td className="text-right">{fmtUsd(r.verkauf_usd)}</td>
      <td className="text-right">{fmtUsd(r.gewinn_usd)}</td>
    </tr>
  );

  return (
    <section className="rounded-lg border p-4">
      <h2 className="mb-3 font-semibold">Abrechnung</h2>

      {msg && <p className="mb-2 text-sm text-muted-foreground">{msg}</p>}

      {!summary ? (
        <p className="text-sm text-muted-foreground">Lädt…</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left">
                <th className="py-2">Modell</th>
                <th className="text-right">Läufe</th>
                <th className="text-right">Tokens in</th>
                <th className="text-right">Tokens out</th>
                <th className="text-right">Einkauf</th>
                <th className="text-right">Verkauf</th>
                <th className="text-right">Gewinn</th>
              </tr>
            </thead>
            <tbody>
              {summary.models.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-3 text-sm text-muted-foreground">
                    Noch keine Abrechnungsdaten.
                  </td>
                </tr>
              ) : (
                summary.models.map((m) => row(m, false))
              )}
              {row(summary.total, true)}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
