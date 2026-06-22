"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Job {
  id: string;
  work_id: string;
  cron_expr: string;
  enabled: boolean;
}

export function CronManager({ initialJobs, works }: { initialJobs: Job[]; works: { id: string; title: string }[] }) {
  const [jobs, setJobs] = useState<Job[]>(initialJobs);
  const [workId, setWorkId] = useState(works[0]?.id ?? "");
  const [cronExpr, setCronExpr] = useState("0 8 * * *");
  const [maxCost, setMaxCost] = useState(1.0);
  const [error, setError] = useState<string | null>(null);

  async function create() {
    setError(null);
    const res = await fetch("/api/proxy/cron-jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ work_id: workId, cron_expr: cronExpr, max_cost_usd: maxCost })
    });
    if (!res.ok) {
      setError(await res.text());
      return;
    }
    const created: Job = await res.json();
    setJobs((j) => [...j, created]);
  }

  async function remove(id: string) {
    const res = await fetch(`/api/proxy/cron-jobs/${id}`, { method: "DELETE" });
    if (res.ok) setJobs((j) => j.filter((x) => x.id !== id));
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-3 md:grid-cols-[2fr,2fr,1fr,auto] md:items-end">
        <div>
          <label className="text-sm font-medium">Work</label>
          <select value={workId} onChange={(e) => setWorkId(e.target.value)} className="mt-1 block h-10 w-full rounded-md border bg-background px-3 text-sm">
            {works.map((w) => (
              <option key={w.id} value={w.id}>
                {w.title}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-sm font-medium">Cron-Expression</label>
          <Input value={cronExpr} onChange={(e) => setCronExpr(e.target.value)} placeholder="0 8 * * *" />
        </div>
        <div>
          <label className="text-sm font-medium">Max Kosten/Lauf (USD)</label>
          <Input
            type="number"
            step="0.01"
            value={maxCost}
            onChange={(e) => setMaxCost(Number(e.target.value))}
          />
        </div>
        <Button onClick={create} disabled={!workId}>
          + Anlegen
        </Button>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}

      <ul className="space-y-2">
        {jobs.map((j) => (
          <li key={j.id} className="flex items-center justify-between rounded border p-2 text-sm">
            <div>
              <code>{j.cron_expr}</code>
              <span className="ml-2 text-xs text-muted-foreground">
                → {works.find((w) => w.id === j.work_id)?.title ?? j.work_id}
              </span>
            </div>
            <Button size="sm" variant="destructive" onClick={() => remove(j.id)}>
              löschen
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}
