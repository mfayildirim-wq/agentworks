"use client";

import { useState } from "react";
import type { SystemUserRow, UserConsumption } from "@/lib/api";

const fmtUsd = (v: string | number) => {
  const n = typeof v === "number" ? v : Number(v);
  return `$${n.toLocaleString("de-DE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4
  })}`;
};

const fmtTokens = (n: number) => n.toLocaleString("de-DE");

/**
 * System-Nutzer-Panel (nur GOA): Nutzer suchen (GET /system/users?q=),
 * Klick auf einen Treffer lädt den Verbrauch (GET /system/users/{id}/consumption).
 * Backend ist das eigentliche Gate (nur GOA) — bei 403 zeigen wir den Hinweis.
 */
export function SystemUsersPanel() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SystemUserRow[]>([]);
  const [selected, setSelected] = useState<SystemUserRow | null>(null);
  const [detail, setDetail] = useState<UserConsumption | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [busy, setBusy] = useState(false);
  const [searched, setSearched] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function search() {
    setBusy(true);
    setMsg(null);
    setSelected(null);
    setDetail(null);
    try {
      const r = await fetch(
        `/api/proxy/system/users?q=${encodeURIComponent(query.trim())}`,
        { cache: "no-store" }
      );
      if (r.status === 403) {
        setForbidden(true);
        setResults([]);
        setSearched(true);
        return;
      }
      setForbidden(false);
      setSearched(true);
      if (r.ok) setResults((await r.json()) as SystemUserRow[]);
    } catch {
      setMsg("Netzwerkfehler.");
    } finally {
      setBusy(false);
    }
  }

  async function loadDetail(u: SystemUserRow) {
    setSelected(u);
    setDetail(null);
    setMsg(null);
    try {
      const r = await fetch(
        `/api/proxy/system/users/${encodeURIComponent(u.user_id)}/consumption`,
        { cache: "no-store" }
      );
      if (r.status === 403) {
        setForbidden(true);
        return;
      }
      if (r.ok) setDetail((await r.json()) as UserConsumption);
      else setMsg("Verbrauch konnte nicht geladen werden.");
    } catch {
      setMsg("Netzwerkfehler.");
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
      <h2 className="mb-3 font-semibold">Nutzer-Verbrauch</h2>

      <div className="flex items-center gap-2">
        <input
          type="text"
          value={query}
          placeholder="Name oder E-Mail suchen…"
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void search();
          }}
          className="flex-1 rounded border px-2 py-1"
        />
        <button
          type="button"
          onClick={() => void search()}
          disabled={busy}
          className="rounded bg-black px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          Suchen
        </button>
      </div>

      {msg && <p className="mt-2 text-sm text-muted-foreground">{msg}</p>}

      <div className="mt-4">
        {results.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {searched ? "Keine Treffer." : "Suche nach einem Nutzer."}
          </p>
        ) : (
          <ul className="space-y-1 text-sm">
            {results.map((u) => (
              <li key={u.user_id}>
                <button
                  type="button"
                  onClick={() => void loadDetail(u)}
                  className={`flex w-full items-center justify-between gap-2 rounded border-b px-2 py-2 text-left hover:bg-muted ${
                    selected?.user_id === u.user_id ? "bg-muted" : ""
                  }`}
                >
                  <span>
                    {u.name || "(ohne Name)"}{" "}
                    <span className="text-xs text-gray-400">· {u.email}</span>
                  </span>
                  <span className="text-xs text-muted-foreground">
                    Saldo {fmtUsd(u.saldo_usd)} · Verkauf {fmtUsd(u.verkauf_usd)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {selected && (
        <div className="mt-4 rounded-lg border bg-muted/30 p-3 text-sm">
          <p className="mb-2 font-medium">
            {selected.name || "(ohne Name)"}{" "}
            <span className="text-xs text-gray-400">· {selected.email}</span>
          </p>
          {!detail ? (
            <p className="text-muted-foreground">Lädt…</p>
          ) : (
            <dl className="grid grid-cols-2 gap-x-6 gap-y-1">
              <dt className="text-muted-foreground">Tokens in</dt>
              <dd className="text-right">{fmtTokens(detail.tokens_in)}</dd>
              <dt className="text-muted-foreground">Tokens out</dt>
              <dd className="text-right">{fmtTokens(detail.tokens_out)}</dd>
              <dt className="text-muted-foreground">Läufe</dt>
              <dd className="text-right">{fmtTokens(detail.runs)}</dd>
              <dt className="text-muted-foreground">Einkauf</dt>
              <dd className="text-right">{fmtUsd(detail.einkauf_usd)}</dd>
              <dt className="text-muted-foreground">Verkauf</dt>
              <dd className="text-right">{fmtUsd(detail.verkauf_usd)}</dd>
              <dt className="text-muted-foreground">Gewinn</dt>
              <dd className="text-right">{fmtUsd(detail.gewinn_usd)}</dd>
              <dt className="text-muted-foreground">Aufladungen</dt>
              <dd className="text-right">{fmtUsd(detail.topups_usd)}</dd>
              <dt className="text-muted-foreground">Saldo</dt>
              <dd className="text-right">{fmtUsd(detail.saldo_usd)}</dd>
            </dl>
          )}
        </div>
      )}
    </section>
  );
}
