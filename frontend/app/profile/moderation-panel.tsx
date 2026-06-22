"use client";

import { useEffect, useState } from "react";
import type { PublicationRequest } from "@/lib/api";

/**
 * Moderations-Panel (Admin/GOA): offene Veröffentlichungs-Anfragen genehmigen
 * oder mit Grund ablehnen. Backend ist der eigentliche Gate — bei 403 zeigen
 * wir nur den Hinweis. Wird sowohl unter /admin/publications als auch im
 * Profil-Tab "Moderation" verwendet.
 */
export function ModerationPanel() {
  const [rows, setRows] = useState<PublicationRequest[]>([]);
  const [forbidden, setForbidden] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notes, setNotes] = useState<Record<string, string>>({});

  async function load() {
    try {
      const r = await fetch("/api/proxy/admin/publication-requests", { cache: "no-store" });
      if (r.status === 403) {
        setForbidden(true);
        setRows([]);
        return;
      }
      setForbidden(false);
      if (r.ok) setRows(await r.json());
    } finally {
      setLoaded(true);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function approve(id: string) {
    setBusy(true);
    try {
      const r = await fetch(`/api/proxy/admin/templates/${id}/approve`, { method: "POST" });
      if (r.status === 403) {
        setForbidden(true);
        return;
      }
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function reject(id: string) {
    setBusy(true);
    try {
      const r = await fetch(`/api/proxy/admin/templates/${id}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: notes[id] ?? "" })
      });
      if (r.status === 403) {
        setForbidden(true);
        return;
      }
      await load();
    } finally {
      setBusy(false);
    }
  }

  if (forbidden) {
    return (
      <p className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800">
        Nur für Admins/Systemadmin.
      </p>
    );
  }

  return (
    <section className="rounded-lg border p-4">
      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {loaded ? "Keine offenen Anfragen." : "Lädt…"}
        </p>
      ) : (
        <ul className="space-y-3 text-sm">
          {rows.map((req) => (
            <li key={req.id} className="border-b pb-3">
              <div className="flex items-center justify-between gap-2">
                <span>
                  <span className="font-medium">{req.title}</span>{" "}
                  <span className="text-xs text-gray-400">
                    · {req.category} · {req.owner_name} ·{" "}
                    {new Date(req.created_at).toLocaleDateString("de-DE")}
                  </span>
                </span>
                <button
                  onClick={() => void approve(req.id)}
                  disabled={busy}
                  className="shrink-0 rounded bg-black px-2 py-0.5 text-xs text-white disabled:opacity-50"
                >
                  Genehmigen
                </button>
              </div>
              <div className="mt-2 flex items-center gap-2">
                <input
                  type="text"
                  value={notes[req.id] ?? ""}
                  placeholder="Grund (optional)…"
                  onChange={(e) =>
                    setNotes((n) => ({ ...n, [req.id]: e.target.value }))
                  }
                  className="flex-1 rounded border px-2 py-1 text-xs"
                />
                <button
                  onClick={() => void reject(req.id)}
                  disabled={busy}
                  className="shrink-0 rounded border px-2 py-0.5 text-xs hover:bg-muted disabled:opacity-50"
                >
                  Ablehnen
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
