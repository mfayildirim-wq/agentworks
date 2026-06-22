"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { Visibility } from "@/lib/api";

/**
 * Besitzer-Steuerung für die Veröffentlichung einer privaten Agent-Vorlage.
 * Zeigt je nach `publish_status` einen Anfrage-Button, ein "ausstehend"-Badge
 * oder den Ablehnungsgrund + erneut-anfragen-Button. Nur sichtbar, wenn die
 * Vorlage PRIVAT ist und der Nutzer kein Admin/GOA ist (Backend bleibt der Gate).
 */
export function TemplatePublishControl({
  templateId,
  visibility,
  publishStatus,
  publishNote
}: {
  templateId: string;
  visibility: Visibility;
  publishStatus?: string;
  publishNote?: string;
}) {
  const router = useRouter();
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    void fetch("/api/proxy/users/me", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((me: { is_admin?: boolean } | null) => {
        if (active) setIsAdmin(Boolean(me?.is_admin));
      })
      .catch(() => {
        if (active) setIsAdmin(false);
      });
    return () => {
      active = false;
    };
  }, []);

  // Nur für private Vorlagen von Nicht-Admins.
  if (visibility !== "private" || isAdmin === null || isAdmin) return null;

  const status = publishStatus ?? "";

  async function request(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    setBusy(true);
    try {
      const res = await fetch(`/api/proxy/templates/${templateId}/request-publication`, {
        method: "POST"
      });
      if (res.ok) router.refresh();
      else window.alert("Anfrage fehlgeschlagen.");
    } catch {
      window.alert("Netzwerkfehler bei der Anfrage.");
    } finally {
      setBusy(false);
    }
  }

  if (status === "pending") {
    return (
      <div className="mt-1 rounded bg-amber-50 px-2 py-1 text-center text-xs text-amber-800">
        Veröffentlichung ausstehend
      </div>
    );
  }

  if (status === "rejected") {
    return (
      <div className="mt-1 space-y-1">
        <div className="rounded bg-red-50 px-2 py-1 text-xs text-red-700">
          Abgelehnt{publishNote ? `: ${publishNote}` : ""}
        </div>
        <button
          type="button"
          onClick={request}
          disabled={busy}
          className="w-full rounded border px-2 py-1 text-xs hover:bg-muted disabled:opacity-50"
        >
          {busy ? "…" : "Erneut anfragen"}
        </button>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={request}
      disabled={busy}
      className="mt-1 w-full rounded bg-black px-2 py-1 text-xs text-white disabled:opacity-50"
    >
      {busy ? "…" : "Veröffentlichung anfragen"}
    </button>
  );
}
