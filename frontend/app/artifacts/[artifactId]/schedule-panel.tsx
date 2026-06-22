"use client";

import { useEffect, useState } from "react";
import type {
  ScheduleView,
  ScheduleCadence,
  ScheduleCompletion
} from "@/lib/api";

const CADENCE_LABEL: Record<ScheduleCadence, string> = {
  hourly: "Stündlich",
  daily: "Täglich (06:00 UTC)",
  weekly: "Wöchentlich (Mo 06:00 UTC)"
};

const STATUS_LABEL: Record<ScheduleView["status"], string> = {
  active: "Aktiv",
  paused: "Pausiert",
  completed: "Abgeschlossen"
};

function fmt(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function SchedulePanel({ artifactId }: { artifactId: string }) {
  const [schedule, setSchedule] = useState<ScheduleView | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Formularfelder
  const [cadence, setCadence] = useState<ScheduleCadence>("daily");
  const [instruction, setInstruction] = useState("");
  const [completion, setCompletion] = useState<ScheduleCompletion>("recurring");
  const [endAt, setEndAt] = useState("");

  function loadInto(s: ScheduleView | null) {
    setSchedule(s);
    if (s) {
      setCadence(s.cadence);
      setInstruction(s.refresh_instruction);
      setCompletion(s.completion_mode);
      setEndAt(s.end_at ? s.end_at.slice(0, 16) : "");
    }
  }

  async function load() {
    const res = await fetch(`/api/proxy/artifacts/${artifactId}/schedule`, {
      cache: "no-store"
    });
    if (res.ok) {
      const txt = await res.text();
      loadInto(txt ? (JSON.parse(txt) as ScheduleView) : null);
    }
    setLoading(false);
  }

  useEffect(() => {
    void load();
    // nur beim Mount laden
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!instruction.trim()) {
      setError("Bitte beschreibe, was bei jeder Aktualisierung passieren soll.");
      return;
    }
    if (completion === "until" && !endAt) {
      setError("Bitte ein Enddatum angeben.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/proxy/artifacts/${artifactId}/schedule`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cadence,
          refresh_instruction: instruction,
          completion_mode: completion,
          end_at: completion === "until" && endAt ? new Date(endAt).toISOString() : null
        })
      });
      if (!res.ok) {
        setError((await res.text()) || "Speichern fehlgeschlagen.");
        return;
      }
      loadInto((await res.json()) as ScheduleView);
    } catch {
      setError("Netzwerkfehler — bitte erneut versuchen.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/proxy/artifacts/${artifactId}/schedule`, {
        method: "DELETE"
      });
      if (!res.ok && res.status !== 204) {
        setError("Löschen fehlgeschlagen.");
        return;
      }
      setSchedule(null);
      setInstruction("");
      setCompletion("recurring");
      setEndAt("");
    } catch {
      setError("Netzwerkfehler — bitte erneut versuchen.");
    } finally {
      setBusy(false);
    }
  }

  async function resume() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/proxy/artifacts/${artifactId}/schedule/resume`, {
        method: "POST"
      });
      if (!res.ok) {
        setError("Fortsetzen fehlgeschlagen.");
        return;
      }
      loadInto((await res.json()) as ScheduleView);
    } catch {
      setError("Netzwerkfehler — bitte erneut versuchen.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border p-4">
      <h2 className="text-sm font-semibold">Automatisch aktualisieren</h2>
      <p className="mb-3 text-xs text-gray-400">
        Lass das Artefakt sich selbst zeitgesteuert auffrischen — z.B. täglich mit neuen Daten.
      </p>

      {loading ? (
        <p className="text-xs text-gray-400">Lädt…</p>
      ) : (
        <>
          {schedule && (
            <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500">
              <span>
                Status:{" "}
                <span
                  className={
                    schedule.status === "active"
                      ? "font-medium text-green-700"
                      : schedule.status === "paused"
                        ? "font-medium text-amber-700"
                        : "font-medium text-gray-500"
                  }
                >
                  {STATUS_LABEL[schedule.status]}
                </span>
              </span>
              <span>Nächster Lauf: {fmt(schedule.next_run_at)}</span>
              <span>Letzter Lauf: {fmt(schedule.last_run_at)}</span>
              <span>Läufe: {schedule.run_count}</span>
              {schedule.fail_count > 0 && (
                <span className="text-red-600">Fehler in Folge: {schedule.fail_count}</span>
              )}
            </div>
          )}

          {schedule?.status === "paused" && (
            <p className="mb-3 rounded bg-amber-50 p-2 text-xs text-amber-800">
              Nach mehreren Fehlern pausiert. Prüfe die Anweisung und setze fort.
            </p>
          )}

          <form onSubmit={save} className="space-y-3">
            <div className="flex flex-wrap gap-3">
              <label className="flex flex-col text-xs text-gray-500">
                Rhythmus
                <select
                  className="mt-1 rounded border px-2 py-1.5 text-sm text-gray-900"
                  value={cadence}
                  onChange={(e) => setCadence(e.target.value as ScheduleCadence)}
                  disabled={busy}
                >
                  {(Object.keys(CADENCE_LABEL) as ScheduleCadence[]).map((c) => (
                    <option key={c} value={c}>
                      {CADENCE_LABEL[c]}
                    </option>
                  ))}
                </select>
              </label>

              <label className="flex flex-col text-xs text-gray-500">
                Abschluss
                <select
                  className="mt-1 rounded border px-2 py-1.5 text-sm text-gray-900"
                  value={completion}
                  onChange={(e) => setCompletion(e.target.value as ScheduleCompletion)}
                  disabled={busy}
                >
                  <option value="recurring">Dauerhaft</option>
                  <option value="once">Nur einmal</option>
                  <option value="until">Bis Datum</option>
                </select>
              </label>

              {completion === "until" && (
                <label className="flex flex-col text-xs text-gray-500">
                  Enddatum
                  <input
                    type="datetime-local"
                    className="mt-1 rounded border px-2 py-1.5 text-sm text-gray-900"
                    value={endAt}
                    onChange={(e) => setEndAt(e.target.value)}
                    disabled={busy}
                  />
                </label>
              )}
            </div>

            <label className="block text-xs text-gray-500">
              Was soll bei jeder Aktualisierung passieren?
              <textarea
                className="mt-1 w-full rounded border px-3 py-2 text-sm text-gray-900"
                rows={2}
                placeholder="z.B. Aktualisiere die Wetterdaten und Veranstaltungen für die nächsten 3 Tage."
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                disabled={busy}
              />
            </label>

            {error && <p className="text-sm text-red-600">{error}</p>}

            <div className="flex flex-wrap gap-2">
              <button
                type="submit"
                disabled={busy}
                className="rounded bg-black px-4 py-2 text-sm text-white disabled:opacity-50"
              >
                {busy ? "Speichert…" : schedule ? "Zeitplan aktualisieren" : "Zeitplan einrichten"}
              </button>
              {schedule?.status === "paused" && (
                <button
                  type="button"
                  onClick={resume}
                  disabled={busy}
                  className="rounded border px-4 py-2 text-sm disabled:opacity-50"
                >
                  Fortsetzen
                </button>
              )}
              {schedule && (
                <button
                  type="button"
                  onClick={remove}
                  disabled={busy}
                  className="rounded border border-red-300 px-4 py-2 text-sm text-red-600 disabled:opacity-50"
                >
                  Zeitplan löschen
                </button>
              )}
            </div>
          </form>
        </>
      )}
    </div>
  );
}
