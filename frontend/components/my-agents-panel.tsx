"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { ArtifactListItem, Template } from "@/lib/api";
import { TemplateCard } from "@/components/template-card";
import { TemplateEditButton } from "@/components/template-edit-button";
import { TemplatePublishControl } from "@/components/template-publish-control";
import { useI18n } from "@/lib/i18n/provider";

/**
 * „Meine Agenten"-Filter-Inhalt: KPIs (aktive Instanzen, geplant) + eigene Vorlagen
 * mit Löschen/Veröffentlichen. Ersetzt die frühere /dashboard-Seite.
 */
export function MyAgentsPanel() {
  const { t } = useI18n();
  const [instances, setInstances] = useState<ArtifactListItem[] | null>(null);
  const [templates, setTemplates] = useState<Template[] | null>(null);

  useEffect(() => {
    void (async () => {
      const [iR, tR] = await Promise.all([
        fetch("/api/proxy/artifacts", { cache: "no-store" }),
        fetch("/api/proxy/templates?mine=true", { cache: "no-store" })
      ]);
      setInstances(iR.ok ? await iR.json() : []);
      setTemplates(tR.ok ? await tR.json() : []);
    })();
  }, []);

  const loading = instances === null || templates === null;
  const scheduled = (instances ?? []).filter((a) => a.schedule_cadence).length;

  return (
    <div className="space-y-4">
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground">
        <span><b className="text-foreground">{templates?.length ?? 0}</b> {t("my.templates")}</span>
        <span>·</span>
        <span><b className="text-foreground">{instances?.length ?? 0}</b> {t("my.activeInstances")}</span>
        <span>·</span>
        <span><b className="text-foreground">{scheduled}</b> {t("my.scheduled")}</span>
      </p>

      {loading ? (
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      ) : (templates ?? []).length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {t("my.noTemplates")}{" "}
          <Link className="underline" href="/agent-templates/create">
            {t("my.createTemplate")}
          </Link>
          .
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {(templates ?? []).map((t) => (
            <div key={t.id} className="relative mx-auto w-full max-w-[190px]">
              <TemplateCard
                template={{
                  id: t.id,
                  title: t.title,
                  description: t.description,
                  category: t.category,
                  image_url: t.image_url,
                  output_type: t.output_type,
                  model: t.model ?? null,
                  price: 0
                }}
              />
              <div className="absolute right-2 top-2 z-10">
                <TemplateEditButton templateId={t.id} />
              </div>
              <TemplatePublishControl
                templateId={t.id}
                visibility={t.visibility}
                publishStatus={t.publish_status}
                publishNote={t.publish_note}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

