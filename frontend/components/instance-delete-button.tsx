"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

/** Löscht eine Agent-Instanz (DELETE /artifacts/{id}) und navigiert zum Dashboard. */
export function InstanceDeleteButton({ artifactId, title }: { artifactId: string; title: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function del() {
    if (!window.confirm(`Instanz „${title}“ wirklich löschen?`)) return;
    setBusy(true);
    try {
      const res = await fetch(`/api/proxy/artifacts/${artifactId}`, { method: "DELETE" });
      if (res.ok) router.push("/");
      else window.alert("Löschen fehlgeschlagen.");
    } catch {
      window.alert("Netzwerkfehler beim Löschen.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={del}
      disabled={busy}
      title="Instanz löschen"
      aria-label="Instanz löschen"
      className="rounded p-1.5 text-sm text-red-600 transition hover:bg-red-50 disabled:opacity-50"
    >
      {busy ? "…" : "🗑"}
    </button>
  );
}
