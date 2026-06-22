import Link from "next/link";
import { notFound } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatCost } from "@/lib/utils";
import { RunPanel } from "./run-panel";

export const dynamic = "force-dynamic";

export default async function WorkPage({ params }: { params: { id: string } }) {
  let work;
  try {
    work = await api.works.get(params.id);
  } catch {
    notFound();
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[2fr,1fr]">
      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl">{work.title}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p>
              <span className="text-muted-foreground">Ziel: </span>
              {work.goal}
            </p>
            {work.expected_outcome && (
              <p>
                <span className="text-muted-foreground">Erwartetes Ergebnis: </span>
                {work.expected_outcome}
              </p>
            )}
            <p>
              <span className="text-muted-foreground">Initiale Nachricht: </span>
              {work.initial_message}
            </p>
            <div className="flex gap-3 text-xs text-muted-foreground">
              <span>Modus: {work.mode}</span>
              <span>· Max Turns: {work.max_turns}</span>
              <span>· Geschätzte Kosten: {formatCost(work.estimated_cost_usd)}</span>
            </div>
          </CardContent>
        </Card>

        <RunPanel workId={work.id} initialMode={work.mode} />
      </div>

      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Agenten ({work.agents.length})</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {work.agents.map((wa) => (
              <Link
                key={wa.agent_id}
                href={`/agents/${wa.agent_id}`}
                className="block rounded border p-2 hover:border-primary"
              >
                <div className="font-medium">{wa.name}</div>
                <div className="text-xs text-muted-foreground">
                  {wa.model}
                  {wa.role_in_work ? ` · ${wa.role_in_work}` : ""}
                </div>
              </Link>
            ))}
          </CardContent>
        </Card>

        <div className="flex flex-col gap-2">
          <Button asChild variant="outline">
            <Link href={`/workflows/${work.id}`}>Workflow-Editor</Link>
          </Button>
          <form action={`/api/proxy/works/${work.id}/copy`} method="post">
            <Button variant="outline" className="w-full" type="submit">
              Work kopieren
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
