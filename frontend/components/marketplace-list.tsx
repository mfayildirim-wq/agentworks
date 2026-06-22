"use client";
import { useEffect, useState } from "react";
import { TemplateCard } from "@/components/template-card";
import { MyAgentsPanel } from "@/components/my-agents-panel";
import { CATEGORIES } from "@/lib/categories";
import { useI18n } from "@/lib/i18n/provider";
import { categoryLabel } from "@/lib/i18n/dict";
import type { PublicTemplate } from "@/lib/api";

const MINE = "Meine Agenten";

export function MarketplaceList({
  templates,
  loggedIn = false
}: {
  templates: PublicTemplate[];
  loggedIn?: boolean;
}) {
  const { t, lang } = useI18n();
  const [cat, setCat] = useState<string>("Beliebte");
  const [searchResults, setSearchResults] = useState<PublicTemplate[] | null>(null);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);

  // Deeplink `?f=mine` (Nav „Meine Agenten") hat Vorrang; sonst zuletzt gewählter Filter.
  useEffect(() => {
    const fromUrl = new URLSearchParams(window.location.search).get("f");
    if (fromUrl === "mine" && loggedIn) {
      setCat(MINE);
      window.localStorage.setItem("aw_marktplatz_filter", MINE);
      return;
    }
    const saved = window.localStorage.getItem("aw_marktplatz_filter");
    if (saved && (saved !== MINE || loggedIn)) setCat(saved);
  }, [loggedIn]);

  function choose(c: string) {
    setCat(c);
    setSearchResults(null);
    window.localStorage.setItem("aw_marktplatz_filter", c);
  }

  async function runSearch() {
    const term = q.trim();
    if (!term) {
      setSearchResults(null);
      return;
    }
    const res = await fetch(
      `/api/proxy/templates/public?q=${encodeURIComponent(term)}&sort=popular`,
      { cache: "no-store" }
    );
    setSearchResults((await res.json()) as PublicTemplate[]);
  }

  function resetSearch() {
    setSearchResults(null);
    setQ("");
    setOpen(false);
  }

  const shown =
    searchResults ??
    (cat === "Beliebte" || cat === "Alle"
      ? templates
      : templates.filter((t) => t.category === cat));

  // Filter-Leiste: Meine Agenten (bei Login) zuerst, dann Beliebte/Alle/Kategorien.
  const tabs = [...(loggedIn ? [MINE] : []), "Beliebte", "Alle", ...CATEGORIES];

  // Anzeige-Label der drei Sondertabs übersetzen; Kategorienamen bleiben unverändert.
  const tabLabel = (c: string) =>
    c === MINE ? t("market.myAgents") : c === "Beliebte" ? t("market.popular") : c === "Alle" ? t("market.all") : categoryLabel(lang, c);

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        {tabs.map((c) => (
          <button key={c} type="button" onClick={() => choose(c)}
            className={`rounded-full px-3 py-1 text-sm transition ${cat === c ? "bg-primary text-primary-foreground" : "border hover:bg-muted"}`}>
            {tabLabel(c)}
          </button>
        ))}
        <button type="button" onClick={() => setOpen((o) => !o)}
          className={`ml-auto rounded-full px-3 py-1 text-sm transition ${open ? "bg-primary text-primary-foreground" : "border hover:bg-muted"}`}>
          🔍 {t("market.searchBtn")}
        </button>
      </div>

      {open && (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runSearch()}
            placeholder={t("market.searchPlaceholder")}
            className="min-w-0 flex-1 rounded-md border px-3 py-1 text-sm"
          />
          <button type="button" onClick={runSearch}
            className="rounded-md bg-primary px-3 py-1 text-sm text-primary-foreground transition hover:opacity-90">
            {t("market.searchSubmit")}
          </button>
        </div>
      )}

      {cat === MINE ? (
        <MyAgentsPanel />
      ) : (
        <>
          {/* Anzahl unter der Filter-Leiste */}
          <p className="mb-3 text-xs text-muted-foreground">
            {searchResults !== null ? (
              <>
                {t("market.searchResult", { q, n: shown.length })}{" "}
                <button type="button" onClick={resetSearch} className="underline hover:text-foreground">
                  {t("market.reset")}
                </button>
              </>
            ) : (
              t("market.templatesCount", { n: shown.length })
            )}
          </p>
          {shown.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {searchResults !== null
                ? t("market.noneFound", { q })
                : cat === "Beliebte" || cat === "Alle"
                  ? t("market.empty")
                  : t("market.noneInCat", { cat })}
            </p>
          ) : (
            <div className="grid grid-cols-2 items-stretch gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
              {shown.map((t) => (<TemplateCard key={t.id} template={t} />))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
