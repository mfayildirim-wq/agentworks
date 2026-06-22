"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { Clock, Eye, Pencil } from "lucide-react";
import { AgentAvatar } from "@/components/agent-avatar";
import { ArtifactWorkView } from "@/app/artifacts/[artifactId]/work-view";
import { viewPrefsStore } from "@/lib/view-prefs-store";
import { useI18n } from "@/lib/i18n/provider";
import type { ArtifactView, MasterInstance } from "@/lib/api";

/**
 * Master-Seite = Ergebnis-Viewer mit drei Ansichts-Modi (steuerbar über das
 * Nav-Einstellungs-Dropdown, persistiert via view-prefs-store):
 *  - "standard": bestehende horizontale Instanz-Leiste + Ansehen/Bearbeiten.
 *  - "menu":     linke Seitenleiste (vertikale Liste), rechts der Inhalt.
 *  - "grid":     Kachelraster mit HTML-Vorschau; Klick öffnet die Instanz (→ "menu").
 *
 * Der Bleistift/Auge-Umschalter (Ansehen vs. Bearbeiten) wirkt in "standard"
 * und "menu". Ansehen = iframe srcDoc; Bearbeiten = volle ArtifactWorkView.
 */
export function MasterView({
  instances,
  isOwner,
  ownerName,
  ownerId
}: {
  instances: MasterInstance[];
  isOwner: boolean;
  ownerName: string;
  ownerId: string;
}) {
  const { t } = useI18n();
  const [active, setActive] = useState(0);
  const [editMode, setEditMode] = useState(false);
  const [selView, setSelView] = useState<ArtifactView | null>(null);
  const [selLoading, setSelLoading] = useState(false);

  const prefs = useSyncExternalStore(
    viewPrefsStore.subscribe,
    viewPrefsStore.getSnapshot,
    viewPrefsStore.getServerSnapshot
  );
  const masterView = prefs.masterView;

  const cur = instances.length ? instances[Math.min(active, instances.length - 1)] : null;

  // Im Bearbeiten-Modus die volle (editierbare) Instanz-Ansicht der aktiven
  // Instanz laden (nur in "standard" und "menu" relevant).
  useEffect(() => {
    if (!editMode || !cur || masterView === "grid") {
      setSelView(null);
      return;
    }
    let cancelled = false;
    setSelLoading(true);
    setSelView(null);
    fetch(`/api/proxy/artifacts/${cur.id}`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((v) => {
        if (!cancelled) setSelView(v);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setSelLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [editMode, cur?.id, masterView]);

  // Letzte Auswahl merken (Refresh/Login): Bearbeiten/Ansehen + aktive Instanz.
  useEffect(() => {
    if (window.localStorage.getItem("aw_edit_mode") === "1") setEditMode(true);
    const aid = window.localStorage.getItem("aw_active_instance");
    if (aid) {
      const idx = instances.findIndex((i) => i.id === aid);
      if (idx >= 0) setActive(idx);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    window.localStorage.setItem("aw_edit_mode", editMode ? "1" : "0");
  }, [editMode]);
  useEffect(() => {
    if (cur) window.localStorage.setItem("aw_active_instance", cur.id);
  }, [cur?.id]);

  if (!instances.length || !cur) {
    return (
      <div className="container py-12 text-center">
        <h1 className="mb-2 text-xl font-bold">
          {isOwner ? t("master.noResults") : t("master.notPublished", { name: ownerName })}
        </h1>
        <p className="text-sm text-muted-foreground">
          {t("master.lookPre")}{" "}
          <Link href="/marktplatz" className="underline">
            {t("nav.marketplace")}
          </Link>{" "}
          {t("master.lookPost")}
        </p>
      </div>
    );
  }

  // Bleistift/Auge-Umschalter (geteilt von "standard" und "menu").
  const editToggle = isOwner ? (
    <button
      type="button"
      onClick={() => setEditMode((v) => !v)}
      aria-pressed={editMode}
      title={editMode ? t("master.viewResult") : t("master.edit")}
      className={`flex shrink-0 items-center justify-center rounded-lg border px-3 py-2 transition ${
        editMode ? "bg-black text-white" : "bg-white text-gray-700 hover:bg-muted"
      }`}
    >
      {editMode ? <Eye size={18} /> : <Pencil size={18} />}
    </button>
  ) : null;

  // Inhalt der aktiven Instanz: Bearbeiten (Work-View) ODER reine Ansicht (iframe).
  const detail = editMode ? (
    selLoading || !selView ? (
      <div className="flex min-h-0 flex-1 items-center justify-center rounded-lg border bg-white text-sm text-muted-foreground">
        {t("common.loading")}
      </div>
    ) : (
      <div className="min-h-0 flex-1">
        <ArtifactWorkView
          key={selView.id}
          initial={selView}
          artifactId={selView.id}
          layout={prefs.layout}
          onLayoutChange={(l) => viewPrefsStore.setLayout(l)}
        />
      </div>
    )
  ) : (
    <iframe
      key={cur.id}
      title={cur.title}
      srcDoc={cur.html}
      sandbox=""
      className="min-h-0 w-full flex-1 rounded-lg border bg-white"
    />
  );

  // ── Modus: Kachel (Grid) ──────────────────────────────────────────────
  if (masterView === "grid") {
    return (
      <div className="container h-[calc(100vh-4rem)] -mt-5 overflow-y-auto pb-4 pt-0">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {instances.map((a, i) => (
            <button
              key={a.id}
              type="button"
              onClick={() => {
                setActive(i);
                viewPrefsStore.setMasterView("menu");
              }}
              className="group block text-left"
            >
              <article className="flex h-44 overflow-hidden rounded-xl border bg-white shadow-sm transition hover:shadow-lg">
                {/* LINKS (40%): Vorschau des HTML-Outputs */}
                <div className="relative w-2/5 shrink-0 overflow-hidden border-r bg-white">
                  {a.html ? (
                    <iframe
                      title={`Vorschau ${a.title}`}
                      srcDoc={a.html}
                      sandbox=""
                      tabIndex={-1}
                      aria-hidden="true"
                      className="pointer-events-none absolute left-0 top-0 h-[600px] w-[800px] origin-top-left scale-[0.22] border-0"
                    />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center px-2 text-center text-[11px] text-gray-400">
                      Noch keine Seite
                    </div>
                  )}
                </div>
                {/* RECHTS (60%): Avatar + Titel & letzter Lauf */}
                <div className="flex w-3/5 flex-col gap-2 p-3">
                  <div className="flex items-start gap-2">
                    <AgentAvatar avatarUrl={a.image_url} name={a.title} size={36} />
                    <div className="min-w-0 flex-1">
                      <h3 className="line-clamp-2 text-base font-bold leading-tight text-gray-900">
                        {a.title}
                      </h3>
                      {a.updated_at && (
                        <div className="mt-1 truncate text-xs text-muted-foreground">
                          zuletzt gelaufen:{" "}
                          {new Date(a.updated_at).toLocaleDateString("de-DE", {
                            day: "2-digit",
                            month: "2-digit",
                            year: "numeric",
                            hour: "2-digit",
                            minute: "2-digit"
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </article>
            </button>
          ))}
        </div>
      </div>
    );
  }

  // ── Modus: Links-Menü (Sidebar) ───────────────────────────────────────
  if (masterView === "menu") {
    return (
      <div className="container h-[calc(100vh-4rem)] -mt-5 pb-2 pt-0">
        <div className="flex h-full gap-3">
          {/* SIDEBAR: vertikale Instanz-Liste */}
          <div
            className="flex w-60 shrink-0 flex-col gap-1 overflow-y-auto border-r pr-2 [&::-webkit-scrollbar]:hidden"
            style={{ scrollbarWidth: "none" }}
          >
            {editToggle && <div className="mb-1 flex">{editToggle}</div>}
            {instances.map((a, i) => (
              <button
                key={a.id}
                type="button"
                onClick={() => setActive(i)}
                title={a.title}
                className={`flex items-center gap-2 rounded-lg border bg-white p-2 text-left transition ${
                  i === active ? "border-black bg-gray-100 shadow-[inset_0_2px_5px_rgba(0,0,0,0.18)]" : "hover:bg-muted"
                }`}
              >
                <AgentAvatar avatarUrl={a.image_url} name={a.title} size={32} />
                <div className="min-w-0">
                  <div className="flex items-center gap-1 truncate text-sm font-bold text-gray-900">
                    {a.scheduled && <Clock size={13} className="shrink-0 text-blue-600" />}
                    <span className="truncate">{a.title}</span>
                  </div>
                </div>
              </button>
            ))}
          </div>

          {/* RECHTS: Inhalt der aktiven Instanz */}
          <div className="flex min-w-0 flex-1 flex-col">{detail}</div>
        </div>
      </div>
    );
  }

  // ── Modus: Standard (bestehend, unverändert) ──────────────────────────
  return (
    <div className="container flex h-[calc(100vh-4rem)] flex-col -mt-5 pb-2 pt-0">
      {/* Bleistift-Umschalter (links) + horizontale Instanz-Leiste */}
      <div
        className="mb-2 flex shrink-0 items-stretch gap-2 overflow-x-auto pb-1 [&::-webkit-scrollbar]:hidden"
        style={{ scrollbarWidth: "none" }}
      >
        {isOwner && (
          <button
            type="button"
            onClick={() => setEditMode((v) => !v)}
            aria-pressed={editMode}
            title={editMode ? t("master.viewResult") : t("master.edit")}
            className={`flex shrink-0 items-center justify-center rounded-lg border px-3 transition ${
              editMode ? "bg-black text-white" : "bg-white text-gray-700 hover:bg-muted"
            }`}
          >
            {editMode ? <Eye size={18} /> : <Pencil size={18} />}
          </button>
        )}
        {instances.map((a, i) => (
          <button
            key={a.id}
            type="button"
            onClick={() => setActive(i)}
            title={a.title}
            className={`flex shrink-0 items-center gap-2 rounded-lg border bg-white p-2 text-left transition ${
              i === active ? "border-black bg-gray-100 shadow-[inset_0_2px_5px_rgba(0,0,0,0.18)]" : "hover:bg-muted"
            }`}
          >
            <AgentAvatar avatarUrl={a.image_url} name={a.title} size={32} />
            <div className="min-w-0 max-w-[10rem]">
              <div className="flex items-center gap-1 truncate text-sm font-bold text-gray-900">
                {a.scheduled && <Clock size={13} className="shrink-0 text-blue-600" />}
                <span className="truncate">{a.title}</span>
              </div>
            </div>
          </button>
        ))}
      </div>

      {/* Unten: Bearbeiten (Chat + Ergebnis) ODER reine Ansicht */}
      {editMode ? (
        selLoading || !selView ? (
          <div className="flex min-h-0 flex-1 items-center justify-center rounded-lg border bg-white text-sm text-muted-foreground">
            {t("common.loading")}
          </div>
        ) : (
          <div className="min-h-0 flex-1">
            <ArtifactWorkView
              key={selView.id}
              initial={selView}
              artifactId={selView.id}
              layout={prefs.layout}
              onLayoutChange={(l) => viewPrefsStore.setLayout(l)}
            />
          </div>
        )
      ) : (
        <iframe
          key={cur.id}
          title={cur.title}
          srcDoc={cur.html}
          sandbox=""
          className="min-h-0 w-full flex-1 rounded-lg border bg-white"
        />
      )}
    </div>
  );
}
