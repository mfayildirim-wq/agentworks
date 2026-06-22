import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

async function authHeaders(): Promise<Record<string, string>> {
  const session = await getServerSession(authOptions);
  const idToken = (session as { idToken?: string } | null)?.idToken;
  return idToken ? { Authorization: `Bearer ${idToken}` } : {};
}

export type Visibility = "private" | "unlisted" | "friends" | "public";
export type RunMode = "single" | "group" | "swarm" | "graph";
export type RunStatus = "pending" | "running" | "completed" | "failed";

export interface Agent {
  id: string;
  owner_id: string;
  name: string;
  description: string;
  role: string;
  domain: string;
  avatar_url: string | null;
  visibility: Visibility;
  price_per_run: number;
  model: string;
  temperature: number;
  system_prompt: string;
  skills: string[];
  tools: string[];
  rating_avg: number;
  rating_count: number;
  created_at: string;
  updated_at: string;
}

export interface WorkAgent {
  agent_id: string;
  role_in_work: string;
  handoff_targets: string[];
  name: string;
  model: string;
}

export interface Work {
  id: string;
  owner_id: string;
  title: string;
  goal: string;
  expected_outcome: string;
  initial_message: string;
  mode: RunMode;
  visibility: Visibility;
  max_turns: number;
  max_tokens: number;
  image_url: string | null;
  agents: WorkAgent[];
  estimated_cost_usd: number;
  created_at: string;
  updated_at: string;
}

export type TemplateOutput = "html" | "markdown" | "json";

export interface TemplateInputField {
  key: string;
  label: string;
  type: "string" | "number" | "select" | "boolean";
  required: boolean;
  default?: unknown;
  options?: string[] | null;
}

export interface TemplateConfig {
  agent_ids: string[];
  prompt_template: string;
  /** Gewählte eingebaute HTML-Vorlage (Schritt ①.1); "" = keine/Altbestand. */
  html_template_id?: string;
  /** Ausgabe-Modus pro Lauf für neue Instanzen: "hinzufuegen" | "ueberarbeiten" | "ueberschreiben". */
  default_output_mode?: string;
  mcp_servers?: string[];
}

export interface Template {
  id: string;
  owner_id: string;
  title: string;
  description: string;
  category: string;
  visibility: Visibility;
  input_schema: TemplateInputField[];
  output_type: TemplateOutput;
  mode: RunMode;
  config: TemplateConfig;
  max_iterations: number;
  max_cost_usd: number;
  success_criteria: string[] | null;
  image_url: string | null;
  model?: string | null;
  /** Veröffentlichungs-Status: "" | "pending" | "rejected" (aus TemplateOut). */
  publish_status?: string;
  publish_note?: string;
  /** Kennzahlen (Slice 3): Bewertungs-Schnitt/Anzahl und Anzahl erstellter Werke. */
  avg_stars?: number;
  ratings_count?: number;
  works_count?: number;
  created_at: string;
  updated_at: string;
}

/** Eine gelistete Rezension (Bewertung mit Kommentar) für die Detailseite. */
export interface Review {
  stars: number;
  comment: string;
  user_name: string;
  created_at: string;
}

export interface PublicationRequest {
  id: string;
  title: string;
  category: string;
  owner_name: string;
  created_at: string;
}

export interface PublicTemplate {
  id: string;
  title: string;
  description: string;
  category: string;
  image_url: string | null;
  output_type: TemplateOutput;
  model: string | null;
  price: number;
  avg_stars?: number;
  ratings_count?: number;
  works_count?: number;
  creator_id?: string | null;
  creator_name?: string;
  creator_avatar?: string | null;
}

export interface ArtifactVersion {
  id: string;
  version_no: number;
  prompt: string;
  run_id: string | null;
  created_at: string;
}

export interface Job {
  id: string;
  artifact_id: string;
  title: string;
  instruction: string;
  trigger_kind: string;
  cadence: string | null;
  status: string;
  next_run_at: string | null;
  last_run_at: string | null;
  run_count: number;
  fail_count: number;
  notify_email: boolean;
  notify_telegram: boolean;
  notify_chat: boolean;
  created_by: string;
  created_at: string;
}

export interface RecentAction {
  prompt: string;
  created_at: string;
}

export interface ArtifactView {
  id: string;
  owner_id: string;
  agent_id: string;
  template_id: string | null;
  inputs: Record<string, unknown>;
  title: string;
  output_type: TemplateOutput;
  visibility: Visibility;
  image_url?: string | null;
  current_content: string;
  current_version_no: number | null;
  versions: ArtifactVersion[];
  jobs: Job[];
  publish_targets: string[];
  mcp_credentials: { server_id: string; name: string; secret_label: string; configured: boolean }[];
  external_url?: string | null;
  content_mode?: string;
  html_template_id?: string;
  /** Pro-Instanz-Ausgabevorlage: "prepared:<name>" | "agent" | "slots:<design>". */
  output_template?: string;
  /** Ausgabe-Modus für neue Versionen: "hinzufuegen" | "ueberarbeiten" | "ueberschreiben". */
  output_mode?: string;
  updated_at: string;
  cost_total_usd: string;
  /** true, wenn der anfragende Nutzer Eigentümer der Instanz ist (gating der Sichtbarkeits-Auswahl). */
  is_owner?: boolean;
  /** Eigene Bewertung des Agenten (Vorbelegung der Sterne); 0 = noch nicht bewertet. */
  my_stars?: number;
  agent_rating_avg?: number;
  agent_rating_count?: number;
  chain_next_id?: string | null;
  chain_auto?: boolean;
  chain_path?: { id: string; title: string; image_url?: string | null; is_self: boolean }[];
}

export interface Friend {
  id: string;
  name: string;
  email: string;
  avatar_url: string | null;
}

export interface FriendRequest {
  id: string;
  requester_id: string;
  name: string;
  avatar_url: string | null;
}

export interface UserSearch {
  id: string;
  name: string;
  avatar_url: string | null;
}

export interface SharedArtifact {
  artifact_id: string;
  title: string;
  icon: string | null;
  owner_name: string;
  visibility: string;
  updated_at: string;
  template_title?: string | null;
}

/** Eine 'fertige' Seiten-Vorlage (prepared) für die Instanz-Auswahl. */
export interface PageTemplate {
  name: string;
  label: string;
  description: string;
  placeholders: { key: string; label?: string }[];
}

/** Client-seitig: lädt die prepared-Vorlagen über den Proxy (mirror von html-templates). */
export async function fetchPageTemplates(): Promise<PageTemplate[]> {
  const res = await fetch("/api/proxy/page-templates", { cache: "no-store" });
  if (!res.ok) return [];
  return (await res.json()) as PageTemplate[];
}

export interface Slot {
  id: string;
  title: string;
  type: string;
  order: number;
  body: string;
}

export interface SlotData {
  layout: string;
  slots: Slot[];
}

/** Ein Eintrag im „/"-Befehlsmenü einer Instanz. */
export interface ArtifactCommand {
  key: string;
  label: string;
  /** System-Befehl ("mode"/"action") oder Template-eigener Befehl ("template"). */
  kind: string;
  /** Nur bei kind="template": Ausgabe-Modus, der vor dem Lauf gesetzt wird. */
  mode?: string;
  /** Nur bei kind="template": Anweisung an den Agenten (optional mit {input}-Platzhalter). */
  instruction?: string;
}

export interface ArtifactMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  version_id: string | null;
  version_no: number | null;
  created_at: string;
}

/** Eine Instanz in der Master-Seite (Ergebnis-Viewer). */
export interface MasterInstance {
  id: string;
  title: string;
  image_url: string | null;
  updated_at: string | null;
  /** Gerendertes HTML-Ergebnis (current_version.content). */
  html: string;
  /** True, wenn die Instanz eine aktive zeitgesteuerte Aufgabe hat (Uhr-Icon). */
  scheduled?: boolean;
}

/** Master-Seite eines Nutzers: alle (sichtbaren) Instanz-Ergebnisse. */
export interface MasterPage {
  owner_id: string;
  owner_name: string;
  is_owner: boolean;
  instances: MasterInstance[];
}

export interface ArtifactListItem {
  id: string;
  owner_id: string;
  agent_id: string;
  template_id: string | null;
  inputs: Record<string, unknown>;
  title: string;
  agent_name?: string;
  visibility: Visibility;
  image_url?: string | null;
  current_version_no: number | null;
  preview_html?: string | null;
  updated_at: string;
  schedule_cadence: string | null;
  job_count: number;
  recent_actions: RecentAction[];
  model: string | null;
  uses_own_key: boolean;
}

export interface Profile {
  email: string;
  name: string;
  avatar_url: string | null;
  telegram_connected: boolean;
  notify_email: boolean;
  notify_telegram: boolean;
  balance_usd: string;
  /** Rolle/Berechtigungen aus /users/me (Template-Gating + GOA-Admin-Seite). */
  role?: string;
  is_admin?: boolean;
  is_goa?: boolean;
}

/** Status der plattformweiten System-Keys (nie Klartext). */
export interface SystemKeysStatus {
  anthropic: boolean;
  openai: boolean;
  deepseek: boolean;
}

/** Update plattformweiter System-Keys; leer/weggelassen = behalten. */
export interface SystemKeysUpdate {
  anthropic?: string;
  openai?: string;
  deepseek?: string;
}

export interface ModelPrice {
  provider: string;
  model: string;
  label: string;
  input_per_million_usd: string;
  output_per_million_usd: string;
  portal_input_per_million_usd: string;
  portal_output_per_million_usd: string;
}

export interface LedgerItem {
  kind: string;
  amount_usd: string;
  artifact_id?: string | null;
  app_name?: string | null;
  model?: string | null;
  tokens_in: number;
  tokens_out: number;
  description: string;
  created_at: string;
}

export interface Wallet {
  balance_usd: string;
  ledger: LedgerItem[];
}

export interface InstanceUsage {
  artifact_id: string;
  title: string;
  icon: string | null;
  total_usd: string;
  runs: number;
  last_at: string | null;
}

export interface ModelOption {
  value: string;
  label: string;
  group: string;
}

/** Eine Zeile der System-Abrechnungs-Summary (je Modell oder Gesamtzeile). */
export interface BillingRow {
  model: string | null;
  runs: number;
  tokens_in: number;
  tokens_out: number;
  einkauf_usd: string;
  verkauf_usd: string;
  gewinn_usd: string;
}

export interface BillingSummary {
  models: BillingRow[];
  total: BillingRow;
}

/** Treffer der System-Nutzersuche (GOA). */
export interface SystemUserRow {
  user_id: string;
  email: string;
  name: string;
  saldo_usd: string;
  verkauf_usd: string;
}

/** Verbrauchs-Kennzahlen eines Nutzers (GOA). */
export interface UserConsumption {
  user_id: string;
  tokens_in: number;
  tokens_out: number;
  einkauf_usd: string;
  verkauf_usd: string;
  gewinn_usd: string;
  runs: number;
  topups_usd: string;
  saldo_usd: string;
}

export type ScheduleCadence = "hourly" | "daily" | "weekly";
export type ScheduleCompletion = "once" | "until" | "recurring";
export type ScheduleStatus = "active" | "paused" | "completed";

export interface ScheduleView {
  id: string;
  artifact_id: string;
  cadence: ScheduleCadence;
  cron_expr: string;
  refresh_instruction: string;
  completion_mode: ScheduleCompletion;
  end_at: string | null;
  enabled: boolean;
  status: ScheduleStatus;
  fail_count: number;
  run_count: number;
  last_run_at: string | null;
  next_run_at: string | null;
  updated_at: string;
}

export interface SchedulePut {
  cadence: ScheduleCadence;
  refresh_instruction: string;
  enabled?: boolean;
  completion_mode?: ScheduleCompletion;
  end_at?: string | null;
}

export interface InstantiateResponse {
  template_run_id: string;
  work_id: string;
  run_id: string | null;
  artifact_id: string | null;
}

export interface AgentWorkRef {
  id: string;
  title: string;
  image_url: string | null;
}

export interface Run {
  id: string;
  work_id: string;
  status: RunStatus;
  started_at: string;
  finished_at: string | null;
  total_tokens_in: number;
  total_tokens_out: number;
  total_cost: number;
  result: {
    final_message?: string;
    artifact?: string;
    output_type?: string;
    stop_reason?: string;
    iterations?: number;
  } | null;
  error: string | null;
}

export interface Message {
  id: string;
  run_id: string;
  agent_id: string | null;
  agent_name: string;
  role: string;
  content: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  ts: string;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = { "Content-Type": "application/json", ...(await authHeaders()), ...(init?.headers ?? {}) };
  const res = await fetch(`${BACKEND}${path}`, { ...init, headers, cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  agents: {
    list: (params?: Record<string, string | boolean | undefined>) => {
      const qs = new URLSearchParams();
      Object.entries(params ?? {}).forEach(([k, v]) => {
        if (v !== undefined && v !== "" && v !== false) qs.append(k, String(v));
      });
      const q = qs.toString();
      return call<Agent[]>(`/agents${q ? `?${q}` : ""}`);
    },
    get: (id: string) => call<Agent>(`/agents/${id}`),
    create: (body: unknown) => call<Agent>("/agents", { method: "POST", body: JSON.stringify(body) }),
    update: (id: string, body: unknown) =>
      call<Agent>(`/agents/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    remove: (id: string) => call<void>(`/agents/${id}`, { method: "DELETE" }),
    works: (id: string) => call<AgentWorkRef[]>(`/agents/${id}/works`)
  },
  works: {
    list: (params?: Record<string, boolean>) => {
      const qs = new URLSearchParams();
      Object.entries(params ?? {}).forEach(([k, v]) => v && qs.append(k, "true"));
      const q = qs.toString();
      return call<Work[]>(`/works${q ? `?${q}` : ""}`);
    },
    get: (id: string) => call<Work>(`/works/${id}`),
    create: (body: unknown) => call<Work>("/works", { method: "POST", body: JSON.stringify(body) }),
    copy: (id: string) => call<Work>(`/works/${id}/copy`, { method: "POST" }),
    runs: {
      start: (workId: string) => call<Run>(`/works/${workId}/runs`, { method: "POST" }),
      get: (workId: string, runId: string) => call<Run>(`/works/${workId}/runs/${runId}`),
      messages: (workId: string, runId: string) =>
        call<Message[]>(`/works/${workId}/runs/${runId}/messages`)
    }
  },
  templates: {
    list: (params?: Record<string, string | boolean | undefined>) => {
      const qs = new URLSearchParams();
      Object.entries(params ?? {}).forEach(([k, v]) => {
        if (v !== undefined && v !== "" && v !== false) qs.append(k, String(v));
      });
      const q = qs.toString();
      return call<Template[]>(`/templates${q ? `?${q}` : ""}`);
    },
    get: (id: string) => call<Template>(`/templates/${id}`),
    create: (body: unknown) =>
      call<Template>("/templates", { method: "POST", body: JSON.stringify(body) }),
    update: (id: string, body: unknown) =>
      call<Template>(`/templates/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    remove: (id: string) => call<void>(`/templates/${id}`, { method: "DELETE" }),
    instantiate: (id: string, inputs: Record<string, unknown>, output_template?: string) =>
      call<InstantiateResponse>(`/templates/${id}/instantiate`, {
        method: "POST",
        body: JSON.stringify({ inputs, ...(output_template ? { output_template } : {}) })
      }),
    // Tokenfrei — für die öffentliche Startseite (kein Login nötig).
    // Hinweis: `call` ist server-only (getServerSession + BACKEND_URL); der
    // Marktplatz sucht client-seitig direkt über /api/proxy/templates/public.
    listPublic: (category?: string, q?: string) =>
      call<PublicTemplate[]>(
        `/templates/public?sort=popular${category ? `&category=${encodeURIComponent(category)}` : ""}${q ? `&q=${encodeURIComponent(q)}` : ""}`
      )
  },
  artifacts: {
    mine: () => call<ArtifactListItem[]>("/artifacts"),
    get: (artifactId: string) => call<ArtifactView>(`/artifacts/${artifactId}`),
    adjust: (artifactId: string, instruction: string) =>
      call<{ run_id: string }>(`/artifacts/${artifactId}/adjust`, {
        method: "POST",
        body: JSON.stringify({ instruction })
      }),
    messages: (artifactId: string) =>
      call<ArtifactMessage[]>(`/artifacts/${artifactId}/messages`),
    chat: (artifactId: string, message: string) =>
      call<{ ok: boolean }>(`/artifacts/${artifactId}/chat`, {
        method: "POST",
        body: JSON.stringify({ message })
      }),
    start: (artifactId: string) =>
      call<{ ok: boolean }>(`/artifacts/${artifactId}/start`, { method: "POST" }),
    remove: (artifactId: string) =>
      call<void>(`/artifacts/${artifactId}`, { method: "DELETE" }),
    getSchedule: (artifactId: string) =>
      call<ScheduleView | null>(`/artifacts/${artifactId}/schedule`),
    putSchedule: (artifactId: string, body: SchedulePut) =>
      call<ScheduleView>(`/artifacts/${artifactId}/schedule`, {
        method: "PUT",
        body: JSON.stringify(body)
      }),
    deleteSchedule: (artifactId: string) =>
      call<void>(`/artifacts/${artifactId}/schedule`, { method: "DELETE" }),
    resumeSchedule: (artifactId: string) =>
      call<ScheduleView>(`/artifacts/${artifactId}/schedule/resume`, { method: "POST" })
  },
  models: {
    list: () => call<ModelOption[]>("/models")
  },
  // Master-Seite: "me" (Auth) = eigene Instanzen; UUID = öffentlich (PUBLIC/UNLISTED).
  master: (userId: string) => call<MasterPage>(`/users/${userId}/master`),
  wallet: {
    get: () => call<Wallet>("/wallet"),
    topup: (amount_usd: number) =>
      call<Wallet>("/wallet/topup", {
        method: "POST",
        body: JSON.stringify({ amount_usd })
      })
  },
  pricing: {
    list: () => call<ModelPrice[]>("/pricing")
  },
  profile: {
    get: () => call<Profile>("/profile"),
    update: (body: {
      name?: string;
      notify_email?: boolean;
      notify_telegram?: boolean;
    }) => call<Profile>("/profile", { method: "PUT", body: JSON.stringify(body) }),
    telegramLinkToken: () =>
      call<{ token: string; bot_username: string }>("/profile/telegram/link-token", {
        method: "POST"
      }),
    telegramDisconnect: () => call<Profile>("/profile/telegram", { method: "DELETE" })
  },
  ratings: {
    list: (agentId: string) =>
      call<{ id: string; user_id: string; stars: number; comment: string }[]>(
        `/agents/${agentId}/ratings`
      ),
    add: (agentId: string, stars: number, comment: string) =>
      call(`/agents/${agentId}/ratings`, {
        method: "POST",
        body: JSON.stringify({ stars, comment })
      })
  },
  workflow: {
    get: (workId: string) =>
      call<{ nodes: { id: string; x: number; y: number }[]; edges: { source: string; target: string }[] }>(
        `/works/${workId}/workflow`
      ),
    save: (workId: string, body: unknown) =>
      call(`/works/${workId}/workflow`, { method: "PUT", body: JSON.stringify(body) })
  },
  cron: {
    list: () => call<{ id: string; work_id: string; cron_expr: string; enabled: boolean }[]>("/cron-jobs"),
    create: (body: unknown) => call("/cron-jobs", { method: "POST", body: JSON.stringify(body) }),
    remove: (id: string) => call(`/cron-jobs/${id}`, { method: "DELETE" })
  }
};

export const CONNECTION_KINDS: Record<
  string,
  {
    name: string;
    /** "fields" (Default) = Formular mit Eingabefeldern; "oauth" = Verbinden-Button. */
    auth?: "fields" | "oauth";
    fields?: { key: string; label: string; type: string }[];
    secretLabel?: string;
  }
> = {
  sftp: {
    name: "SFTP-Server", auth: "fields", secretLabel: "Passwort",
    fields: [
      { key: "host", label: "Host", type: "text" },
      { key: "port", label: "Port", type: "number" },
      { key: "username", label: "Benutzer", type: "text" },
      { key: "remote_path", label: "Zielpfad", type: "text" }
    ]
  },
  wordpress: {
    name: "WordPress", auth: "fields", secretLabel: "Application Password",
    fields: [
      { key: "site_url", label: "Seiten-URL (https://…)", type: "text" },
      { key: "username", label: "Benutzer", type: "text" }
    ]
  },
  google_calendar: {
    name: "Google Kalender", auth: "oauth"
  },
  gmail: {
    name: "Gmail", auth: "oauth"
  }
};
