"use client";

import { useEffect, useMemo, useState } from "react";
import type { SharedArtifact } from "@/lib/api";
import { AgentAvatar } from "@/components/agent-avatar";

/**
 * „Öffentlich": alle öffentlichen Instanzen (+ friends-Instanzen meiner Freunde) als
 * Button-Bar; rechts oben eine Suche, die nach Nutzer- oder Vorlagen-Name (und Titel)
 * filtert. Klick öffnet die öffentliche Seite der Instanz im neuen Tab.
 */
export default function PublicPage() {
  const [items, setItems] = useState<SharedArtifact[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [q, setQ] = useState("");

  useEffect(() => {
    void (async () => {
      try {
        const r = await fetch("/api/proxy/artifacts/public", { cache: "no-store" });
        if (r.ok) setItems(await r.json());
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return items;
    return items.filter(
      (a) =>
        a.title.toLowerCase().includes(s) ||
        (a.owner_name || "").toLowerCase().includes(s) ||
        (a.template_title || "").toLowerCase().includes(s)
    );
  }, [items, q]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Öffentlich</h1>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Suche: Nutzer oder Vorlage…"
          className="w-64 rounded border px-3 py-1.5 text-sm"
          aria-label="Suche nach Nutzer oder Vorlage"
        />
      </div>

      {loaded && filtered.length === 0 ? (
        <p className="text-muted-foreground">
          {items.length === 0 ? "Noch nichts öffentlich." : "Keine Treffer."}
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {filtered.map((a) => (
            <a
              key={a.artifact_id}
              href={`/p/${a.artifact_id}`}
              target="_blank"
              rel="noreferrer"
              title={`${a.title}${a.owner_name ? " · " + a.owner_name : ""}`}
              className="flex items-center gap-2 rounded-lg border bg-white p-2 text-left transition hover:border-primary"
            >
              <AgentAvatar avatarUrl={a.icon} name={a.title} size={32} />
              <div className="min-w-0 max-w-[12rem]">
                <div className="truncate text-sm font-semibold">{a.title}</div>
                <div className="truncate text-xs text-muted-foreground">
                  {a.owner_name}
                  {a.template_title ? ` · ${a.template_title}` : ""}
                </div>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
