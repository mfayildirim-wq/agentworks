import { LoginGate } from "@/components/login-gate";
import { api } from "@/lib/api";
import { CreateTemplateForm } from "./form";

export const dynamic = "force-dynamic";

export default async function CreateTemplatePage() {
  let agents: Awaited<ReturnType<typeof api.agents.list>> = [];
  try {
    agents = await api.agents.list();
  } catch {}
  return (
    <LoginGate>
      <h1 className="mb-4 text-2xl font-bold">Template erstellen</h1>
      <CreateTemplateForm agents={agents} />
    </LoginGate>
  );
}
