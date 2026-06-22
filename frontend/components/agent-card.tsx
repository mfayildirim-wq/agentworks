"use client";

import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Agent } from "@/lib/api";
import { formatCost } from "@/lib/utils";
import { AgentAvatar } from "@/components/agent-avatar";

export function AgentCard({ agent }: { agent: Agent }) {
  return (
    <Link href={`/agents/${agent.id}`}>
      <Card className="h-full transition hover:border-primary hover:shadow-md">
        <CardHeader>
          <div className="flex items-center gap-3">
            <AgentAvatar avatarUrl={agent.avatar_url} name={agent.name} size={44} />
            <div>
              <CardTitle>{agent.name}</CardTitle>
              <CardDescription>{agent.role || agent.domain || agent.model}</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="line-clamp-3 text-sm text-muted-foreground">{agent.description || "—"}</p>
          <div className="flex flex-wrap gap-1">
            {agent.skills.slice(0, 4).map((s) => (
              <Badge key={s}>{s}</Badge>
            ))}
          </div>
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{agent.model}</span>
            <span>
              {agent.rating_count > 0 ? `★ ${agent.rating_avg.toFixed(1)} (${agent.rating_count})` : "neu"}
            </span>
            <span>{formatCost(agent.price_per_run)}</span>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
