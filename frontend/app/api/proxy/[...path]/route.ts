import { getServerSession } from "next-auth";
import { NextRequest, NextResponse } from "next/server";
import { authOptions } from "@/lib/auth";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

async function forward(req: NextRequest, ctx: { params: { path: string[] } }) {
  const session = await getServerSession(authOptions);
  const idToken = (session as { idToken?: string } | null)?.idToken;
  const url = new URL(req.url);
  const path = `/${ctx.params.path.join("/")}${url.search}`;

  const headers: Record<string, string> = {};
  const ct = req.headers.get("content-type");
  if (ct) headers["content-type"] = ct;
  if (idToken) headers.Authorization = `Bearer ${idToken}`;

  const init: RequestInit = { method: req.method, headers, cache: "no-store" };
  if (!["GET", "HEAD"].includes(req.method)) {
    const buf = await req.arrayBuffer();
    if (buf.byteLength) init.body = Buffer.from(buf);
  }

  const res = await fetch(`${BACKEND}${path}`, init);
  // 204/205/304 sind „null body status"-Codes: der Response-Konstruktor wirft, wenn man
  // ihnen einen (nicht-null) Body übergibt. Solche Antworten ohne Body weiterreichen —
  // sonst scheitert z.B. jeder DELETE (Backend antwortet 204) am Proxy.
  const nullBody = res.status === 204 || res.status === 205 || res.status === 304;
  const data = nullBody ? null : await res.arrayBuffer();
  return new NextResponse(data, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" }
  });
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const PUT = forward;
export const DELETE = forward;
