import { notFound } from "next/navigation";
import { LoginGate } from "@/components/login-gate";
import { api } from "@/lib/api";
import { WorkflowEditor } from "./editor";

export const dynamic = "force-dynamic";

export default async function WorkflowEditorPage({ params }: { params: { id: string } }) {
  let work, graph;
  try {
    [work, graph] = await Promise.all([api.works.get(params.id), api.workflow.get(params.id)]);
  } catch {
    notFound();
  }
  return (
    <LoginGate>
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Workflow: {work.title}</h1>
        <WorkflowEditor
          workId={params.id}
          agents={work.agents.map((a) => ({ id: a.agent_id, name: a.name }))}
          initialNodes={graph.nodes}
          initialEdges={graph.edges}
        />
      </div>
    </LoginGate>
  );
}
