"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import {
  ChevronDown,
  Columns2,
  LayoutGrid,
  LayoutPanelTop,
  PanelLeft,
  Plus,
  Rows2,
  SlidersHorizontal
} from "lucide-react";
import { instanceConfigStore } from "@/lib/instance-config-store";
import { viewPrefsStore, type MasterView, type Layout } from "@/lib/view-prefs-store";
import { useI18n } from "@/lib/i18n/provider";

/**
 * Agent-UI-Einstellungen in der Navi (neben dem Benutzer-Icon): Icon + Dropdown.
 * Geordnetes Menü:
 *  1. + Neue Instanz (→ /marktplatz)
 *  2. Ansicht (Standard | Links-Menü | Kachel → viewPrefsStore.setMasterView)
 *  3. Chat/Ergebnis (Horizontal | Vertikal → setLayout)
 *  4. Instanz-Konfig (Button → Popup: Sichtbarkeit/Kosten/Kette/ext. Link)
 *  5. Template (Button → Popup: Agent-Template-Bewertung)
 * 4 und 5 nur sichtbar, wenn eine Instanz offen ist (Work-View schiebt die Knoten
 * via instanceConfigStore hinein). Ansicht/Chat-Ergebnis live via view-prefs-store.
 */
export function AgentUiSettings() {
  const { t, lang, setLang } = useI18n();
  const [open, setOpen] = useState(false);
  // Aufgeklapptes Konfig-Popup im Dropdown: "instanz" | "template" | null.
  const [panel, setPanel] = useState<"instanz" | "template" | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  const prefs = useSyncExternalStore(
    viewPrefsStore.subscribe,
    viewPrefsStore.getSnapshot,
    viewPrefsStore.getServerSnapshot
  );

  // Kontextabhängig: die zwei Konfig-Knoten der gerade offenen Instanz
  // (Work-View schiebt sie via Store hinein). Ohne offene Instanz: null.
  const cfg = useSyncExternalStore(
    instanceConfigStore.subscribe,
    instanceConfigStore.getSnapshot,
    instanceConfigStore.getServerSnapshot
  );

  useEffect(() => {
    if (!open) {
      setPanel(null); // Beim Schließen des Dropdowns das Konfig-Popup zuklappen.
      return;
    }
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const viewModes: { v: MasterView; title: string; Icon: typeof LayoutPanelTop }[] = [
    { v: "standard", title: "Standard", Icon: LayoutPanelTop },
    { v: "menu", title: "Links-Menü", Icon: PanelLeft },
    { v: "grid", title: "Kachel", Icon: LayoutGrid }
  ];
  const layouts: { v: Layout; title: string; Icon: typeof Columns2 }[] = [
    { v: "side", title: "Horizontal", Icon: Columns2 },
    { v: "stacked", title: "Vertikal", Icon: Rows2 }
  ];

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex h-8 w-8 items-center justify-center rounded-full border hover:bg-muted"
        aria-label="Agent-UI-Einstellungen"
        aria-haspopup="menu"
        aria-expanded={open}
        title="Agent-UI-Einstellungen"
      >
        <SlidersHorizontal size={16} />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 top-10 z-20 max-h-[75vh] w-80 overflow-y-auto rounded-md border bg-background p-3 text-sm shadow-md"
        >
          {/* Sprache (DE/EN) */}
          <div className="mb-3 flex items-center gap-2">
            <span className="text-xs font-semibold text-muted-foreground">{t("settings.language")}</span>
            <div className="flex gap-1">
              <button type="button" onClick={() => setLang("de")}
                className={`rounded border px-2 py-0.5 text-xs ${lang === "de" ? "bg-black text-white" : "hover:bg-muted"}`}>
                DE
              </button>
              <button type="button" onClick={() => setLang("en")}
                className={`rounded border px-2 py-0.5 text-xs ${lang === "en" ? "bg-black text-white" : "hover:bg-muted"}`}>
                EN
              </button>
            </div>
          </div>

          {/* 1. Neue Instanz anlegen */}
          <Link
            href="/marktplatz"
            onClick={() => setOpen(false)}
            className="mb-3 flex items-center gap-2 rounded border px-2 py-1.5 text-xs font-medium hover:bg-muted"
          >
            <Plus size={14} /> {t("settings.newInstance")}
          </Link>

          {/* 2. Ansicht (Master-Seite): nur Icons. */}
          <p className="mb-1 text-xs font-semibold text-muted-foreground">Ansicht</p>
          <div className="mb-2 flex gap-1">
            {viewModes.map(({ v, title, Icon }) => (
              <button
                key={v}
                type="button"
                title={title}
                aria-label={title}
                aria-pressed={prefs.masterView === v}
                onClick={() => viewPrefsStore.setMasterView(v)}
                className={`flex flex-1 items-center justify-center rounded border p-1.5 ${
                  prefs.masterView === v ? "bg-black text-white" : "text-gray-600 hover:bg-muted"
                }`}
              >
                <Icon size={16} />
              </button>
            ))}
          </div>

          {/* 3. Chat/Ergebnis (Layout): nur Icons. */}
          <p className="mb-1 text-xs font-semibold text-muted-foreground">Chat/Ergebnis</p>
          <div className="mb-3 flex gap-1">
            {layouts.map(({ v, title, Icon }) => (
              <button
                key={v}
                type="button"
                title={title}
                aria-label={title}
                aria-pressed={prefs.layout === v}
                onClick={() => viewPrefsStore.setLayout(v)}
                className={`flex flex-1 items-center justify-center rounded border p-1.5 ${
                  prefs.layout === v ? "bg-black text-white" : "text-gray-600 hover:bg-muted"
                }`}
              >
                <Icon size={16} />
              </button>
            ))}
          </div>

          {/* Externer Link — eigener Menüpunkt, über Instanz-Konfig (nur wenn vorhanden). */}
          {cfg?.externalUrl && (
            <a
              href={cfg.externalUrl}
              target="_blank"
              rel="noreferrer"
              onClick={() => setOpen(false)}
              className="mb-2 flex items-center justify-between rounded border px-2 py-1.5 text-xs font-medium hover:bg-muted"
            >
              <span>Externe Seite</span>
              <span aria-hidden>↗</span>
            </a>
          )}

          {/* 4. Instanz-Konfig — Button + aufklappbares Popup (nur bei offener Instanz). */}
          {cfg?.instanz && (
            <div className="mb-2">
              <button
                type="button"
                aria-expanded={panel === "instanz"}
                onClick={() => setPanel((p) => (p === "instanz" ? null : "instanz"))}
                className="flex w-full items-center justify-between rounded border px-2 py-1.5 text-xs font-medium hover:bg-muted"
              >
                <span>Instanz-Konfig</span>
                <ChevronDown
                  size={14}
                  className={`transition-transform ${panel === "instanz" ? "rotate-180" : ""}`}
                />
              </button>
              {panel === "instanz" && (
                <div className="mt-2 rounded-md border bg-muted/30 p-2">{cfg.instanz}</div>
              )}
            </div>
          )}

          {/* 5. Template — Button + aufklappbares Popup (nur bei offener Instanz). */}
          {cfg?.template && (
            <div>
              <button
                type="button"
                aria-expanded={panel === "template"}
                onClick={() => setPanel((p) => (p === "template" ? null : "template"))}
                className="flex w-full items-center justify-between rounded border px-2 py-1.5 text-xs font-medium hover:bg-muted"
              >
                <span>Template</span>
                <ChevronDown
                  size={14}
                  className={`transition-transform ${panel === "template" ? "rotate-180" : ""}`}
                />
              </button>
              {panel === "template" && (
                <div className="mt-2 rounded-md border bg-muted/30 p-2">{cfg.template}</div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
