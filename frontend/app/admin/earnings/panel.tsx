"use client";

import { useEffect, useState } from "react";

type Row = {
  template_id: string;
  template_title: string;
  creator_name: string;
  total_usd: number;
  runs: number;
};

export function CreatorEarningsPanel() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const r = await fetch("/api/proxy/admin/creator-earnings", { cache: "no-store" });
        if (r.status === 403) {
          setError("Nur für Admins.");
          return;
        }
        setRows(r.ok ? await r.json() : []);
      } catch {
        setError("Konnte Einnahmen nicht laden.");
      }
    })();
  }, []);

  if (error) return <p className="text-sm text-muted-foreground">{error}</p>;
  if (rows === null) return <p className="text-sm text-muted-foreground">Lädt…</p>;
  if (rows.length === 0)
    return <p className="text-sm text-muted-foreground">Noch keine Creator-Einnahmen.</p>;

  const total = rows.reduce((s, r) => s + r.total_usd, 0);

  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr className="border-b text-left text-xs uppercase text-muted-foreground">
          <th className="py-2">Vorlage</th>
          <th className="py-2">Ersteller</th>
          <th className="py-2 text-right">Läufe</th>
          <th className="py-2 text-right">Verdient</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.template_id} className="border-b">
            <td className="py-2 font-medium">{r.template_title}</td>
            <td className="py-2 text-muted-foreground">{r.creator_name}</td>
            <td className="py-2 text-right">{r.runs}</td>
            <td className="py-2 text-right font-medium">${r.total_usd.toFixed(4)}</td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr className="font-semibold">
          <td className="py-2" colSpan={3}>
            Gesamt
          </td>
          <td className="py-2 text-right">${total.toFixed(4)}</td>
        </tr>
      </tfoot>
    </table>
  );
}
