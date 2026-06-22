import Link from "next/link";
import { notFound } from "next/navigation";
import { api, type Template, type ArtifactListItem } from "@/lib/api";
import { getT, getLang } from "@/lib/i18n/server";
import { categoryLabel } from "@/lib/i18n/dict";
import { UseTemplateForm } from "./use-form";
import { Reviews } from "./reviews";

export const dynamic = "force-dynamic";

export default async function TemplateDetailPage({ params }: { params: { id: string } }) {
  const t = getT();
  let template: Template;
  try {
    template = await api.templates.get(params.id);
  } catch {
    notFound();
  }

  let instances: ArtifactListItem[] = [];
  try {
    const mine = await api.artifacts.mine();
    instances = mine.filter((a) => a.template_id === params.id);
  } catch {}

  const primaryAgentId = template.config?.agent_ids?.[0];

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-1 text-xs uppercase text-gray-400">{template.category ? categoryLabel(getLang(), template.category) : "—"}</div>
      <h1 className="text-2xl font-bold">{template.title}</h1>

      {/* 1. Meine Instanzen zu dieser Vorlage: schwarzer Rahmen, weiß, grünes Status-Icon. */}
      {instances.length > 0 && (
        <div className="mt-6">
          <h2 className="mb-2 font-semibold">{t("tpl.yourInstances")}</h2>
          <div className="flex flex-wrap gap-2">
            {instances.map((a) => (
              <Link
                key={a.id}
                href={`/artifacts/${a.id}`}
                title={a.title}
                className="flex items-center gap-2 rounded-lg border border-black bg-white p-2 text-sm transition hover:shadow"
              >
                <span
                  className={`h-2.5 w-2.5 shrink-0 rounded-full ${
                    a.current_version_no ? "bg-green-500" : "bg-amber-400"
                  }`}
                  title={a.current_version_no ? t("tpl.ready") : t("tpl.running")}
                />
                <span className="max-w-[12rem] truncate font-medium text-gray-900">{a.title}</span>
                {a.schedule_cadence && <span className="text-xs text-blue-600">⏱</span>}
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* 2. Neue Instanz starten. */}
      <div className="mt-6 rounded-lg border p-4">
        <h2 className="mb-3 font-semibold">{t("tpl.newInstance")}</h2>
        <UseTemplateForm template={template} />
      </div>

      {/* 3. Agent-Beschreibung. */}
      {template.description && (
        <div className="mt-6">
          <h2 className="mb-1 font-semibold">{t("tpl.description")}</h2>
          <p className="text-gray-600">{template.description}</p>
        </div>
      )}

      {/* Sterne-Zeile direkt oberhalb der Bewertungen. */}
      <div className="mt-6 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-gray-500">
        <span className="text-amber-500">
          ★ <span className="text-gray-700">{template.avg_stars?.toFixed(1) ?? "0.0"}</span>{" "}
          <span className="text-gray-400">({template.ratings_count ?? 0})</span>
        </span>
        <span>{template.works_count ?? 0} {t("tpl.works")}</span>
        {template.model && <span>{template.model}</span>}
      </div>

      {/* 4. Kommentare/Bewertungen. */}
      {primaryAgentId && <Reviews agentId={String(primaryAgentId)} />}
    </div>
  );
}
