"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function SkillInput({
  value,
  onChange,
  suggestions = []
}: {
  value: string[];
  onChange: (v: string[]) => void;
  suggestions?: string[];
}) {
  const [draft, setDraft] = useState("");

  const add = (s: string) => {
    const t = s.trim();
    if (t && !value.includes(t)) onChange([...value, t]);
    setDraft("");
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1">
        {value.map((s) => (
          <Badge key={s} className="cursor-pointer" onClick={() => onChange(value.filter((x) => x !== s))}>
            {s} ✕
          </Badge>
        ))}
        {value.length === 0 && <span className="text-sm text-muted-foreground">Noch keine Skills</span>}
      </div>
      <div className="flex gap-2">
        <Input
          value={draft}
          placeholder="Fähigkeit, z.B. java"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add(draft);
            }
          }}
        />
        <Button type="button" variant="outline" onClick={() => add(draft)}>
          + Hinzufügen
        </Button>
      </div>
      {suggestions.filter((s) => !value.includes(s)).length > 0 && (
        <div className="flex flex-wrap gap-1">
          <span className="text-xs text-muted-foreground">Erkannt:</span>
          {suggestions
            .filter((s) => !value.includes(s))
            .map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => add(s)}
                className="rounded-full border px-2 py-0.5 text-xs hover:border-primary"
              >
                + {s}
              </button>
            ))}
        </div>
      )}
    </div>
  );
}
