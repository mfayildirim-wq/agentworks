import { notFound } from "next/navigation";
import { LoginGate } from "@/components/login-gate";
import { api, type Template } from "@/lib/api";
import { AgentTemplateForm, type AgentTemplateInitial } from "../../create/form";
import { loadModelOptions } from "../../model-options";
import { TemplateDeleteButton } from "@/components/template-delete-button";

export const dynamic = "force-dynamic";

export default async function EditAgentTemplatePage({ params }: { params: { id: string } }) {
  let template: Template;
  try {
    template = await api.templates.get(params.id);
  } catch {
    notFound();
  }

  const { options, hasOwnKeys } = await loadModelOptions();

  const initial: AgentTemplateInitial = {
    name: template.title,
    description: template.description ?? "",
    prompt: template.config?.prompt_template ?? "",
    model: template.model ?? options[0]?.value ?? "qwen2.5:3b",
    price: template.max_cost_usd,
    category: template.category ?? "",
    visibility: template.visibility,
    image_url: template.image_url ?? "",
    html_template_id: template.config?.html_template_id ?? "",
    mcp_servers: template.config?.mcp_servers ?? []
  };

  return (
    <LoginGate>
      <div className="mb-1 flex items-start justify-between gap-2">
        <h1 className="text-2xl font-bold">Agent-Vorlage bearbeiten</h1>
        <TemplateDeleteButton templateId={params.id} title={template.title} redirectTo="/marktplatz?f=mine" />
      </div>
      <p className="mb-4 text-sm text-muted-foreground">
        Änderungen gelten ab dem nächsten Lauf für neue Instanzen dieser Vorlage.
      </p>
      <AgentTemplateForm
        models={options}
        hasOwnKeys={hasOwnKeys}
        templateId={params.id}
        initial={initial}
      />
    </LoginGate>
  );
}
