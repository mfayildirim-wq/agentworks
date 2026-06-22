"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import type { InstanceUsage } from "@/lib/api";

export function UsageByInstance() {
  const [rows, setRows] = useState<InstanceUsage[] | null>(null);
  useEffect(() => {
    void (async () => {
      const r = await fetch("/api/proxy/wallet/by-instance", { cache: "no-store" });
      if (r.ok) setRows(await r.json());
    })();
  }, []);
  return (
    <section className="mt-6 rounded-lg border p-4">
      <h2 className="text-lg font-semibold">Verbrauch pro App</h2>
      {rows && rows.length === 0 && (
        <p className="mt-2 text-sm text-muted-foreground">Noch kein Verbrauch.</p>
      )}
      <ul className="mt-2 space-y-1 text-sm">
        {(rows ?? []).map((r) => (
          <li key={r.artifact_id} className="flex items-center justify-between border-b py-1">
            <Link href={`/artifacts/${r.artifact_id}`} className="truncate hover:underline">
              {r.title}
            </Link>
            <span className="ml-3 shrink-0 tabular-nums">
              ${Number(r.total_usd).toFixed(4)} · {r.runs} Läufe
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
