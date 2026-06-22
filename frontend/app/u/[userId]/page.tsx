import { notFound } from "next/navigation";
import { AgentAvatar } from "@/components/agent-avatar";
import { TemplateCard } from "@/components/template-card";
import type { PublicTemplate } from "@/lib/api";

export const dynamic = "force-dynamic";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

/**
 * Öffentliches Creator-Profil: Name + Avatar des Erstellers und die von ihm
 * erstellten öffentlichen Agent-Vorlagen.
 */
export default async function CreatorProfilePage({ params }: { params: { userId: string } }) {
  let templates: PublicTemplate[] = [];
  try {
    const res = await fetch(
      `${BACKEND}/templates/public?owner=${encodeURIComponent(params.userId)}&sort=popular`,
      { cache: "no-store" }
    );
    if (res.ok) templates = await res.json();
  } catch {
    notFound();
  }

  const name = templates[0]?.creator_name || "Creator";
  const avatar = templates[0]?.creator_avatar ?? null;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <AgentAvatar avatarUrl={avatar} name={name} size={48} />
        <div>
          <h1 className="text-2xl font-bold">{name}</h1>
          <p className="text-sm text-muted-foreground">{templates.length} templates</p>
        </div>
      </div>

      {templates.length === 0 ? (
        <p className="text-sm text-muted-foreground">No public templates.</p>
      ) : (
        <div className="grid grid-cols-2 items-stretch gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {templates.map((t) => (
            <TemplateCard key={t.id} template={t} />
          ))}
        </div>
      )}
    </div>
  );
}
