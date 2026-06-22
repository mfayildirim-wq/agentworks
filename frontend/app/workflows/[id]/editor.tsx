"use client";

import { useCallback, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  addEdge,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node
} from "reactflow";
import "reactflow/dist/style.css";
import { Button } from "@/components/ui/button";

interface Props {
  workId: string;
  agents: { id: string; name: string }[];
  initialNodes: { id: string; x: number; y: number }[];
  initialEdges: { source: string; target: string }[];
}

export function WorkflowEditor({ workId, agents, initialNodes, initialEdges }: Props) {
  const agentName = (id: string) => agents.find((a) => a.id === id)?.name ?? id.slice(0, 8);

  const seedNodes: Node[] =
    initialNodes.length > 0
      ? initialNodes.map((n) => ({
          id: n.id,
          position: { x: n.x, y: n.y },
          data: { label: agentName(n.id) }
        }))
      : agents.map((a, i) => ({
          id: a.id,
          position: { x: 80 + (i % 3) * 200, y: 80 + Math.floor(i / 3) * 120 },
          data: { label: a.name }
        }));

  const seedEdges: Edge[] = initialEdges.map((e, i) => ({
    id: `e-${i}`,
    source: e.source,
    target: e.target
  }));

  const [nodes, , onNodesChange] = useNodesState(seedNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(seedEdges);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  const onConnect = useCallback(
    (conn: Connection) => setEdges((eds) => addEdge({ ...conn, id: `e-${Date.now()}` }, eds)),
    [setEdges]
  );

  async function save() {
    setSaving(true);
    const payload = {
      nodes: nodes.map((n) => ({ id: n.id, x: n.position.x, y: n.position.y })),
      edges: edges.map((e) => ({ source: e.source, target: e.target }))
    };
    const res = await fetch(`/api/proxy/works/${workId}/workflow`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    setSaving(false);
    if (res.ok) setSavedAt(new Date().toLocaleTimeString());
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Verbinde Agenten zu einem DAG; das Speichern setzt Mode = graph.
        </p>
        <div className="flex items-center gap-2">
          {savedAt && <span className="text-xs text-muted-foreground">gespeichert {savedAt}</span>}
          <Button onClick={save} disabled={saving}>
            {saving ? "speichere…" : "Speichern"}
          </Button>
        </div>
      </div>
      <div className="h-[600px] rounded-md border">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          fitView
        >
          <Background />
          <Controls />
          <MiniMap />
        </ReactFlow>
      </div>
    </div>
  );
}
