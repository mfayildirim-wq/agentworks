"use client";

import { useState } from "react";

type AdminUser = {
  id: string; name: string; email: string; role: string; topup_mode: string;
  is_system_admin?: boolean; balance_usd?: number;
};

/**
 * Systemadmin-Panel: Nutzer suchen, zum Admin machen/entziehen und Guthaben gutschreiben
 * (Attrappe, ohne Bezahlung). Backend ist der eigentliche Gate (nur Systemadmin).
 * Wird unter /admin/users und im Profil-Tab "Admin" verwendet.
 */
export function AdminUsersPanel() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<AdminUser[]>([]);
  const [forbidden, setForbidden] = useState(false);
  const [busy, setBusy] = useState(false);
  const [searched, setSearched] = useState(false);
  const [grant, setGrant] = useState<Record<string, string>>({});

  async function grantCredit(id: string) {
    const amount = Number(grant[id]);
    if (!amount || amount <= 0) return;
    setBusy(true);
    try {
      const r = await fetch(`/api/proxy/admin/users/${id}/grant-credit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount_usd: amount })
      });
      if (r.status === 403) {
        setForbidden(true);
        return;
      }
      setGrant((g) => ({ ...g, [id]: "" }));
      await search();
    } finally {
      setBusy(false);
    }
  }

  async function search() {
    const q = query.trim();
    if (!q) {
      setResults([]);
      setSearched(false);
      return;
    }
    setBusy(true);
    try {
      const r = await fetch(`/api/proxy/admin/users?q=${encodeURIComponent(q)}`, {
        cache: "no-store"
      });
      if (r.status === 403) {
        setForbidden(true);
        setResults([]);
        setSearched(true);
        return;
      }
      setForbidden(false);
      setSearched(true);
      if (r.ok) setResults(await r.json());
    } finally {
      setBusy(false);
    }
  }

  async function setRole(id: string, role: "" | "admin") {
    setBusy(true);
    try {
      const r = await fetch(`/api/proxy/admin/users/${id}/role`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role })
      });
      if (r.status === 403) {
        setForbidden(true);
        return;
      }
      await search();
    } finally {
      setBusy(false);
    }
  }


  if (forbidden) {
    return (
      <p className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800">
        Nur für Systemadmin.
      </p>
    );
  }

  return (
    <section className="rounded-lg border p-4">
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
          onClick={() => void search()}
          disabled={busy}
          className="rounded bg-black px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          Suchen
        </button>
      </div>

      <div className="mt-4">
        {results.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {searched ? "Keine Treffer." : "Suche nach einem Nutzer."}
          </p>
        ) : (
          <ul className="space-y-1 text-sm">
            {results.map((u) => (
              <li
                key={u.id}
                className="flex items-center justify-between border-b py-2"
              >
                <span>
                  {u.name} <span className="text-xs text-gray-400">· {u.email}</span>
                  {u.is_system_admin && (
                    <span className="ml-2 rounded bg-indigo-600 px-1.5 py-0.5 text-xs text-white">
                      Systemadmin
                    </span>
                  )}
                  {u.role === "admin" && !u.is_system_admin && (
                    <span className="ml-2 rounded bg-black px-1.5 py-0.5 text-xs text-white">
                      Admin
                    </span>
                  )}
                  <span className="ml-2 text-xs text-gray-500">
                    Guthaben: ${Number(u.balance_usd ?? 0).toFixed(2)}
                  </span>
                </span>
                <div className="flex items-center gap-1.5">
                  {!u.is_system_admin &&
                    (u.role === "admin" ? (
                      <button
                        onClick={() => void setRole(u.id, "")}
                        disabled={busy}
                        className="rounded border px-2 py-0.5 text-xs hover:bg-muted disabled:opacity-50"
                      >
                        Admin entziehen
                      </button>
                    ) : (
                      <button
                        onClick={() => void setRole(u.id, "admin")}
                        disabled={busy}
                        className="rounded bg-black px-2 py-0.5 text-xs text-white disabled:opacity-50"
                      >
                        Zum Admin machen
                      </button>
                    ))}
                  {/* Guthaben gutschreiben (Attrappe, ohne Bezahlung) */}
                  <input
                    type="number"
                    step="0.5"
                    min="0"
                    placeholder="$"
                    value={grant[u.id] ?? ""}
                    onChange={(e) => setGrant((g) => ({ ...g, [u.id]: e.target.value }))}
                    className="w-16 rounded border px-1 py-0.5 text-xs"
                  />
                  <button
                    onClick={() => void grantCredit(u.id)}
                    disabled={busy}
                    className="rounded border px-2 py-0.5 text-xs hover:bg-muted disabled:opacity-50"
                  >
                    Gutschreiben
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
