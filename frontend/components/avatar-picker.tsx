"use client";

import { AVATAR_ICONS, randomAvatar } from "@/lib/icons";
import { AgentAvatar } from "@/components/agent-avatar";
import { Button } from "@/components/ui/button";

export function AvatarPicker({
  value,
  onChange,
  name
}: {
  value: string | null;
  onChange: (v: string | null) => void;
  name: string;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3">
        <AgentAvatar avatarUrl={value} name={name || "?"} size={56} />
        <Button type="button" variant="outline" onClick={() => onChange(randomAvatar())}>
          🎲 Zufällig
        </Button>
      </div>
      <div className="grid grid-cols-8 gap-2 sm:grid-cols-10">
        {AVATAR_ICONS.map((ic) => {
          const v = `preset:${ic.key}`;
          return (
            <button
              key={ic.key}
              type="button"
              title={ic.label}
              onClick={() => onChange(v)}
              className={`rounded-md border p-1 transition hover:border-primary ${
                value === v ? "border-primary ring-2 ring-primary" : ""
              }`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`/avatars/${ic.key}.svg`} alt={ic.label} width={28} height={28} />
            </button>
          );
        })}
      </div>
      <input type="hidden" name={name} value={value ?? ""} />
    </div>
  );
}
