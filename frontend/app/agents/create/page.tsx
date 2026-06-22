import { LoginGate } from "@/components/login-gate";
import { CreateAgentForm } from "./form";

export default function CreateAgentPage() {
  return (
    <LoginGate>
      <h1 className="mb-4 text-2xl font-bold">Neuen Agenten erstellen</h1>
      <CreateAgentForm />
    </LoginGate>
  );
}
