"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

interface RatingRow {
  id: string;
  user_id: string;
  stars: number;
  comment: string;
}

export function RatingsBlock({ agentId }: { agentId: string }) {
  const [ratings, setRatings] = useState<RatingRow[]>([]);
  const [stars, setStars] = useState(5);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function refresh() {
    const res = await fetch(`/api/proxy/agents/${agentId}/ratings`, { cache: "no-store" });
    if (res.ok) setRatings(await res.json());
  }
  useEffect(() => {
    refresh();
  }, [agentId]);

  async function submit() {
    setSubmitting(true);
    await fetch(`/api/proxy/agents/${agentId}/ratings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stars, comment })
    });
    setSubmitting(false);
    setComment("");
    refresh();
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Bewertungen</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-2">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => setStars(n)}
              className={n <= stars ? "text-yellow-500" : "text-muted-foreground"}
            >
              ★
            </button>
          ))}
        </div>
        <Textarea value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Kommentar…" />
        <Button onClick={submit} disabled={submitting} size="sm">
          {submitting ? "…" : "Bewertung abgeben"}
        </Button>
        <div className="space-y-2 pt-2">
          {ratings.map((r) => (
            <div key={r.id} className="rounded border p-2 text-sm">
              <div className="text-yellow-500">{"★".repeat(r.stars)}</div>
              {r.comment && <p className="text-muted-foreground">{r.comment}</p>}
            </div>
          ))}
          {ratings.length === 0 && <p className="text-xs text-muted-foreground">Noch keine Bewertungen.</p>}
        </div>
      </CardContent>
    </Card>
  );
}
