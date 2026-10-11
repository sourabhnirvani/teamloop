import type { Bot } from "./api";

// Each bot is a little mascot with its own shape, colour and accessory (the same characters walk
// around the 3D Crew Room). Moves: thinking while it works, a bounce when it talks, a shake when it
// needs your OK, a hop when a job is done, a droop when something failed.
export type Move = "idle" | "think" | "talk" | "ask" | "cheer" | "oops";

export const COLORS: Record<string, string> = {
  s: "#4f6bff", desk: "#16b38a", web: "#ff8a3d", scout: "#9b6bff", inbox: "#ff5c8a", writer: "#f2b705",
};

export function botColor(id: string): string {
  if (COLORS[id]) return COLORS[id];
  let h = 0;
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) % 360;
  return `hsl(${h} 60% 55%)`;
}

function Eyes({ x1 = 24, x2 = 40, y = 32, r = 4.6, look = 0, mood = "idle" }: { x1?: number; x2?: number; y?: number; r?: number; look?: number; mood?: Move }) {
  if (mood === "oops") {
    return (
      <g stroke="#1b1f2e" strokeWidth={2.6} strokeLinecap="round">
        <path d={`M${x1 - 3} ${y - 3} l6 6 M${x1 + 3} ${y - 3} l-6 6`} />
        <path d={`M${x2 - 3} ${y - 3} l6 6 M${x2 + 3} ${y - 3} l-6 6`} />
      </g>
    );
  }
  return (
    <g>
      <ellipse cx={x1} cy={y} rx={r} ry={r * 1.12} fill="#fff" />
      <ellipse cx={x2} cy={y} rx={r} ry={r * 1.12} fill="#fff" />
      <circle cx={x1 + look} cy={y + 0.6} r={r * 0.52} fill="#1b1f2e" />
      <circle cx={x2 + look} cy={y + 0.6} r={r * 0.52} fill="#1b1f2e" />
      <circle cx={x1 + look + 1} cy={y - 0.6} r={r * 0.18} fill="#fff" />
      <circle cx={x2 + look + 1} cy={y - 0.6} r={r * 0.18} fill="#fff" />
    </g>
  );
}

function shade(id: string) {
  return { fill: `url(#g-${id})` };
}

function Body({ id, mood }: { id: string; mood: Move }) {
  switch (id) {
    case "s": // the captain: a round blob with a cap and a compass badge
      return (
        <g>
          <ellipse cx="32" cy="38" rx="21" ry="19" {...shade(id)} />
          <path d="M13 26 Q32 6 51 26 L51 28 Q32 22 13 28 Z" fill="#1d2550" />
          <rect x="10" y="26" width="44" height="4" rx="2" fill="#141a3d" />
          <circle cx="32" cy="18" r="4.2" fill="#f6c453" />
          <path d="M32 15 L33.4 18 L32 21 L30.6 18 Z" fill="#e5484d" />
          <Eyes y={39} mood={mood} />
        </g>
      );
    case "desk": // a little screen-faced cube with an antenna
      return (
        <g>
          <line x1="32" y1="12" x2="32" y2="6" stroke="#9aa7c7" strokeWidth="2" />
          <circle cx="32" cy="5" r="2.6" fill="#7dfbd3" />
          <rect x="11" y="12" width="42" height="40" rx="11" {...shade(id)} />
          <rect x="17" y="19" width="30" height="22" rx="6" fill="#0d1526" />
          {mood === "oops" ? <Eyes y={30} r={3.6} mood={mood} /> : (
            <g fill="#7dfbd3">
              <rect x="22" y="26" width="6" height="7" rx="2" />
              <rect x="36" y="26" width="6" height="7" rx="2" />
            </g>
          )}
          <rect x="24" y="45" width="16" height="2.4" rx="1.2" fill="#0d1526" opacity=".5" />
        </g>
      );
    case "web": // a globe-ball whose eyes wander, like it's always looking something up
      return (
        <g>
          <circle cx="32" cy="34" r="21" {...shade(id)} />
          <g fill="none" stroke="#fff" strokeOpacity=".35" strokeWidth="1.4">
            <ellipse cx="32" cy="34" rx="9" ry="21" />
            <path d="M11.5 28 H52.5 M12 41 H52" />
          </g>
          <Eyes x1={30} x2={44} y={30} r={4.2} look={1.6} mood={mood} />
        </g>
      );
    case "scout": // a bean with a magnifying monocle
      return (
        <g>
          <path d="M20 14 Q44 6 50 30 Q56 54 34 57 Q12 58 13 36 Q12 18 20 14 Z" {...shade(id)} />
          <Eyes x1={26} x2={41} y={32} r={4.2} mood={mood} />
          <circle cx="41" cy="32" r="7.5" fill="none" stroke="#f6c453" strokeWidth="2.4" />
          <line x1="46" y1="38" x2="52" y2="46" stroke="#f6c453" strokeWidth="2.6" strokeLinecap="round" />
        </g>
      );
    case "inbox": // an envelope blob with a heart seal
      return (
        <g>
          <rect x="9" y="16" width="46" height="36" rx="10" {...shade(id)} />
          <path d="M11 20 L32 36 L53 20" fill="none" stroke="#fff" strokeOpacity=".55" strokeWidth="2.4" strokeLinejoin="round" />
          <path d="M32 44 c-3 -3 -7 -1 -5 2 l5 4 l5 -4 c2 -3 -2 -5 -5 -2z" fill="#fff" />
          <Eyes x1={23} x2={41} y={30} r={3.8} mood={mood} />
        </g>
      );
    case "writer": // a pill with round glasses and a quill
      return (
        <g>
          <path d="M47 8 Q58 4 53 18 L44 24 Z" fill="#fff" opacity=".9" />
          <rect x="15" y="10" width="34" height="46" rx="17" {...shade(id)} />
          <Eyes x1={25} x2={39} y={30} r={3.9} mood={mood} />
          <g fill="none" stroke="#1b1f2e" strokeWidth="1.8">
            <circle cx="25" cy="30" r="6.2" />
            <circle cx="39" cy="30" r="6.2" />
            <path d="M31.2 30 H32.8" />
          </g>
        </g>
      );
    default:
      return (
        <g>
          <circle cx="32" cy="34" r="21" {...shade(id)} />
          <Eyes mood={mood} />
        </g>
      );
  }
}

export function Mascot({ id, move = "idle", size = 36, title }: { id: string; move?: Move; size?: number; title?: string }) {
  const c = botColor(id);
  return (
    <svg className={`mascot move-${move}`} width={size} height={size} viewBox="0 0 64 64" role="img" aria-label={title}>
      {title && <title>{title}</title>}
      <defs>
        <radialGradient id={`g-${id}`} cx="35%" cy="28%" r="80%">
          <stop offset="0%" stopColor="#ffffff" stopOpacity=".55" />
          <stop offset="18%" stopColor={c} />
          <stop offset="100%" stopColor={c} stopOpacity=".78" />
        </radialGradient>
      </defs>
      <ellipse cx="32" cy="60" rx="15" ry="2.6" fill="#000" opacity=".22" />
      <Body id={id} mood={move} />
    </svg>
  );
}

export function Avatar({ bot, move = "idle", size = 36 }: { bot?: Bot; move?: Move; size?: number }) {
  const id = bot?.id ?? "?";
  return (
    <span className="avatar" style={{ width: size, height: size }} title={bot ? `${bot.name} · ${bot.role}` : ""}>
      <Mascot id={id} move={move} size={size} title={bot?.name} />
    </span>
  );
}
