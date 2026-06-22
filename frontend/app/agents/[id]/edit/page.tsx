import { api } from "@/lib/api";
import { EditAgentForm } from "./form";

export const dynamic = "force-dynamic";

export default async function EditAgentPage({ params }: { params: { id: string } }) {
  const agent = await api.agents.get(params.id);
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Agent bearbeiten</h1>
      <EditAgentForm agent={agent} />
    </div>
  );
}
