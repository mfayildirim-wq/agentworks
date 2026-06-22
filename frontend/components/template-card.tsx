"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Play } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { AgentAvatar } from "@/components/agent-avatar";
import type { PublicTemplate } from "@/lib/api";
import { monogram, resolveAvatar } from "@/lib/icons";
import { useI18n } from "@/lib/i18n/provider";
import { categoryLabel } from "@/lib/i18n/dict";

/**
 * Kompakte Karte für die öffentliche Startseite: oben ein Bild, das ~40 % der Box
 * füllt, darunter (60 %) Titel, Kurzbeschreibung, Stichwörter und unten Modell + Preis.
 */
export function TemplateCard({ template }: { template: PublicTemplate }) {
  const { lang } = useI18n();
  const router = useRouter();
  const isEmoji = !!template.image_url?.startsWith("emoji:");
  // Avatar-Presets (preset:…) und hochgeladene Bilder (/media/…) zu einer src auflösen.
  const imgSrc = isEmoji ? null : resolveAvatar(template.image_url);
  return (
    <Link href={`/templates/${template.id}`} className="group mx-auto block h-full w-full max-w-[190px]">
      <article className="flex h-full min-h-96 flex-col overflow-hidden rounded-xl border bg-card transition hover:border-primary hover:shadow-md">
        {/* Bild oben: feste Höhe, damit der Inhalt darunter (auch 2-zeilig) genug Platz behält */}
        <div className="flex h-44 shrink-0 items-center justify-center overflow-hidden bg-muted">
          {isEmoji ? (
            <span className="text-5xl">{template.image_url!.slice("emoji:".length)}</span>
          ) : imgSrc ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={imgSrc}
              alt={template.title}
              className="h-full w-full object-cover transition group-hover:scale-[1.03]"
            />
          ) : (
            <span
              className="flex h-full w-full items-center justify-center text-5xl font-semibold text-white"
              style={{ backgroundColor: monogram(template.title).color }}
            >
              {monogram(template.title).letter}
            </span>
          )}
        </div>

        {/* Inhalt: restliche ~60 % */}
        <div className="flex flex-1 flex-col gap-1.5 p-3">
          <h3 className="line-clamp-2 text-center text-base font-semibold leading-tight">
            {template.title}
          </h3>
          {template.description && (
            <p className="line-clamp-2 text-center text-xs text-muted-foreground">
              {template.description}
            </p>
          )}

          {template.category && (
            <div className="flex flex-wrap justify-center gap-1">
              {template.category
                .split(/[,\s]+/)
                .filter(Boolean)
                .slice(0, 3)
                .map((kw) => (
                  <Badge key={kw}>{categoryLabel(lang, kw)}</Badge>
                ))}
            </div>
          )}

          {/* „Let's Work" — sieht aus wie ein Knopf (Karte selbst ist der Link). */}
          <div className="mt-auto flex items-center justify-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition group-hover:opacity-90">
            <Play size={13} className="fill-current" /> Let&apos;s Work
          </div>

          {/* Unten: Instanz-Anzahl / Bewertung links, Creator (Bild+Name, klickbar) rechts */}
          <div className="flex items-center justify-between gap-1 border-t pt-2 text-xs text-muted-foreground">
            <span className="shrink-0">
              {template.works_count ?? 0}
              <span className="mx-1">/</span>
              <span className="text-amber-500">★ {Number(template.avg_stars ?? 0).toFixed(1)}</span>
            </span>
            {template.creator_id && (
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  router.push(`/u/${template.creator_id}`);
                }}
                title={template.creator_name || "Creator"}
                className="flex min-w-0 items-center gap-1 hover:text-foreground"
              >
                <AgentAvatar avatarUrl={template.creator_avatar ?? null} name={template.creator_name || "?"} size={16} />
                <span className="max-w-[8ch] truncate">{(template.creator_name || "").slice(0, 8)}</span>
              </button>
            )}
          </div>
        </div>
      </article>
    </Link>
  );
}
