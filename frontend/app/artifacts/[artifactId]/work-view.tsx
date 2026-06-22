"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AgentAvatar } from "@/components/agent-avatar";
import { ChainBar } from "./chain-bar";
import { JobsList } from "./jobs-list";
import { instanceConfigStore } from "@/lib/instance-config-store";
import type { ArtifactCommand, ArtifactMessage, ArtifactView, SlotData } from "@/lib/api";
import { CONNECTION_KINDS } from "@/lib/api";
import { themeTemplate } from "@/lib/canvas/themes";
import { buildSlotIframeDoc } from "@/lib/canvas/slot-iframe";
import { useI18n } from "@/lib/i18n/provider";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// Links im Canvas/iFrame sollen in einem NEUEN Tab öffnen. `<base target="_blank">`
// im Dokument + `allow-popups…` am sandboxed iFrame (sonst blockt die Sandbox Pop-ups).
const POPUP_SANDBOX = "allow-popups allow-popups-to-escape-sandbox";
function withBaseTarget(html: string): string {
  const base = '<base target="_blank">';
  if (/<head[^>]*>/i.test(html)) return html.replace(/<head[^>]*>/i, (m) => m + base);
  if (/<html[^>]*>/i.test(html)) return html.replace(/<html[^>]*>/i, (m) => `${m}<head>${base}</head>`);
  return base + html;
}

function humanSize(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

const CHIPS_RE = /```chips\s*\n([\s\S]*?)```/;
function splitChips(content: string): { text: string; chips: string[] } {
  const m = content.match(CHIPS_RE);
  if (!m) return { text: content, chips: [] };
  const chips = m[1].split("\n").map((s) => s.trim()).filter(Boolean);
  return { text: content.replace(CHIPS_RE, "").trim(), chips };
}

/**
 * Dialog-Agent-Ansicht: links der Chat (Fragen/Infos), rechts der HTML-Canvas
 * (das Ergebnis, z.B. der Reiseplan). Der Agent fragt zuerst im Chat und legt das
 * Ergebnis erst dann in den Canvas — die Kommunikation landet nicht mehr im HTML.
 */
export function ArtifactWorkView({
  initial,
  artifactId,
  defaultLayout,
  layout: layoutProp,
  onLayoutChange
}: {
  initial: ArtifactView;
  artifactId: string;
  defaultLayout?: "side" | "stacked";
  layout?: "side" | "stacked";
  onLayoutChange?: (l: "side" | "stacked") => void;
}) {
  const { t } = useI18n();
  const [layoutState, setLayoutState] = useState<"side" | "stacked">(defaultLayout ?? "side");
  const isControlled = layoutProp !== undefined;
  // Globale Standard-Ansicht (Agent-UI-Einstellung in der Navi) anwenden, wenn diese
  // Instanz-Ansicht weder kontrolliert noch ein Layout fest vorgegeben ist.
  useEffect(() => {
    if (isControlled || defaultLayout) return;
    const pref = typeof window !== "undefined" ? window.localStorage.getItem("aw_default_layout") : null;
    if (pref === "side" || pref === "stacked") setLayoutState(pref);
  }, [isControlled, defaultLayout]);
  const layout = isControlled ? layoutProp : layoutState;
  // Layout-Umschalter sitzt jetzt im Nav-Dropdown („Chat/Ergebnis"); die frühere
  // lokale changeLayout-Funktion entfällt. onLayoutChange bleibt als Prop erhalten.
  void onLayoutChange;
  const [view, setView] = useState<ArtifactView>(initial);
  const [messages, setMessages] = useState<ArtifactMessage[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState<{ id: string; filename: string; url: string }[]>([]);
  const [files, setFiles] = useState<
    { id: string; filename: string; url: string; content_type: string; size: number }[]
  >([]);
  const [showFiles, setShowFiles] = useState(false);
  const [fileFilter, setFileFilter] = useState<"all" | "image" | "doc">("all");
  const fileRef = useRef<HTMLInputElement>(null);
  // "/"-Befehlsmenü + Modus-Chip + Verlauf-Panel
  const [commands, setCommands] = useState<ArtifactCommand[] | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [newTabName, setNewTabName] = useState<string | null>(null);
  // Template-Befehl mit {input}-Platzhalter: hier wird der Wert eingegeben.
  const [cmdInput, setCmdInput] = useState<{ cmd: ArtifactCommand; value: string } | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [sectionsOpen, setSectionsOpen] = useState(false);
  const [sections, setSections] = useState<
    { layout: string; slots: { id: string; title: string; order: number }[] } | null
  >(null);
  const [sectionsError, setSectionsError] = useState<string | null>(null);
  const [sectionTitles, setSectionTitles] = useState<Record<string, string>>({});
  const [previewVersion, setPreviewVersion] = useState<
    { version_no: number; content: string; created_at: string; prompt: string } | null
  >(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [balance, setBalance] = useState<number | null>(null);
  const [delta, setDelta] = useState<number | null>(null);
  const prevCostRef = useRef<number | null>(null);
  const [rightView, setRightView] = useState<"result" | "connection">("result");
  const [copiedLink, setCopiedLink] = useState(false);
  const [myStars, setMyStars] = useState<number>(initial.my_stars ?? 0);
  const [hoverStar, setHoverStar] = useState<number>(0);
  const [ratingComment, setRatingComment] = useState("");
  const [ratingSaved, setRatingSaved] = useState(false);
  // Ziehbarer Splitter (nur "side"-Layout ab lg): Chat-Spaltenbreite in Prozent.
  const [splitPct, setSplitPct] = useState(50);
  const splitDragRef = useRef<HTMLDivElement>(null);

  const submitRating = useCallback(
    async (stars: number) => {
      setMyStars(stars);
      const res = await fetch(`/api/proxy/agents/${view.agent_id}/rating`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stars, comment: ratingComment })
      });
      if (res.ok && mounted.current) {
        const r = (await res.json()) as { avg_stars: number; ratings_count: number; my_stars: number };
        setMyStars(r.my_stars);
        setView((v) => ({
          ...v,
          my_stars: r.my_stars,
          agent_rating_avg: r.avg_stars,
          agent_rating_count: r.ratings_count
        }));
        setRatingSaved(true);
        setTimeout(() => mounted.current && setRatingSaved(false), 2000);
      }
    },
    [view.agent_id, ratingComment]
  );

  const setVisibility = useCallback(
    async (visibility: string) => {
      const res = await fetch(`/api/proxy/artifacts/${artifactId}/visibility`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ visibility })
      });
      if (res.ok && mounted.current) {
        setView((v) => ({ ...v, visibility: visibility as ArtifactView["visibility"] }));
      }
    },
    [artifactId]
  );

  const copyShareLink = useCallback(() => {
    const url = `${window.location.origin}/p/${artifactId}`;
    void navigator.clipboard?.writeText(url);
    setCopiedLink(true);
    setTimeout(() => mounted.current && setCopiedLink(false), 1500);
  }, [artifactId]);
  // Mobil (< lg) ist das Layout einspaltig — dieser Tab steuert, welche Spalte sichtbar ist.
  const [mobileTab, setMobileTab] = useState<"chat" | "right">("chat");
  const [connConfigs, setConnConfigs] = useState<Record<string, Record<string, string>>>({});
  const [connSecrets, setConnSecrets] = useState<Record<string, string>>({});
  const [connStatus, setConnStatus] = useState<string | null>(null);
  const [slotData, setSlotData] = useState<SlotData>({ layout: "sections", slots: [] });
  const slotIframeRef = useRef<HTMLIFrameElement | null>(null);
  const [designCss, setDesignCss] = useState<string>("");
  const [iframeReady, setIframeReady] = useState(false);
  const design = view.html_template_id || "classic";
  const isSlots = view.content_mode === "slots";
  // Pro-Instanz-Ausgabevorlage: bei "prepared:*"/"slots:*" rendert current_content
  // ein eigenstaendiges HTML mit kuratiertem Inline-JS -> Skripte erlauben.
  // Bei "agent"/Altbestand bleibt es ohne Skripte.
  const ot = view.output_template || "";
  const resultSandbox =
    ot.startsWith("prepared:") || ot.startsWith("slots:")
      ? `allow-scripts ${POPUP_SANDBOX}`
      : POPUP_SANDBOX;
  const kinds = view.publish_targets || [];
  const mcpCreds = view.mcp_credentials || [];
  const canPublish = kinds.length > 0 || mcpCreds.length > 0;
  const hasSftp = kinds.includes("sftp");
  const mounted = useRef(true);
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadBalance = useCallback(async () => {
    const res = await fetch("/api/proxy/wallet", { cache: "no-store" });
    if (res.ok && mounted.current) {
      const w = (await res.json()) as { balance_usd: string };
      setBalance(Number(w.balance_usd));
    }
  }, []);

  const loadMessages = useCallback(async (): Promise<ArtifactMessage[]> => {
    const res = await fetch(`/api/proxy/artifacts/${artifactId}/messages`, { cache: "no-store" });
    if (!res.ok) return [];
    const m = (await res.json()) as ArtifactMessage[];
    if (mounted.current) setMessages(m);
    return m;
  }, [artifactId]);

  const refreshView = useCallback(async () => {
    const res = await fetch(`/api/proxy/artifacts/${artifactId}`, { cache: "no-store" });
    if (res.ok && mounted.current) {
      const v = (await res.json()) as ArtifactView;
      setView(v);
      // Verbrauch-Delta dieses Turns kurz einblenden + Guthaben auffrischen.
      const newCost = Number(v?.cost_total_usd ?? 0);
      if (prevCostRef.current != null && newCost > prevCostRef.current) {
        setDelta(newCost - prevCostRef.current);
        setTimeout(() => mounted.current && setDelta(null), 3000);
      }
      prevCostRef.current = newCost;
      void loadBalance();
    }
  }, [artifactId, loadBalance]);

  const loadFiles = useCallback(async () => {
    const res = await fetch(`/api/proxy/artifacts/${artifactId}/files`, { cache: "no-store" });
    if (res.ok && mounted.current) setFiles(await res.json());
  }, [artifactId]);

  const loadConns = useCallback(async () => {
    const res = await fetch(`/api/proxy/artifacts/${artifactId}/connections`, { cache: "no-store" });
    if (res.ok && mounted.current) {
      const items = (await res.json()) as { kind: string; config: Record<string, string> }[];
      const cfgs: Record<string, Record<string, string>> = {};
      items.forEach((i) => (cfgs[i.kind] = i.config || {}));
      setConnConfigs(cfgs);
    }
  }, [artifactId]);

  const loadSlots = useCallback(async () => {
    const res = await fetch(`/api/proxy/artifacts/${artifactId}/slots`, { cache: "no-store" });
    if (res.ok && mounted.current) {
      const d = (await res.json()) as SlotData;
      setSlotData(d);
    }
  }, [artifactId]);

  // Das iframe-Dokument haengt NUR von Design + CSS ab — bleibt also stabil,
  // damit ein Slot-Edit den iframe NICHT neu laedt (Re-Render via postMessage).
  const slotSrcDoc = useMemo(
    () => buildSlotIframeDoc(designCss, themeTemplate(design)),
    [designCss, design]
  );

  // Schickt die aktuellen (vorsortierten) Slots an den iframe.
  const postSlots = useCallback(() => {
    slotIframeRef.current?.contentWindow?.postMessage(
      {
        type: "render",
        design,
        data: {
          slots: [...(slotData.slots || [])].sort((a, b) => (a.order || 0) - (b.order || 0)),
          layout: slotData.layout || "sections"
        }
      },
      "*"
    );
  }, [slotData, design]);

  // Design-CSS einmalig laden (nur bei Slots-Instanzen).
  useEffect(() => {
    if (!isSlots) return;
    void (async () => {
      const res = await fetch("/api/proxy/html-templates", { cache: "no-store" });
      if (!res.ok || !mounted.current) return;
      const items = (await res.json()) as { id: string; css?: string }[];
      const item = items.find((i) => i.id === design);
      setDesignCss(item?.css || "");
    })();
  }, [isSlots, design]);

  // postMessage-Verdrahtung: NUR Events des eigenen iframe akzeptieren
  // (e.source-Check, da der sandboxed iframe Origin "null" hat). Auf "ready"
  // sofort die aktuellen Slots posten.
  useEffect(() => {
    if (!isSlots) return;
    function onMessage(e: MessageEvent) {
      if (e.source !== slotIframeRef.current?.contentWindow) return;
      if (e.data?.type === "ready") {
        setIframeReady(true);
        postSlots();
      }
      if (e.data?.type === "action" && typeof e.data.prompt === "string") {
        const p = e.data.prompt.trim();
        if (p && window.confirm(t("wv.confirmAction", { prompt: p }))) void sendMessage(p);
      }
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [isSlots, postSlots]);

  // Slot-Aenderung -> neu posten (sobald iframe bereit ist).
  useEffect(() => {
    if (isSlots && iframeReady) postSlots();
  }, [slotData, iframeReady, isSlots, postSlots]);

  async function saveConn(kind: string) {
    const res = await fetch(`/api/proxy/artifacts/${artifactId}/connections/${kind}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config: connConfigs[kind] || {}, secret: connSecrets[kind] || "" })
    });
    if (res.ok) { setConnStatus(t("wv.connSaved", { kind })); setConnSecrets((s) => ({ ...s, [kind]: "" })); }
    else setConnStatus((await res.text()) || t("wv.saveFailed"));
  }

  async function publishNow() {
    setConnStatus(t("wv.publishing"));
    const res = await fetch(`/api/proxy/artifacts/${artifactId}/publish`, { method: "POST" });
    const body = res.ok ? await res.json() : { ok: false, message: t("wv.error") };
    setConnStatus(body.message);
  }

  async function onPickFiles(e: React.ChangeEvent<HTMLInputElement>) {
    const list = e.target.files;
    if (!list?.length) return;
    const fd = new FormData();
    Array.from(list).forEach((f) => fd.append("files", f));
    const res = await fetch(`/api/proxy/artifacts/${artifactId}/files`, {
      method: "POST",
      body: fd
    });
    if (res.ok) {
      const saved = (await res.json()) as { id: string; filename: string; url: string }[];
      setPending((p) => [...p, ...saved]);
      loadFiles();
    } else {
      setError((await res.text()) || t("wv.uploadFailed"));
    }
    if (fileRef.current) fileRef.current.value = "";
  }

  // Befehle (/-Menü) laden + cachen.
  const ensureCommands = useCallback(async (): Promise<ArtifactCommand[]> => {
    if (commands) return commands;
    const res = await fetch(`/api/proxy/artifacts/${artifactId}/commands`, { cache: "no-store" });
    if (!res.ok) return [];
    const list = (await res.json()) as ArtifactCommand[];
    if (mounted.current) setCommands(list);
    return list;
  }, [artifactId, commands]);

  async function applyMode(mode: string) {
    const res = await fetch(`/api/proxy/artifacts/${artifactId}/output-mode`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode })
    });
    if (res.ok && mounted.current) {
      const r = (await res.json()) as { mode: string };
      setView((v) => ({ ...v, output_mode: r.mode }));
    }
  }

  // Benannten neuen Tab anlegen: leeren Tab mit Namen (aktiv/vorn), Layout=Tabs,
  // Modus „überarbeiten" → der nächste Lauf füllt genau diesen Tab.
  async function createNamedTab(name: string) {
    const title = name.trim();
    if (!title) return;
    const id = Math.random().toString(36).slice(2, 10);
    await fetch(`/api/proxy/artifacts/${artifactId}/layout`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ layout: "tabs" })
    });
    await fetch(`/api/proxy/artifacts/${artifactId}/slots/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, body: "<p></p>", type: "richtext", order: -1 })
    });
    await applyMode("ueberarbeiten");
    setNewTabName(null);
    setMenuOpen(false);
    await loadSections();
    await loadSlots();
    await refreshView();
  }

  // Tabs (Slots) fuer das Panel laden; aktualisiert auch den Canvas
  // (slotData -> postMessage -> iframe re-render), kein Reload noetig.
  const loadSections = useCallback(async () => {
    setSectionsError(null);
    const res = await fetch(`/api/proxy/artifacts/${artifactId}/slots`, { cache: "no-store" });
    if (res.status === 404) {
      if (mounted.current) {
        setSections(null);
        setSectionsError(t("wv.noTabsYet"));
      }
      return;
    }
    if (res.ok && mounted.current) {
      const d = (await res.json()) as { layout: string; slots: { id: string; title: string; order: number }[] };
      setSections(d);
      setSectionTitles(Object.fromEntries((d.slots || []).map((s) => [s.id, s.title])));
      setSlotData(d as SlotData);
    }
  }, [artifactId]);

  async function setSectionsLayout(newLayout: string) {
    const res = await fetch(`/api/proxy/artifacts/${artifactId}/layout`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ layout: newLayout })
    });
    if (res.ok) await loadSections();
  }

  async function renameSection(slotId: string) {
    const title = sectionTitles[slotId] ?? "";
    const res = await fetch(`/api/proxy/artifacts/${artifactId}/slots/${slotId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title })
    });
    if (res.ok) await loadSections();
  }

  async function deleteSection(slotId: string) {
    const res = await fetch(`/api/proxy/artifacts/${artifactId}/slots/${slotId}`, {
      method: "DELETE"
    });
    if (res.ok) await loadSections();
  }

  async function moveSection(slotId: string, dir: -1 | 1) {
    const sorted = [...(sections?.slots || [])].sort((a, b) => (a.order || 0) - (b.order || 0));
    const i = sorted.findIndex((s) => s.id === slotId);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= sorted.length) return;
    const a = sorted[i];
    const b = sorted[j];
    const put = (id: string, order: number) =>
      fetch(`/api/proxy/artifacts/${artifactId}/slots/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ order })
      });
    const [r1, r2] = await Promise.all([put(a.id, b.order), put(b.id, a.order)]);
    if (r1.ok && r2.ok) await loadSections();
  }

  // Template-Befehl ausführen: Modus setzen, dann Anweisung (mit {input} ersetzt) als Lauf.
  async function runTemplateCommand(cmd: ArtifactCommand, inputValue?: string) {
    const filled = (cmd.instruction ?? "").replace(/\{input\}/g, inputValue ?? "");
    setCmdInput(null);
    setMenuOpen(false);
    if (cmd.mode) await applyMode(cmd.mode);
    await sendMessage(filled);
  }

  async function runCommand(cmd: ArtifactCommand) {
    if (cmd.kind === "template") {
      // Mit {input}-Platzhalter: erst nach Wert fragen (Muster wie newTabName).
      if (cmd.instruction?.includes("{input}")) {
        setCmdInput({ cmd, value: "" });
        return;
      }
      await runTemplateCommand(cmd);
      return;
    }
    setMenuOpen(false);
    if (cmd.kind === "mode") {
      await applyMode(cmd.key);
    } else if (cmd.kind === "action" && cmd.key === "abschnitte") {
      setSectionsOpen(true);
      await loadSections();
    } else if (cmd.kind === "action" && cmd.key === "refresh") {
      void sendMessage("Seite aktualisieren");
    }
  }

  const toggleMenu = useCallback(async () => {
    if (!menuOpen) {
      await ensureCommands();
      if (mounted.current) setMenuOpen(true);
    } else {
      setMenuOpen(false);
    }
  }, [menuOpen, ensureCommands]);

  // "/" als erstes Zeichen im Eingabefeld öffnet das Menü ebenfalls (und leert das Feld).
  useEffect(() => {
    if (input === "/") {
      setInput("");
      void toggleMenu();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [input]);

  // Außerhalb-Klick schließt das Menü.
  useEffect(() => {
    if (!menuOpen) return;
    function onDown(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [menuOpen]);

  // Splitter ziehen: Maus bewegt die Trennlinie -> Chat-Breite in % (25–75 geklemmt).
  const onSplitStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const container = splitDragRef.current?.parentElement;
    if (!container) return;
    function onMove(ev: MouseEvent) {
      const rect = container!.getBoundingClientRect();
      if (rect.width <= 0) return;
      const pct = ((ev.clientX - rect.left) / rect.width) * 100;
      setSplitPct(Math.min(75, Math.max(25, pct)));
    }
    function onUp() {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.body.style.userSelect = "";
    }
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, []);

  async function viewVersion(versionId: string) {
    const res = await fetch(`/api/proxy/artifacts/${artifactId}/versions/${versionId}`, {
      cache: "no-store"
    });
    if (res.ok && mounted.current) {
      setPreviewVersion(
        (await res.json()) as { version_no: number; content: string; created_at: string; prompt: string }
      );
    }
  }

  async function restoreVersion(versionId: string) {
    const res = await fetch(`/api/proxy/artifacts/${artifactId}/versions/${versionId}/restore`, {
      method: "POST"
    });
    if (res.ok) location.reload();
  }

  async function deleteFile(id: string) {
    const res = await fetch(`/api/proxy/artifacts/${artifactId}/files/${id}`, {
      method: "DELETE"
    });
    if (res.ok) {
      setFiles((f) => f.filter((x) => x.id !== id));
      setPending((p) => p.filter((x) => x.id !== id));
    }
  }

  // Pollt, bis die Zahl der Assistant-Nachrichten über `from` steigt (neue Antwort da).
  const waitForReply = useCallback(
    async (from: number): Promise<boolean> => {
      for (let i = 0; i < 90 && mounted.current; i++) {
        await sleep(2000);
        if (!mounted.current) return false;
        const m = await loadMessages();
        if (m.filter((x) => x.role === "assistant").length > from) {
          await refreshView();
          return true;
        }
      }
      return false;
    },
    [loadMessages, refreshView]
  );

  // Erstes Öffnen: Verlauf laden; ist er leer, den Begrüßungs-Turn anstoßen.
  useEffect(() => {
    mounted.current = true;
    prevCostRef.current = Number(initial?.cost_total_usd ?? 0);
    void (async () => {
      const m = await loadMessages();
      void loadFiles();
      void loadBalance();
      void ensureCommands();
      if (canPublish) void loadConns();
      if (isSlots) void loadSlots();
      if (m.length === 0) {
        setBusy(true);
        await fetch(`/api/proxy/artifacts/${artifactId}/start`, { method: "POST" });
        const ok = await waitForReply(0);
        if (!ok && mounted.current) {
          setError(t("wv.agentSlow"));
        }
        if (mounted.current) setBusy(false);
      }
    })();
    return () => {
      mounted.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  async function sendMessage(raw: string) {
    const text = raw.trim();
    if (!text || busy) return;
    setBusy(true);
    setError(null);
    const before = messages.filter((x) => x.role === "assistant").length;
    setMessages((prev) => [
      ...prev,
      {
        id: `tmp-${prev.length}`,
        role: "user",
        content: text,
        version_id: null,
        version_no: null,
        created_at: new Date().toISOString()
      }
    ]);
    setInput("");
    setPending([]);
    try {
      const res = await fetch(`/api/proxy/artifacts/${artifactId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, file_ids: pending.map((p) => p.id) })
      });
      if (!res.ok) {
        setError((await res.text()) || t("wv.error"));
        return;
      }
      const ok = await waitForReply(before);
      if (!ok && mounted.current) {
        setError(t("wv.tookLonger"));
      }
    } catch {
      setError(t("wv.networkRetry"));
    } finally {
      if (mounted.current) setBusy(false);
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    await sendMessage(input);
  }

  const hasCanvas = Boolean(view.current_content);
  const lastAssistantId = [...messages].reverse().find((x) => x.role === "assistant")?.id;

  // Layout-abhaengige Wrapper-Klassen: "side" = bisheriges Verhalten (Mobil-Tabs +
  // lg:grid-cols-2, 78vh), "stacked" = Chat oben / Canvas darunter (beide voll, 46vh).
  const chatColClass =
    layout === "stacked"
      ? "flex flex-col"
      : `${mobileTab === "chat" ? "flex" : "hidden"} lg:flex h-[78vh] flex-col rounded-lg border`;
  const rightColClass =
    layout === "stacked"
      ? "flex h-[60vh] flex-col"
      : `${mobileTab === "right" ? "flex" : "hidden"} lg:flex h-[78vh] flex-col rounded-lg border p-2`;
  // Im gestapelten Layout ist der Chat-Log kompakt: feste ~5-Zeilen-Hoehe, kein Scroll,
  // neueste Nachrichten unten (justify-end + overflow-hidden klippt aeltere oben weg).
  const msgListClass =
    layout === "stacked"
      ? "h-52 space-y-2 overflow-y-auto p-3"
      : "flex-1 space-y-3 overflow-y-auto p-3";

  const mobileTabBar = (
    /* Mobil-Tabs: nur unter lg sichtbar; schalten Chat / Ergebnis / Verbindung um */
    <div className="flex gap-1 lg:hidden">
      <button type="button" onClick={() => setMobileTab("chat")}
        className={`flex-1 rounded border px-2 py-1.5 text-sm ${mobileTab === "chat" ? "bg-black text-white" : ""}`}>
        {t("wv.chat")}
      </button>
      <button type="button" onClick={() => { setMobileTab("right"); setRightView("result"); }}
        className={`flex-1 rounded border px-2 py-1.5 text-sm ${mobileTab === "right" && rightView === "result" ? "bg-black text-white" : ""}`}>
        {t("wv.result")}
      </button>
      {canPublish && (
        <button type="button" onClick={() => { setMobileTab("right"); setRightView("connection"); }}
          className={`flex-1 rounded border px-2 py-1.5 text-sm ${mobileTab === "right" && rightView === "connection" ? "bg-black text-white" : ""}`}>
          {t("wv.connection")}
        </button>
      )}
    </div>
  );

  // Instanz-Konfig (Popup 1 im Nav-Dropdown): Sichtbarkeit (als Button-Auswahl),
  // Kosten/Guthaben, Kette (nächster Agent), externer Link. Funktionen/States 1:1
  // wiederverwendet. Wird via Store ins Nav-Dropdown „Agent-UI-Einstellungen"
  // geschoben (siehe useEffect unten). Die frühere „Ansicht (Layout)"-Sektion
  // entfällt hier — Layout wird im Dropdown über „Chat/Ergebnis" gesteuert.
  const instanzKonfig = (
        <div className="space-y-3">
          {/* Sichtbarkeit / Teilen — als Button-Auswahl */}
          {view.is_owner ? (
            <div className="space-y-1.5">
              <p className="text-xs font-semibold text-gray-600">{t("wv.visibility")}</p>
              <div className="flex gap-1">
                {([
                  ["private", t("wv.private")],
                  ["friends", t("wv.friends")],
                  ["public", t("wv.public")]
                ] as const).map(([v, label]) => {
                  const active =
                    (view.visibility === "friends" || view.visibility === "public"
                      ? view.visibility
                      : "private") === v;
                  return (
                    <button
                      key={v}
                      type="button"
                      onClick={() => void setVisibility(v)}
                      className={`flex-1 rounded border px-2 py-1 text-xs ${
                        active ? "bg-black text-white" : "hover:bg-muted"
                      }`}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
              {(view.visibility === "friends" || view.visibility === "public") && (
                <div className="flex flex-wrap items-center gap-2 text-xs text-gray-600">
                  <button
                    type="button"
                    onClick={copyShareLink}
                    title={`/p/${artifactId}`}
                    className="rounded border px-1.5 py-0.5 hover:bg-muted"
                  >
                    {copiedLink ? t("wv.copied") : t("wv.copyLink")}
                  </button>
                  <a
                    href={`/p/${artifactId}`}
                    target="_blank"
                    rel="noreferrer"
                    title={t("wv.openExternalTitle")}
                    className="rounded border px-1.5 py-0.5 hover:bg-muted"
                  >
                    {t("wv.open")}
                  </a>
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs text-gray-400">
              {t("wv.shareable")}{" "}
              <a className="underline" href={`/p/${artifactId}`} target="_blank" rel="noreferrer">
                /p/{artifactId}
              </a>
            </p>
          )}

          {/* Kosten / Guthaben */}
          <div className="space-y-0.5 border-t pt-3 text-xs text-gray-500">
            {view.cost_total_usd != null && (
              <p>{t("wv.instanceCost", { cost: Number(view.cost_total_usd).toFixed(2) })}</p>
            )}
            <p className="flex flex-wrap items-center gap-3 text-muted-foreground">
              <span title={t("wv.thisAppUsage")}>{t("wv.thisApp", { cost: Number(view?.cost_total_usd ?? 0).toFixed(4) })}</span>
              <span title={t("wv.yourBalance")}>{t("wv.balance", { balance: Number(balance ?? 0).toFixed(2) })}</span>
              {delta != null && <span className="text-red-600">−${delta.toFixed(4)}</span>}
            </p>
          </div>

          {/* Kette → nächster Agent */}
          {view.is_owner && (
            <div className="border-t pt-3">
              <ChainBar view={view} artifactId={artifactId} onChanged={(p) => setView((v) => ({ ...v, ...p }))} />
            </div>
          )}

          {/* Versionen / Verlauf */}
          <div className="border-t pt-3">
            <p className="mb-1 text-xs font-semibold text-gray-600">
              {t("wv.versions", { n: view.versions?.length ?? 0 })}
            </p>
            {(view.versions?.length ?? 0) === 0 ? (
              <p className="text-xs text-gray-400">{t("wv.noVersions")}</p>
            ) : (
              <ul className="max-h-56 space-y-1 overflow-y-auto text-xs">
                {view.versions.map((v) => (
                  <li key={v.id} className="flex items-center gap-2 border-b py-1 last:border-b-0">
                    <span className="shrink-0 font-medium">v{v.version_no}</span>
                    <span className="shrink-0 text-gray-400">
                      {new Date(v.created_at).toLocaleDateString()}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-gray-600" title={v.prompt}>
                      {v.prompt}
                    </span>
                    <button type="button" onClick={() => void viewVersion(v.id)}
                      className="shrink-0 rounded border px-2 py-0.5 hover:bg-muted">{t("wv.view")}</button>
                    <button type="button" onClick={() => void restoreVersion(v.id)}
                      className="shrink-0 rounded border px-2 py-0.5 hover:bg-muted">{t("wv.restore")}</button>
                  </li>
                ))}
              </ul>
            )}
            {previewVersion && (
              <div className="mt-2">
                <div className="mb-1 flex items-center justify-between text-xs text-gray-400">
                  <span>{t("wv.previewV", { n: previewVersion.version_no })}</span>
                  <button type="button" onClick={() => setPreviewVersion(null)} className="hover:text-black">
                    {t("wv.close")}
                  </button>
                </div>
                <iframe
                  title={`Version ${previewVersion.version_no}`}
                  srcDoc={withBaseTarget(previewVersion.content || "")}
                  sandbox={POPUP_SANDBOX}
                  className="h-56 w-full rounded border bg-white"
                />
              </div>
            )}
          </div>
        </div>
  );

  // Template (Popup 2 im Nav-Dropdown): Agent-Template-Bewertung (Sterne +
  // Kommentar-Textfeld). Nur für den Eigentümer mit verknüpftem Agent. Ist sonst
  // null, sodass das Nav den Template-Menüpunkt ausblendet.
  const templateKonfig =
    view.is_owner && view.agent_id ? (
      <div className="space-y-1.5">
        <p className="text-xs font-semibold text-gray-600">{t("wv.rateAgent")}</p>
        <div className="flex items-center" onMouseLeave={() => setHoverStar(0)}>
          {[1, 2, 3, 4, 5].map((s) => (
            <button
              key={s}
              type="button"
              onMouseEnter={() => setHoverStar(s)}
              onClick={() => void submitRating(s)}
              title={t("wv.outOf5", { s })}
              aria-label={t("wv.stars", { s })}
              className={`px-0.5 text-base leading-none ${
                s <= (hoverStar || myStars) ? "text-amber-500" : "text-gray-300"
              }`}
            >
              ★
            </button>
          ))}
          {ratingSaved && <span className="ml-2 text-xs text-green-600">{t("wv.saved")}</span>}
        </div>
        <textarea
          value={ratingComment}
          onChange={(e) => setRatingComment(e.target.value)}
          placeholder={t("wv.commentOptional")}
          rows={2}
          className="w-full rounded border px-1.5 py-1 text-xs"
        />
      </div>
    ) : null;

  // Beide Konfig-Knoten bei jedem Render frisch in den Store schieben (bewusst ohne
  // Dependency-Array → die Event-Handler schließen über aktuelle Work-View-States).
  useEffect(() => {
    instanceConfigStore.set({
      instanz: instanzKonfig,
      template: templateKonfig,
      externalUrl: view.external_url || null
    });
  });
  // Beim Verlassen der Instanz das Nav-Dropdown leeren.
  useEffect(() => () => instanceConfigStore.set(null), []);

  const chatCol = (
    /* LINKS: Chat */
    <div className={chatColClass}>
        {balance != null && balance <= 0 && (
          <div className="m-3 rounded border border-amber-300 bg-amber-50 p-2 text-sm">
            {t("wv.balanceUsedUp")}{" "}
            <a href="/profile" className="underline">
              {t("wv.topUpNow")}
            </a>
            {t("wv.toContinue")}
          </div>
        )}

        <div className={msgListClass}>
          {messages.map((m) => {
            const parsed =
              m.role === "assistant" ? splitChips(m.content) : { text: m.content, chips: [] };
            return (
            <div
              key={m.id}
              className={`flex items-end gap-2 ${
                m.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              {m.role === "assistant" && (
                <AgentAvatar avatarUrl={view.image_url} name={view.title} size={28} />
              )}
              <div className="flex max-w-[80%] flex-col items-start">
                <div
                  className={`whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm leading-snug ${
                    m.role === "user" ? "bg-black text-white" : "bg-muted"
                  }`}
                >
                  {m.role === "assistant" ? parsed.text.replace(/\n{2,}/g, "\n") : parsed.text}
                  {m.version_no != null && (
                    <div
                      className={`mt-1 text-xs ${
                        m.role === "user" ? "text-gray-300" : "text-green-700"
                      }`}
                    >
                      {t("wv.pageUpdated", { n: m.version_no })}
                    </div>
                  )}
                </div>
                {m.role === "assistant" && m.id === lastAssistantId && parsed.chips.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {parsed.chips.map((c, i) => (
                      <button key={i} type="button" disabled={busy} onClick={() => void sendMessage(c)}
                        className="rounded-full border border-black bg-white px-3 py-1 text-xs text-black hover:bg-gray-100 disabled:opacity-50">
                        {c}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
            );
          })}
          {busy && (
            <div className="flex items-end gap-2">
              <AgentAvatar avatarUrl={view.image_url} name={view.title} size={28} />
              <div className="rounded-2xl bg-muted px-3 py-2 text-sm text-gray-500">
                {t("wv.agentThinking")}
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {error && <p className="px-3 text-sm text-red-600">{error}</p>}

        {sectionsOpen && (
          <div className="mx-3 mb-2 rounded-lg border bg-white p-3 text-sm">
            <div className="mb-2 flex items-center justify-between">
              <span className="font-semibold">{t("wv.tabs")}</span>
              <button
                type="button"
                onClick={() => setSectionsOpen(false)}
                className="text-gray-500 hover:text-black"
                aria-label={t("wv.closeTabs")}
              >
                ×
              </button>
            </div>
            {sectionsError ? (
              <p className="text-xs text-gray-400">{sectionsError}</p>
            ) : !sections ? (
              <p className="text-xs text-gray-400">{t("wv.loading")}</p>
            ) : (
              <>
                <div className="mb-3 flex items-center gap-2 text-xs">
                  <span className="text-gray-500">{t("wv.layout")}</span>
                  {(["sections", "tabs"] as const).map((l) => (
                    <button
                      key={l}
                      type="button"
                      onClick={() => void setSectionsLayout(l)}
                      className={`rounded border border-black px-2 py-0.5 ${
                        sections.layout === l ? "bg-black text-white" : "bg-white text-black hover:bg-gray-100"
                      }`}
                    >
                      {l === "sections" ? t("wv.sections") : t("wv.tabs")}
                    </button>
                  ))}
                </div>
                {sections.slots.length === 0 ? (
                  <p className="text-xs text-gray-400">
                    {t("wv.noTabsHint")}
                  </p>
                ) : (
                  <ul className="max-h-64 space-y-2 overflow-y-auto">
                    {[...sections.slots]
                      .sort((a, b) => (a.order || 0) - (b.order || 0))
                      .map((s, idx, arr) => (
                        <li key={s.id} className="flex items-center gap-1.5">
                          <input
                            value={sectionTitles[s.id] ?? ""}
                            onChange={(e) =>
                              setSectionTitles((t) => ({ ...t, [s.id]: e.target.value }))
                            }
                            className="min-w-0 flex-1 rounded border px-2 py-1 text-xs"
                          />
                          <button
                            type="button"
                            onClick={() => void renameSection(s.id)}
                            disabled={(sectionTitles[s.id] ?? "") === s.title}
                            className="shrink-0 rounded border border-black px-2 py-1 text-xs hover:bg-gray-100 disabled:opacity-40"
                          >
                            {t("wv.save")}
                          </button>
                          <button
                            type="button"
                            onClick={() => void moveSection(s.id, -1)}
                            disabled={idx === 0}
                            aria-label={t("wv.moveUp")}
                            className="shrink-0 rounded border border-black px-2 py-1 text-xs hover:bg-gray-100 disabled:opacity-40"
                          >
                            ↑
                          </button>
                          <button
                            type="button"
                            onClick={() => void moveSection(s.id, 1)}
                            disabled={idx === arr.length - 1}
                            aria-label={t("wv.moveDown")}
                            className="shrink-0 rounded border border-black px-2 py-1 text-xs hover:bg-gray-100 disabled:opacity-40"
                          >
                            ↓
                          </button>
                          <button
                            type="button"
                            onClick={() => void deleteSection(s.id)}
                            className="shrink-0 rounded border border-black px-2 py-1 text-xs text-red-600 hover:bg-gray-100"
                          >
                            {t("wv.delete")}
                          </button>
                        </li>
                      ))}
                  </ul>
                )}
              </>
            )}
          </div>
        )}

        {view.output_mode && view.output_mode !== "ueberschreiben" && (
          <div className="px-3 pb-1">
            <span className="inline-flex items-center gap-1 rounded-full border border-black bg-white px-3 py-1 text-xs text-black">
              {t("wv.mode", { label: commands?.find((c) => c.key === view.output_mode)?.label ?? view.output_mode })}
              <button
                type="button"
                onClick={() => void applyMode("ueberschreiben")}
                className="text-gray-500 hover:text-red-600"
                aria-label={t("wv.resetMode")}
              >
                ✕
              </button>
            </span>
          </div>
        )}

        <div className="border-t p-3">
          {pending.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-1">
              {pending.map((f) => (
                <span
                  key={f.id}
                  className="inline-flex items-center gap-1 rounded bg-muted px-2 py-0.5 text-xs"
                >
                  📎 {f.filename}
                  <button
                    type="button"
                    onClick={() => deleteFile(f.id)}
                    className="text-gray-500 hover:text-red-600"
                    aria-label={t("wv.removeAttachment")}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
          <form onSubmit={submit} className="flex gap-2">
            <input
              ref={fileRef}
              type="file"
              multiple
              hidden
              onChange={onPickFiles}
              accept="image/*,.pdf,.txt,.md,.csv,.doc,.docx"
            />
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={busy}
              title={t("wv.attachFile")}
              className="rounded border px-3 py-2 text-sm disabled:opacity-50"
            >
              📎
            </button>
            <div className="relative" ref={menuRef}>
              <button
                type="button"
                onClick={() => void toggleMenu()}
                disabled={busy}
                title={t("wv.commands")}
                className="rounded border px-3 py-2 text-sm disabled:opacity-50"
              >
                /
              </button>
              {menuOpen && (
                <div className="absolute bottom-11 left-0 z-20 max-h-64 w-56 overflow-y-auto rounded-lg border bg-white shadow-lg">
                  {/* Benannten neuen Tab anlegen (Name eingeben → leerer Tab, nächster Lauf füllt ihn). */}
                  {newTabName === null ? (
                    <button
                      type="button"
                      onClick={() => setNewTabName("")}
                      className="flex w-full items-center gap-2 border-b px-3 py-2 text-left text-sm font-medium hover:bg-muted"
                    >
                      {t("wv.newNamedTab")}
                    </button>
                  ) : (
                    <div className="flex items-center gap-1 border-b p-2">
                      <input
                        autoFocus
                        value={newTabName}
                        onChange={(e) => setNewTabName(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") void createNamedTab(newTabName);
                          if (e.key === "Escape") setNewTabName(null);
                        }}
                        placeholder={t("wv.tabNamePlaceholder")}
                        className="min-w-0 flex-1 rounded border px-2 py-1 text-sm"
                      />
                      <button
                        type="button"
                        onClick={() => void createNamedTab(newTabName)}
                        className="shrink-0 rounded bg-black px-2 py-1 text-xs text-white"
                      >
                        {t("wv.ok")}
                      </button>
                    </div>
                  )}
                  {(commands ?? []).length === 0 ? (
                    <p className="px-3 py-2 text-xs text-gray-400">{t("wv.noCommands")}</p>
                  ) : (
                    <>
                      {/* System-Befehle (mode/action) wie bisher. */}
                      {(commands ?? [])
                        .filter((c) => c.kind !== "template")
                        .map((c) => (
                          <button
                            key={`${c.kind}:${c.key}`}
                            type="button"
                            onClick={() => void runCommand(c)}
                            className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-muted"
                          >
                            <span>{c.label}</span>
                            <span className="text-xs text-gray-400">{c.kind === "mode" ? t("wv.modeLabel") : t("wv.actionLabel")}</span>
                          </button>
                        ))}
                      {/* Template-eigene Funktionen unter eigener Überschrift „Vorlage". */}
                      {(commands ?? []).some((c) => c.kind === "template") && (
                        <>
                          <p className="border-t px-3 pb-1 pt-2 text-xs font-medium uppercase tracking-wide text-gray-400">
                            {t("wv.templateHeading")}
                          </p>
                          {(commands ?? [])
                            .filter((c) => c.kind === "template")
                            .map((c) =>
                              cmdInput?.cmd.key === c.key ? (
                                <div key={`template:${c.key}`} className="flex items-center gap-1 p-2">
                                  <input
                                    autoFocus
                                    value={cmdInput.value}
                                    onChange={(e) => setCmdInput({ cmd: c, value: e.target.value })}
                                    onKeyDown={(e) => {
                                      if (e.key === "Enter") void runTemplateCommand(c, cmdInput.value);
                                      if (e.key === "Escape") setCmdInput(null);
                                    }}
                                    placeholder={t("wv.inputPlaceholder")}
                                    className="min-w-0 flex-1 rounded border px-2 py-1 text-sm"
                                  />
                                  <button
                                    type="button"
                                    onClick={() => void runTemplateCommand(c, cmdInput.value)}
                                    className="shrink-0 rounded bg-black px-2 py-1 text-xs text-white"
                                  >
                                    {t("wv.ok")}
                                  </button>
                                </div>
                              ) : (
                                <button
                                  key={`template:${c.key}`}
                                  type="button"
                                  onClick={() => void runCommand(c)}
                                  className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-muted"
                                >
                                  <span>{c.label}</span>
                                  <span className="text-xs text-gray-400">/{c.key}</span>
                                </button>
                              )
                            )}
                        </>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
            <input
              className="flex-1 rounded border px-3 py-2 text-sm"
              placeholder={t("wv.chatPlaceholder")}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={busy}
            />
            <button
              type="submit"
              disabled={busy}
              className="rounded bg-black px-4 py-2 text-sm text-white disabled:opacity-50"
            >
              {t("wv.send")}
            </button>
          </form>
        </div>
    </div>
  );

  const rightCol = (
    /* RECHTS: Canvas (Ergebnis) */
    <div className={rightColClass}>
        <div className="mb-1 flex items-center justify-between px-1 text-xs text-gray-400">
          <span>{hasCanvas || isSlots ? (view.current_version_no ? t("wv.resultV", { n: view.current_version_no }) : t("wv.resultPlain")) : t("wv.noPage")}</span>
          {(canPublish || isSlots) && (
            <span className="flex items-center gap-2">
              {canPublish && (
                <button type="button"
                  onClick={() => setRightView(rightView === "connection" ? "result" : "connection")}
                  className="rounded border px-2 py-0.5 hover:bg-muted">
                  {rightView === "connection" ? t("wv.result") : t("wv.connection")}
                </button>
              )}
              {rightView === "result" && hasSftp && (
                <button type="button" onClick={publishNow} className="rounded bg-black px-2 py-0.5 text-white">
                  {t("wv.publish")}
                </button>
              )}
            </span>
          )}
        </div>
        {connStatus && <p className="px-1 pb-1 text-xs text-gray-600">{connStatus}</p>}
        {rightView === "connection" ? (
          <div className="flex-1 space-y-4 overflow-y-auto rounded border bg-white p-3 text-sm">
            {kinds.map((kind) => {
              const meta = CONNECTION_KINDS[kind];
              if (!meta) return null;
              if (meta.auth === "oauth") {
                const cfg = connConfigs[kind] || {};
                const connected = Boolean(cfg.connected);
                return (
                  <div key={kind} className="space-y-2 border-b pb-3 last:border-b-0">
                    <p className="font-semibold">{meta.name}</p>
                    {connected ? (
                      <p className="text-green-600">
                        {t("wv.connectedAs", { who: cfg.email || meta.name })}
                      </p>
                    ) : (
                      <a
                        href={`/oauth/google/start?artifact_id=${artifactId}&kind=${kind}`}
                        className="inline-block rounded bg-black px-3 py-1.5 text-white"
                      >
                        {t("wv.connectGoogle")}
                      </a>
                    )}
                  </div>
                );
              }
              return (
                <div key={kind} className="space-y-2 border-b pb-3 last:border-b-0">
                  <p className="font-semibold">{meta.name}</p>
                  {(meta.fields ?? []).map((f) => (
                    <input key={f.key} className="w-full rounded border px-2 py-1" type={f.type}
                      placeholder={f.label}
                      value={connConfigs[kind]?.[f.key] ?? ""}
                      onChange={(e) => setConnConfigs((c) => ({ ...c, [kind]: { ...(c[kind] || {}), [f.key]: e.target.value } }))} />
                  ))}
                  <input className="w-full rounded border px-2 py-1" type="password"
                    placeholder={t("wv.secretUnchanged", { label: meta.secretLabel ?? "" })}
                    value={connSecrets[kind] ?? ""}
                    onChange={(e) => setConnSecrets((s) => ({ ...s, [kind]: e.target.value }))} />
                  <button type="button" onClick={() => saveConn(kind)} className="rounded bg-black px-3 py-1.5 text-white">
                    {t("wv.saveNamed", { name: meta.name })}
                  </button>
                </div>
              );
            })}
            {mcpCreds.map((m) => (
              <div key={`mcp:${m.server_id}`} className="space-y-2 border-b pb-3 last:border-b-0">
                <p className="font-semibold">
                  {m.name}
                  {m.configured && <span className="text-green-600"> ✓ {t("wv.stored")}</span>}
                </p>
                <input className="w-full rounded border px-2 py-1" type="password"
                  placeholder={m.configured ? t("wv.mcpSecretUnchanged", { label: m.secret_label }) : m.secret_label}
                  value={connSecrets[`mcp:${m.server_id}`] ?? ""}
                  onChange={(e) => setConnSecrets((s) => ({ ...s, [`mcp:${m.server_id}`]: e.target.value }))} />
                <button type="button" onClick={() => saveConn(`mcp:${m.server_id}`)}
                  className="rounded bg-black px-3 py-1.5 text-white">
                  {t("wv.saveNamed", { name: m.name })}
                </button>
              </div>
            ))}
          </div>
        ) : isSlots ? (
          // Slots-Instanz: isolierter petite-vue-Renderer im gewaehlten Design
          // (sandbox="allow-scripts", KEIN allow-same-origin). srcDoc ist memoiziert
          // (nur Design/CSS), Slot-Daten kommen via postMessage — kein Reload beim Edit.
          <iframe ref={slotIframeRef} title={t("wv.resultPlain")} sandbox={`allow-scripts ${POPUP_SANDBOX}`}
            srcDoc={slotSrcDoc}
            className="h-full w-full rounded border bg-white" />
        ) : view.external_url ? (
          // Geteilt: oben vorbereiteter Beitrag (Canvas), unten die externe Seite live.
          <div className="flex h-full flex-col gap-2">
            <div className="flex min-h-0 flex-1 flex-col">
              <span className="px-1 text-xs text-gray-400">{t("wv.preparedPost")}</span>
              <iframe title={t("wv.preparedPost")}
                srcDoc={withBaseTarget(view.current_content || `<p style='font-family:sans-serif;color:#888;padding:1rem'>${t("wv.noContentChat")}</p>`)}
                className="w-full flex-1 rounded border bg-white" sandbox={resultSandbox} />
            </div>
            <div className="flex min-h-0 flex-1 flex-col">
              <span className="flex items-center justify-between px-1 text-xs text-gray-400">
                {t("wv.externalPage")}
                <a href={view.external_url} target="_blank" rel="noreferrer" className="underline">
                  {t("wv.openInNewTab")}
                </a>
              </span>
              <iframe title={t("wv.externalPage")} src={view.external_url}
                className="w-full flex-1 rounded border bg-white" />
            </div>
          </div>
        ) : (
          <iframe title={t("wv.resultPlain")}
            srcDoc={withBaseTarget(view.current_content || `<p style='font-family:sans-serif;color:#888;padding:1rem'>${t("wv.noContentChatPage")}</p>`)}
            className="h-full w-full rounded border bg-white" sandbox={resultSandbox} />
        )}
        {files.length > 0 && (
          <div className="relative mt-2 border-t pt-2">
            <button
              type="button"
              onClick={() => setShowFiles((s) => !s)}
              className="flex items-center gap-1 rounded border px-2 py-1 text-xs text-gray-600 hover:bg-muted"
            >
              📎 {t("wv.files", { n: files.length })}
            </button>
            {showFiles && (
              <div className="absolute bottom-9 left-0 z-10 max-h-72 w-80 overflow-y-auto rounded-lg border bg-white p-2 shadow-lg">
                <div className="mb-2 flex gap-1 text-xs">
                  {([
                    ["all", t("wv.filterAll")],
                    ["image", t("wv.filterImages")],
                    ["doc", t("wv.filterDocs")]
                  ] as const).map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setFileFilter(key)}
                      className={`rounded px-2 py-0.5 ${
                        fileFilter === key ? "bg-black text-white" : "bg-muted text-gray-600"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                {(() => {
                  const shown = files.filter((f) =>
                    fileFilter === "all"
                      ? true
                      : fileFilter === "image"
                        ? f.content_type.startsWith("image/")
                        : !f.content_type.startsWith("image/")
                  );
                  if (shown.length === 0) {
                    return (
                      <p className="px-1 py-2 text-xs text-gray-400">
                        {fileFilter === "image" ? t("wv.noImages") : t("wv.noDocs")}
                      </p>
                    );
                  }
                  return (
                    <ul className="space-y-1">
                      {shown.map((f) => (
                        <li key={f.id} className="flex items-center gap-2 text-xs">
                          {f.content_type.startsWith("image/") ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                              src={f.url}
                              alt={f.filename}
                              className="h-8 w-8 shrink-0 rounded object-cover"
                            />
                          ) : (
                            <span className="grid h-8 w-8 shrink-0 place-items-center rounded bg-muted">
                              📄
                            </span>
                          )}
                          <span className="min-w-0 flex-1 truncate" title={f.filename}>
                            {f.filename}
                          </span>
                          <span className="shrink-0 text-gray-400">{humanSize(f.size)}</span>
                          <button
                            type="button"
                            onClick={() => deleteFile(f.id)}
                            className="shrink-0 text-gray-400 hover:text-red-600"
                            aria-label={t("wv.deleteFile")}
                          >
                            ×
                          </button>
                        </li>
                      ))}
                    </ul>
                  );
                })()}
              </div>
            )}
          </div>
        )}
    </div>
  );

  return (
    <div className="flex flex-col gap-3">
      {/* Einstellungen (inkl. Layout-Umschalter) sind ins Nav-Dropdown
          „Agent-UI-Einstellungen" gewandert (Store: instanceConfigStore). */}
      {layout === "stacked" ? (
        <div className="flex flex-col">
          {chatCol}
          {/* Dicke Trennlinie zwischen Chat und Ergebnis (klebt direkt darunter). */}
          <div className="my-1 h-1 shrink-0 rounded bg-gray-700" />
          {rightCol}
        </div>
      ) : (
        <>
          {mobileTabBar}
          {/* "side": ab lg ziehbarer Splitter zwischen Chat und Ergebnis (flex-basis %),
              darunter (Mobil) bleibt es einspaltig via Tab-Logik in den Spaltenklassen. */}
          <div
            className="flex flex-col gap-4 lg:flex-row lg:gap-0"
            style={
              {
                "--chat-basis": `${splitPct}%`,
                "--right-basis": `${100 - splitPct}%`
              } as React.CSSProperties
            }
          >
            <div className="min-w-0 basis-auto lg:basis-[var(--chat-basis)] lg:pr-2">
              {chatCol}
            </div>
            <div
              ref={splitDragRef}
              onMouseDown={onSplitStart}
              role="separator"
              aria-orientation="vertical"
              title={t("wv.dragSplit")}
              className="hidden w-2 shrink-0 cursor-col-resize items-center justify-center lg:flex"
            >
              <span className="h-12 w-1 rounded bg-gray-300 transition-colors hover:bg-gray-500" />
            </div>
            <div className="min-w-0 basis-auto lg:basis-[var(--right-basis)] lg:pl-2">
              {rightCol}
            </div>
          </div>
        </>
      )}

      {/* Geplante Aufgaben dieser Instanz — unter der View. */}
      {(view.jobs?.length ?? 0) > 0 && <JobsList jobs={view.jobs} />}
    </div>
  );
}
