"use client";

import { useEffect, useState } from "react";
import type { Friend, FriendRequest, UserSearch } from "@/lib/api";

export function FriendsPanel() {
  const [friends, setFriends] = useState<Friend[]>([]);
  const [requests, setRequests] = useState<FriendRequest[]>([]);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<UserSearch[]>([]);
  const [busy, setBusy] = useState(false);

  async function loadLists() {
    const [fr, rq] = await Promise.all([
      fetch("/api/proxy/friends", { cache: "no-store" }),
      fetch("/api/proxy/friends/requests", { cache: "no-store" })
    ]);
    if (fr.ok) setFriends(await fr.json());
    if (rq.ok) setRequests(await rq.json());
  }

  useEffect(() => {
    void loadLists();
  }, []);

  async function search() {
    const q = query.trim();
    if (!q) {
      setResults([]);
      return;
    }
    const r = await fetch(`/api/proxy/friends/search?q=${encodeURIComponent(q)}`, {
      cache: "no-store"
    });
    if (r.ok) setResults(await r.json());
  }

  async function addFriend(emailOrName: string) {
    setBusy(true);
    try {
      await fetch("/api/proxy/friends/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email_or_name: emailOrName })
      });
      setQuery("");
      setResults([]);
      await loadLists();
    } finally {
      setBusy(false);
    }
  }

  async function accept(id: string) {
    setBusy(true);
    try {
      await fetch(`/api/proxy/friends/${id}/accept`, { method: "POST" });
      await loadLists();
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    setBusy(true);
    try {
      await fetch(`/api/proxy/friends/${id}`, { method: "DELETE" });
      await loadLists();
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mt-6 rounded-lg border p-4">
      <h2 className="text-lg font-semibold">Freunde</h2>

      {/* Suche */}
      <div className="mt-3 flex items-center gap-2">
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
          className="rounded bg-black px-3 py-1.5 text-sm text-white"
        >
          Suchen
        </button>
      </div>

      {results.length > 0 && (
        <ul className="mt-2 space-y-1 text-sm">
          {results.map((u) => (
            <li key={u.id} className="flex items-center justify-between border-b py-1">
              <span>{u.name}</span>
              <button
                onClick={() => void addFriend(u.name)}
                disabled={busy}
                className="rounded border px-2 py-0.5 text-xs hover:bg-muted disabled:opacity-50"
              >
                Hinzufügen
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* Eingehende Anfragen */}
      {requests.length > 0 && (
        <div className="mt-4">
          <h3 className="mb-1 text-sm font-medium text-gray-600">Anfragen</h3>
          <ul className="space-y-1 text-sm">
            {requests.map((r) => (
              <li key={r.id} className="flex items-center justify-between border-b py-1">
                <span>{r.name}</span>
                <span className="flex gap-2">
                  <button
                    onClick={() => void accept(r.id)}
                    disabled={busy}
                    className="rounded bg-black px-2 py-0.5 text-xs text-white disabled:opacity-50"
                  >
                    Annehmen
                  </button>
                  <button
                    onClick={() => void remove(r.id)}
                    disabled={busy}
                    className="rounded border px-2 py-0.5 text-xs hover:bg-muted disabled:opacity-50"
                  >
                    Ablehnen
                  </button>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Freundesliste */}
      <div className="mt-4">
        <h3 className="mb-1 text-sm font-medium text-gray-600">Meine Freunde</h3>
        {friends.length === 0 ? (
          <p className="text-sm text-muted-foreground">Noch keine Freunde.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {friends.map((f) => (
              <li key={f.id} className="flex items-center justify-between border-b py-1">
                <span>
                  {f.name} <span className="text-xs text-gray-400">· {f.email}</span>
                </span>
                <button
                  onClick={() => void remove(f.id)}
                  disabled={busy}
                  className="rounded border px-2 py-0.5 text-xs hover:bg-muted disabled:opacity-50"
                >
                  Entfernen
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
