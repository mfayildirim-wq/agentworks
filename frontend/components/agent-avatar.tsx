import { monogram, resolveAvatar } from "@/lib/icons";

export function AgentAvatar({
  avatarUrl,
  name,
  size = 48
}: {
  avatarUrl: string | null | undefined;
  name: string;
  size?: number;
}) {
  if (avatarUrl && avatarUrl.startsWith("emoji:")) {
    return (
      <div
        className="flex items-center justify-center rounded-full border bg-muted"
        style={{ width: size, height: size, fontSize: Math.round(size * 0.55) }}
      >
        {avatarUrl.slice("emoji:".length)}
      </div>
    );
  }
  const src = resolveAvatar(avatarUrl);

  if (src) {
    // eslint-disable-next-line @next/next/no-img-element
    return (
      <img
        src={src}
        alt={name}
        width={size}
        height={size}
        className="rounded-full border bg-muted object-cover"
        style={{ width: size, height: size }}
      />
    );
  }
  // Kein Bild/Emoji → Monogramm: erster Buchstabe auf namensbasiert gefärbtem Kreis.
  const { letter, color } = monogram(name);
  return (
    <div
      className="flex items-center justify-center rounded-full font-semibold text-white"
      style={{ width: size, height: size, backgroundColor: color, fontSize: Math.round(size * 0.45) }}
    >
      {letter}
    </div>
  );
}
