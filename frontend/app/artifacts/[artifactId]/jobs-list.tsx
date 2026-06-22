"use client";

import type { Job } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import type { MsgKey } from "@/lib/i18n/dict";

const STATUS_COLOR: Record<string, string> = {
  active: "bg-green-500",
  scheduled: "bg-blue-500",
  paused: "bg-amber-500",
  completed: "bg-gray-400",
  failed: "bg-red-500"
};

const CADENCE_KEY: Record<string, MsgKey> = {
  hourly: "jobs.hourly",
  daily: "jobs.daily",
  weekly: "jobs.weekly"
};

function fmt(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("de-DE");
}

/**
 * Schreibgeschützte Liste der Aufgaben (Jobs) einer Instanz. Der Benutzer legt sie
 * nicht selbst an — der Agent erstellt sie aus dem Chat (Folge-Spec B-Teil 2).
 */
export function JobsList({ jobs }: { jobs: Job[] }) {
  const { t } = useI18n();
  return (
    <section className="rounded-xl border bg-card p-4">
      <h2 className="mb-1 text-sm font-semibold">{t("jobs.title")}</h2>
      <p className="mb-3 text-xs text-muted-foreground">
        {t("jobs.intro")}
      </p>
      {jobs.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {t("jobs.none")}
        </p>
      ) : (
        <ul className="divide-y">
          {jobs.map((j) => (
            <li key={j.id} className="flex items-center gap-3 py-2">
              <span
                className={`h-2.5 w-2.5 shrink-0 rounded-full ${
                  STATUS_COLOR[j.status] ?? "bg-gray-400"
                }`}
                title={j.status}
              />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{j.title || j.instruction}</div>
                <div className="text-xs text-muted-foreground">
                  {j.trigger_kind === "recurring"
                    ? (CADENCE_KEY[j.cadence ?? ""] ? t(CADENCE_KEY[j.cadence ?? ""]) : j.cadence)
                    : t("jobs.once")}
                  {` · ${t("jobs.nextRun")}: `}
                  {fmt(j.next_run_at)}
                  {` · ${t("jobs.runs")}: `}
                  {j.run_count}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
