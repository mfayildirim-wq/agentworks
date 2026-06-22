import { LoginGate } from "@/components/login-gate";
import { api } from "@/lib/api";
import { CreateWorkForm } from "./form";

export const dynamic = "force-dynamic";

export default async function CreateWorkPage({ searchParams }: { searchParams: { agent?: string } }) {
  let agents: Awaited<ReturnType<typeof api.agents.list>> = [];
  try {
    agents = await api.agents.list();
  } catch {}
  return (
    <LoginGate>
      <h1 className="mb-4 text-2xl font-bold">Neuen Work erstellen</h1>
      <CreateWorkForm agents={agents} preselected={searchParams.agent} />
    </LoginGate>
  );
}
