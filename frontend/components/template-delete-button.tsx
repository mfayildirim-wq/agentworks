"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

/**
 * Löscht eine Agent-Vorlage (DELETE /templates/{id}). Sitzt in einer Karte, die selbst
 * ein Link ist — daher Navigation/Bubbling unterdrücken.
 */
export function TemplateDeleteButton({
  templateId,
  title,
  redirectTo
}: {
  templateId: string;
  title: string;
  redirectTo?: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function del(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm(`„${title}“ wirklich löschen?`)) return;
    setBusy(true);
    try {
      const res = await fetch(`/api/proxy/templates/${templateId}`, { method: "DELETE" });
      if (res.ok) {
        if (redirectTo) router.push(redirectTo);
        else router.refresh();
      } else window.alert("Löschen fehlgeschlagen.");
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
      title="Vorlage löschen"
      aria-label="Vorlage löschen"
      className="rounded p-1 text-sm text-red-600 transition hover:bg-red-50 disabled:opacity-50"
    >
      {busy ? "…" : "🗑"}
    </button>
  );
}
