import { LoginGate } from "@/components/login-gate";
import { api } from "@/lib/api";
import { CronManager } from "./cron-manager";

export const dynamic = "force-dynamic";

export default async function CronPage() {
  let jobs: Awaited<ReturnType<typeof api.cron.list>> = [];
  let works: Awaited<ReturnType<typeof api.works.list>> = [];
  try {
    [jobs, works] = await Promise.all([api.cron.list(), api.works.list({ mine: true })]);
  } catch {}
  return (
    <LoginGate>
      <h1 className="mb-4 text-2xl font-bold">Cron-Jobs</h1>
      <CronManager
        initialJobs={jobs}
        works={works.map((w) => ({ id: w.id, title: w.title }))}
      />
    </LoginGate>
  );
}
