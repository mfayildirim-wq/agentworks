/**
 * Live-synchronisierter Store für globale Ansichts-Voreinstellungen:
 *  - `masterView`: Ansichts-Modus der Master-Seite ("standard" | "menu" | "grid")
 *  - `layout`:    Chat/Ergebnis-Layout der Work-View ("side" | "stacked")
 *
 * Initialisiert clientseitig aus localStorage (Keys `aw_master_view`,
 * `aw_default_layout`). Setter schreiben localStorage UND benachrichtigen
 * Abonnenten. Für `useSyncExternalStore` wird ein STABILES Snapshot-Objekt
 * gehalten, das nur in den Settern ersetzt wird (sonst Endlosschleife).
 *
 * Kompatibilität: `aw_default_layout` bleibt der bestehende Key, den die
 * Work-View beim Mount weiterhin liest.
 */
export type MasterView = "standard" | "menu" | "grid";
export type Layout = "side" | "stacked";

export interface ViewPrefs {
  masterView: MasterView;
  layout: Layout;
}

const SERVER_SNAPSHOT: ViewPrefs = { masterView: "standard", layout: "side" };

const listeners = new Set<() => void>();
let initialized = false;
// Internes, stabiles Snapshot-Objekt (nur in Settern/Init ersetzt).
let snapshot: ViewPrefs = { masterView: "standard", layout: "side" };

function readFromStorage(): ViewPrefs {
  if (typeof window === "undefined") return { ...SERVER_SNAPSHOT };
  const mv = window.localStorage.getItem("aw_master_view");
  const ly = window.localStorage.getItem("aw_default_layout");
  return {
    masterView: mv === "standard" || mv === "menu" || mv === "grid" ? mv : "standard",
    layout: ly === "side" || ly === "stacked" ? ly : "side"
  };
}

function ensureInit() {
  if (initialized || typeof window === "undefined") return;
  initialized = true;
  snapshot = readFromStorage();
}

function emit() {
  listeners.forEach((cb) => cb());
}

export const viewPrefsStore = {
  subscribe(cb: () => void): () => void {
    ensureInit();
    listeners.add(cb);
    return () => listeners.delete(cb);
  },
  getSnapshot(): ViewPrefs {
    ensureInit();
    return snapshot;
  },
  getServerSnapshot(): ViewPrefs {
    return SERVER_SNAPSHOT;
  },
  getMasterView(): MasterView {
    ensureInit();
    return snapshot.masterView;
  },
  getLayout(): Layout {
    ensureInit();
    return snapshot.layout;
  },
  setMasterView(v: MasterView) {
    if (snapshot.masterView === v) return;
    snapshot = { ...snapshot, masterView: v };
    if (typeof window !== "undefined") window.localStorage.setItem("aw_master_view", v);
    emit();
  },
  setLayout(v: Layout) {
    if (snapshot.layout === v) return;
    snapshot = { ...snapshot, layout: v };
    if (typeof window !== "undefined") window.localStorage.setItem("aw_default_layout", v);
    emit();
  }
};
