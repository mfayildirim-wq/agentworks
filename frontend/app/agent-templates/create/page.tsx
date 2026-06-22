import { LoginGate } from "@/components/login-gate";
import { AgentTemplateForm } from "./form";
import { loadModelOptions } from "../model-options";

export const dynamic = "force-dynamic";

export default async function CreateAgentTemplatePage() {
  const { options, hasOwnKeys } = await loadModelOptions();

  return (
    <LoginGate>
      <h1 className="mb-1 text-2xl font-bold">Agent-Vorlage erstellen</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        Beschreibe im Prompt, was der Agent tun soll — Nutzer erzeugen daraus ihre eigenen Instanzen.
      </p>
      <AgentTemplateForm models={options} hasOwnKeys={hasOwnKeys} />
    </LoginGate>
  );
}
