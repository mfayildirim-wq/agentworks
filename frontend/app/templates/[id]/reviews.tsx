"use client";

import { useEffect, useState } from "react";
import type { Review } from "@/lib/api";

function stars(n: number): string {
  const s = Math.max(0, Math.min(5, Math.round(n)));
  return "★".repeat(s) + "☆".repeat(5 - s);
}

export function Reviews({ agentId }: { agentId: string }) {
  const [reviews, setReviews] = useState<Review[] | null>(null);

  useEffect(() => {
    let active = true;
    void fetch(`/api/proxy/agents/${agentId}/reviews`)
      .then((res) => (res.ok ? (res.json() as Promise<Review[]>) : []))
      .then((list) => {
        if (active) setReviews(Array.isArray(list) ? list : []);
      })
      .catch(() => {
        if (active) setReviews([]);
      });
    return () => {
      active = false;
    };
  }, [agentId]);

  return (
    <div className="mt-6">
      <h2 className="mb-2 font-semibold">Bewertungen</h2>
      {reviews === null ? (
        <p className="text-sm text-gray-500">Lädt…</p>
      ) : reviews.length === 0 ? (
        <p className="text-sm text-gray-500">Noch keine Rezensionen.</p>
      ) : (
        <ul className="space-y-3">
          {reviews.map((r, i) => (
            <li key={i} className="rounded border p-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-amber-500" aria-label={`${r.stars} von 5 Sternen`}>
                  {stars(r.stars)}
                </span>
                <span className="text-xs text-gray-400">
                  {new Date(r.created_at).toLocaleDateString()}
                </span>
              </div>
              <p className="mt-1 text-gray-700">{r.comment}</p>
              <p className="mt-1 text-xs text-gray-500">{r.user_name}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
