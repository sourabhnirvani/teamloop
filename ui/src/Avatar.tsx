import type { Bot } from "./api";

// Each bot has its own colour and little moves: thinking while it works, a bounce when it talks,
// a shake when it needs your OK, a wiggle when a job is done, a droop when something failed.
export type Move = "idle" | "think" | "talk" | "ask" | "cheer" | "oops";

const COLORS: Record<string, string> = {
  s: "#3b6cf6", desk: "#0f9d76", web: "#e0782a", scout: "#8b5cf6", inbox: "#d6336c", writer: "#b08900",
};

export function botColor(id: string): string {
  if (COLORS[id]) return COLORS[id];
  let h = 0;
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) % 360;
  return `hsl(${h} 60% 45%)`;
}

export function Avatar({ bot, move = "idle", size = 36 }: { bot?: Bot; move?: Move; size?: number }) {
  const id = bot?.id ?? "?";
  return (
    <span
      className={`avatar move-${move}`}
      style={{ width: size, height: size, fontSize: size * 0.5, background: botColor(id) }}
      title={bot ? `${bot.name} · ${bot.role}` : ""}
      aria-label={bot?.name}
    >
      {bot?.emoji ?? "?"}
    </span>
  );
}
