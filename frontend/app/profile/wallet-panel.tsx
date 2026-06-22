"use client";

import { useEffect, useState } from "react";
import type { Wallet } from "@/lib/api";

export function WalletPanel() {
  const [w, setW] = useState<Wallet | null>(null);
  const [amount, setAmount] = useState(10);
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<string>("free");

  async function load() {
    const r = await fetch("/api/proxy/wallet");
    if (r.ok) {
      const data = await r.json();
      setW(data);
      setMode(data.topup_mode ?? "free");
    }
  }
  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    if (p.get("topup") === "success" && p.get("session_id")) {
      void fetch("/api/proxy/wallet/stripe/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: p.get("session_id") })
      }).then(() => load());
    }
    if (p.get("topup")) {
      window.history.replaceState({}, "", "/profile");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function topup() {
    setBusy(true);
    try {
      const r = await fetch("/api/proxy/wallet/topup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount_usd: amount })
      });
      if (r.status === 503) {
        alert("Bezahlung ist noch nicht eingerichtet.");
        return;
      }
      if (!r.ok) return;
      const body = await r.json();
      if (body.checkout_url) {
        window.location.assign(body.checkout_url);
        return;
      }
      await load();
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mt-6 rounded-lg border p-4">
      <h2 className="text-lg font-semibold">Guthaben</h2>
      <p className="mt-1 text-3xl font-bold">${Number(w?.balance_usd ?? 0).toFixed(2)}</p>
      <div className="mt-3 flex items-center gap-2">
        <input
          type="number"
          min={1}
          max={1000}
          value={amount}
          onChange={(e) => setAmount(Number(e.target.value))}
          className="w-28 rounded border px-2 py-1"
        />
        <button
          onClick={() => void topup()}
          disabled={busy}
          className="rounded bg-black px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {busy ? "Lädt…" : mode === "real" ? "Mit Karte bezahlen" : "Aufladen"}
        </button>
      </div>
      <div className="mt-4">
        <h3 className="mb-1 text-sm font-medium text-gray-600">Verlauf</h3>
        <ul className="space-y-1 text-sm">
          {(w?.ledger ?? []).map((p, i) => (
            <li key={i} className="flex justify-between border-b py-1">
              <span>
                {new Date(p.created_at).toLocaleString()} · {p.description}
                {p.app_name ? ` · ${p.app_name}` : ""}
              </span>
              <span className={Number(p.amount_usd) < 0 ? "text-red-600" : "text-green-700"}>
                {Number(p.amount_usd) >= 0 ? "+" : ""}
                {Number(p.amount_usd).toFixed(4)} $
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
