import { notFound } from "next/navigation";
import { api, type ArtifactView } from "@/lib/api";
import { LoginGate } from "@/components/login-gate";
import { ArtifactWorkView } from "./work-view";
import { InstanceDeleteButton } from "@/components/instance-delete-button";

export const dynamic = "force-dynamic";

export default async function ArtifactPage({
  params
}: {
  params: { artifactId: string };
}) {
  let view: ArtifactView;
  try {
    view = await api.artifacts.get(params.artifactId);
  } catch {
    notFound();
  }
  return (
    <LoginGate>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="truncate text-lg font-semibold">{view.title}</h1>
          <InstanceDeleteButton artifactId={params.artifactId} title={view.title} />
        </div>
        <ArtifactWorkView initial={view} artifactId={params.artifactId} />
      </div>
    </LoginGate>
  );
}
