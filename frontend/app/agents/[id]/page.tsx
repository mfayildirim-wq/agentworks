import Link from "next/link";
import { notFound } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatCost } from "@/lib/utils";
import { AgentAvatar } from "@/components/agent-avatar";
import { RatingsBlock } from "./ratings-block";

export const dynamic = "force-dynamic";

export default async function AgentPage({ params }: { params: { id: string } }) {
  let agent;
  let works;
  try {
    [agent, works] = await Promise.all([
      api.agents.get(params.id),
      api.agents.works(params.id).catch(() => [])
    ]);
  } catch {
    notFound();
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[2fr,1fr]">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-4">
            <AgentAvatar avatarUrl={agent.avatar_url} name={agent.name} size={80} />
            <div>
              <h1 className="text-2xl font-bold">{agent.name}</h1>
              <p className="text-muted-foreground">
                {[agent.role, agent.domain].filter(Boolean).join(" · ") || agent.model}
              </p>
              <div className="mt-2 flex flex-wrap gap-1">
                {agent.skills.map((s) => (
                  <Badge key={s}>{s}</Badge>
                ))}
              </div>
              <Link href={`/agents/${agent.id}/edit`} className="text-sm text-primary underline">
                Bearbeiten
              </Link>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <p>{agent.description || <span className="text-muted-foreground">(keine Beschreibung)</span>}</p>
          <div>
            <h3 className="text-sm font-semibold">System-Prompt</h3>
            <pre className="mt-1 overflow-auto rounded-md bg-muted p-3 text-xs">{agent.system_prompt}</pre>
          </div>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold">Projekte / Works</h2>
            {works.length === 0 ? (
              <p className="text-sm text-muted-foreground">Noch an keinen Works beteiligt.</p>
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {works.map((w) => (
                  <Link
                    key={w.id}
                    href={`/works/${w.id}`}
                    className="flex items-center gap-3 rounded-md border p-3 transition hover:border-primary"
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={w.image_url ?? "/avatars/data.svg"}
                      alt=""
                      width={40}
                      height={40}
                      className="rounded object-cover"
                    />
                    <span className="text-sm font-medium">{w.title}</span>
                  </Link>
                ))}
              </div>
            )}
          </section>
        </CardContent>
      </Card>

      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Modell" value={agent.model} />
            <Row label="Temperatur" value={agent.temperature.toString()} />
            <Row label="Sichtbarkeit" value={agent.visibility} />
            <Row label="Preis / Run" value={formatCost(agent.price_per_run)} />
            <Row
              label="Bewertung"
              value={
                agent.rating_count > 0
                  ? `★ ${agent.rating_avg.toFixed(2)} (${agent.rating_count})`
                  : "noch keine"
              }
            />
          </CardContent>
        </Card>

        <Button asChild className="w-full">
          <Link href={`/works/create?agent=${agent.id}`}>In Work verwenden</Link>
        </Button>

        <RatingsBlock agentId={agent.id} />
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
