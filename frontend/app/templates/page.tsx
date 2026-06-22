import Link from "next/link";
import { api, type Template } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function TemplatesPage({
  searchParams
}: {
  searchParams: { category?: string };
}) {
  let templates: Template[] = [];
  try {
    templates = await api.templates.list({ category: searchParams.category });
  } catch {}

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Template-Marktplatz</h1>
        <Link
          href="/templates/create"
          className="rounded bg-black px-3 py-2 text-sm text-white"
        >
          Template erstellen
        </Link>
      </div>
      {templates.length === 0 ? (
        <p className="text-gray-500">Noch keine Templates vorhanden.</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {templates.map((t) => (
            <Link
              key={t.id}
              href={`/templates/${t.id}`}
              className="rounded-lg border p-4 transition hover:shadow"
            >
              <div className="mb-1 text-xs uppercase text-gray-400">{t.category || "allgemein"}</div>
              <div className="font-semibold">{t.title}</div>
              <p className="mt-1 line-clamp-2 text-sm text-gray-600">{t.description}</p>
              <div className="mt-2 text-xs text-gray-400">Output: {t.output_type}</div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
