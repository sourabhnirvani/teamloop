import { useId } from "react";
import type { Bot } from "./api";
import { AccessoryBack, AccessoryFront, BodyShape, FRAMES, type Look } from "./Look";

// The crew's mascots, drawn like the app logo: soft glossy bodies, big shiny eyes that blink, blush, and a
// mouth that shows what the bot is doing. Each bot has its own look and its own little habit (see index.css,
// "personalities"). A sign above the head says what it's up to: listening, thinking, a tool, talking...
export type Move = "idle" | "listen" | "think" | "talk" | "ask" | "cheer" | "oops" | "sleep";

export const COLORS: Record<string, string> = {
  s: "#5b6bff", desk: "#16b38a", web: "#ff8a3d", scout: "#9b6bff", inbox: "#ff5c8a", writer: "#f2b705",
};

// body gradients (light top -> colour bottom) per bot
const BODY: Record<string, [string, string]> = {
  s: ["#ffffff", "#cdd4ff"], desk: ["#8af5d6", "#17b48b"], web: ["#ffd0a1", "#ff8a3d"],
  scout: ["#d9c2ff", "#9b6bff"], inbox: ["#ffc2d6", "#ff5c8a"], writer: ["#fff0a8", "#f2b705"],
};

export function botColor(id: string): string {
  if (COLORS[id]) return COLORS[id];
  let h = 0;
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) % 360;
  return `hsl(${h} 60% 55%)`;
}

const INK = "#1d2150";

// a bot's colour: the one picked for a built bot, else the crew colour
export function colorOf(bot?: Bot | null): string {
  const c = bot?.look?.colour;
  return c && c !== "rainbow" ? c : botColor(bot?.id ?? "?");
}

function Eyes({ x1, x2, y, r, mood, ink = INK, look = 0, style = "shiny" }: { x1: number; x2: number; y: number; r: number; mood: Move; ink?: string; look?: number; style?: string }) {
  if (mood === "cheer") { // happy closed eyes: ^ ^
    return (
      <g fill="none" stroke={ink} strokeWidth={r * 0.62} strokeLinecap="round">
        <path d={`M${x1 - r} ${y + 1} Q${x1} ${y - r * 1.1} ${x1 + r} ${y + 1}`} />
        <path d={`M${x2 - r} ${y + 1} Q${x2} ${y - r * 1.1} ${x2 + r} ${y + 1}`} />
      </g>
    );
  }
  if (mood === "oops") { // squeezed > <
    return (
      <g fill="none" stroke={ink} strokeWidth={r * 0.55} strokeLinecap="round" strokeLinejoin="round">
        <path d={`M${x1 - r * 0.8} ${y - r * 0.8} L${x1 + r * 0.6} ${y} L${x1 - r * 0.8} ${y + r * 0.8}`} />
        <path d={`M${x2 + r * 0.8} ${y - r * 0.8} L${x2 - r * 0.6} ${y} L${x2 + r * 0.8} ${y + r * 0.8}`} />
      </g>
    );
  }
  if (mood === "sleep") { // closed, peaceful
    return (
      <g fill="none" stroke={ink} strokeWidth={r * 0.5} strokeLinecap="round">
        <path d={`M${x1 - r} ${y} Q${x1} ${y + r} ${x1 + r} ${y}`} />
        <path d={`M${x2 - r} ${y} Q${x2} ${y + r} ${x2 + r} ${y}`} />
      </g>
    );
  }
  const up = mood === "think" ? -r * 0.35 : 0; // thinking looks up a little
  const big = mood === "ask" || mood === "listen" ? 1.12 : 1; // asking / listening: wide-eyed
  if (style === "dot") {
    return <g className="eyes">{[x1, x2].map((x) => <circle key={x} cx={x + look} cy={y + up} r={r * 0.62 * big} fill={ink} />)}</g>;
  }
  if (style === "sleepy" && mood !== "ask" && mood !== "listen") { // calm half-closed eyes
    return (
      <g className="eyes" fill="none" stroke={ink} strokeWidth={r * 0.55} strokeLinecap="round">
        {[x1, x2].map((x) => <path key={x} d={`M${x - r} ${y + up} Q${x} ${y + up + r * 0.9} ${x + r} ${y + up}`} />)}
      </g>
    );
  }
  return (
    <g className="eyes">
      {[x1, x2].map((x) => (
        <g key={x}>
          <ellipse cx={x + look} cy={y + up} rx={r * big} ry={r * 1.28 * big} fill={ink} />
          {style === "sparkle" ? (
            <path d={`M${x + look + r * 0.35} ${y + up - r * 0.95} l${r * 0.16} ${r * 0.36} ${r * 0.36} ${r * 0.16} -${r * 0.36} ${r * 0.16} -${r * 0.16} ${r * 0.36} -${r * 0.16} -${r * 0.36} -${r * 0.36} -${r * 0.16} ${r * 0.36} -${r * 0.16}z`} fill="#fff" />
          ) : (
            <circle cx={x + look + r * 0.38} cy={y + up - r * 0.45} r={r * 0.42} fill="#fff" />
          )}
          <circle cx={x + look - r * 0.35} cy={y + up + r * 0.5} r={r * 0.18} fill="#fff" opacity=".85" />
        </g>
      ))}
      {mood === "ask" && (
        <g fill="none" stroke={ink} strokeWidth={r * 0.35} strokeLinecap="round" opacity=".8">
          <path d={`M${x1 - r} ${y - r * 2.1} q${r} ${-r * 0.7} ${r * 2} 0`} />
          <path d={`M${x2 - r} ${y - r * 2.1} q${r} ${-r * 0.7} ${r * 2} 0`} />
        </g>
      )}
    </g>
  );
}

function Mouth({ x, y, s = 1, mood, ink = INK }: { x: number; y: number; s?: number; mood: Move; ink?: string }) {
  switch (mood) {
    case "talk":
      return <ellipse className="mouth-talk" cx={x} cy={y + 0.6 * s} rx={2.2 * s} ry={1.9 * s} fill={ink} />;
    case "cheer":
      return (
        <g>
          <path d={`M${x - 3.6 * s} ${y - 0.4 * s} Q${x} ${y + 5 * s} ${x + 3.6 * s} ${y - 0.4 * s} Z`} fill={ink} />
          <ellipse cx={x} cy={y + 2.4 * s} rx={1.6 * s} ry={0.9 * s} fill="#ff7a9c" />
        </g>
      );
    case "think":
      return <circle cx={x + 1.6 * s} cy={y + 0.6 * s} r={1.1 * s} fill={ink} />;
    case "ask":
      return <ellipse cx={x} cy={y + 0.8 * s} rx={1.5 * s} ry={1.8 * s} fill={ink} />;
    case "oops":
      return <path d={`M${x - 3.4 * s} ${y + 1.4 * s} q${0.85 * s} ${-1.4 * s} ${1.7 * s} 0 t${1.7 * s} 0 t${1.7 * s} 0 t${1.7 * s} 0`} fill="none" stroke={ink} strokeWidth={1.2 * s} strokeLinecap="round" />;
    case "sleep":
      return <circle cx={x} cy={y + 0.8 * s} r={0.9 * s} fill={ink} />;
    default: // idle, listen: a small smile
      return <path d={`M${x - 2.6 * s} ${y} Q${x} ${y + 2.6 * s} ${x + 2.6 * s} ${y}`} fill="none" stroke={ink} strokeWidth={1.3 * s} strokeLinecap="round" />;
  }
}

function Blush({ x1, x2, y, r = 2.6 }: { x1: number; x2: number; y: number; r?: number }) {
  return (
    <g fill="#ff8fb3" opacity=".6">
      <ellipse cx={x1} cy={y} rx={r} ry={r * 0.6} />
      <ellipse cx={x2} cy={y} rx={r} ry={r * 0.6} />
    </g>
  );
}

function Body({ id, mood, fill }: { id: string; mood: Move; fill: string }) {
  switch (id) {
    case "s": // the captain: the logo's friendly blob with its antenna star
      return (
        <g>
          <line x1="32" y1="15" x2="32" y2="8.5" stroke="#c9d0ff" strokeWidth="2" strokeLinecap="round" />
          <circle className="quirk bulb" cx="32" cy="7" r="3.3" fill="#ffd45c" />
          <path d="M32 14c12.4 0 20 8.6 20 20.4 0 11.4-7.4 18.3-20 18.3s-20-6.9-20-18.3C12 22.6 19.6 14 32 14z" fill={fill} />
          <path d="M24 49.5 L32 46 L40 49.5 L32 52 Z" fill="#5b6bff" />
          <Eyes x1={25} x2={39} y={31} r={4} mood={mood} />
          <Blush x1={20.5} x2={43.5} y={38} />
          <Mouth x={32} y={39} s={1.15} mood={mood} />
        </g>
      );
    case "desk": // a little monitor with a glowing face
      return (
        <g>
          <line x1="32" y1="14" x2="32" y2="8" stroke="#0f8f6e" strokeWidth="2" strokeLinecap="round" />
          <circle className="quirk bulb" cx="32" cy="6.6" r="2.8" fill="#7dfbd3" />
          <rect x="24" y="48" width="16" height="6" rx="3" fill="#0f8f6e" />
          <rect x="10" y="13" width="44" height="37" rx="11" fill={fill} />
          <rect className="quirk screen" x="15.5" y="18.5" width="33" height="25" rx="7" fill="#0e2b33" />
          <Eyes x1={25.5} x2={38.5} y={29} r={3.6} mood={mood} ink="#7dfbd3" />
          <Mouth x={32} y={36} s={0.85} mood={mood} ink="#7dfbd3" />
          <g fill="#ff8fb3" opacity=".55"><circle cx="20.5" cy="35" r="1.8" /><circle cx="43.5" cy="35" r="1.8" /></g>
        </g>
      );
    case "web": // a dreamy little planet with a ring
      return (
        <g>
          <path d="M5.5 37.5 Q32 22 58.5 30.5" fill="none" stroke="#ffe0bd" strokeOpacity=".7" strokeWidth="2.6" strokeLinecap="round" />
          <circle cx="32" cy="34" r="19" fill={fill} />
          <g fill="none" stroke="#fff" strokeOpacity=".28" strokeWidth="1.2">
            <ellipse cx="32" cy="34" rx="8" ry="19" />
            <path d="M14 28.5 H50 M14.5 40 H49.5" />
          </g>
          <Eyes x1={25.5} x2={38.5} y={31} r={3.9} mood={mood} look={mood === "idle" ? 0.9 : 0} />
          <Blush x1={21} x2={43} y={38.5} />
          <Mouth x={32} y={39.4} s={1.1} mood={mood} />
          <path d="M58.5 30.5 Q40 44 5.5 37.5" fill="none" stroke="#fff3e3" strokeWidth="2.6" strokeLinecap="round" />
        </g>
      );
    case "scout": // a curious explorer with a safari hat and a monocle
      return (
        <g>
          <path d="M32 17c11 0 18 9 18 20.5S43 55 32 55s-18-6.5-18-18S21 17 32 17z" fill={fill} />
          <ellipse cx="32" cy="19" rx="19" ry="4.2" fill="#d9a94e" />
          <path d="M20 19 Q21 7.5 32 7.5 Q43 7.5 44 19 Z" fill="#efc46d" />
          <rect x="20.4" y="15" width="23.2" height="3.4" rx="1.7" fill="#8a5a2b" />
          <Eyes x1={25.5} x2={38.5} y={33} r={3.9} mood={mood} />
          {mood !== "cheer" && mood !== "sleep" && mood !== "oops" && (
            <g className="quirk monocle">
              <circle cx="38.5" cy="33" r="6.8" fill="none" stroke="#f6c453" strokeWidth="1.8" />
              <path d="M45 36.5 q3 4 0 9" fill="none" stroke="#f6c453" strokeWidth="1.1" />
            </g>
          )}
          <Blush x1={21} x2={44} y={41} />
          <Mouth x={32} y={42.6} s={1.1} mood={mood} />
        </g>
      );
    case "inbox": // a sweet envelope bun with a heart seal
      return (
        <g>
          <rect x="9" y="17" width="46" height="36" rx="13" fill={fill} />
          <path d="M11.5 21.5 L32 33 L52.5 21.5" fill="#ffd6e3" fillOpacity=".55" stroke="#fff" strokeOpacity=".75" strokeWidth="2" strokeLinejoin="round" />
          <path className="quirk heart" d="M32 36.2c-1.9-2.2-5.1-0.9-4 1.6l4 3.4 4-3.4c1.1-2.5-2.1-3.8-4-1.6z" fill="#e53965" />
          <Eyes x1={22.5} x2={41.5} y={40} r={3.6} mood={mood} />
          <Blush x1={17} x2={47} y={46} r={2.3} />
          <Mouth x={32} y={46.2} s={0.85} mood={mood} />
        </g>
      );
    case "writer": // a buttery marshmallow scholar: round glasses and a quill
      return (
        <g>
          <g className="quirk quill">
            <path d="M46.5 22.5C48 13.5 53.5 7 60 4.5c-.6 6.8-5 13.2-12 19.6z" fill="#cfe8ff" stroke="#8fbbe8" strokeWidth=".9" />
            <path d="M47.5 23Q52.5 13 59.2 5.4" fill="none" stroke="#8fbbe8" strokeWidth=".9" strokeLinecap="round" />
            <path d="M50.5 15.5l3 .6M52.8 11.8l3 .4" stroke="#8fbbe8" strokeWidth=".7" strokeLinecap="round" />
          </g>
          <rect x="15" y="10" width="34" height="46" rx="17" fill={fill} />
          <Eyes x1={25.5} x2={38.5} y={30} r={3.3} mood={mood} />
          <g fill="none" stroke="#3b2f12" strokeWidth="1.5" opacity=".85">
            <circle cx="25.5" cy="30" r="6.2" />
            <circle cx="38.5" cy="30" r="6.2" />
            <path d="M31.7 30 H32.3" />
          </g>
          <Blush x1={21.5} x2={42.5} y={39} r={2.3} />
          <Mouth x={32} y={40.5} s={1.1} mood={mood} />
        </g>
      );
    default: // a bot you built: a round friend in its own colour
      return (
        <g>
          <circle cx="32" cy="34" r="19" fill={fill} />
          <Eyes x1={25.5} x2={38.5} y={31} r={3.9} mood={mood} />
          <Blush x1={21} x2={43} y={38.5} />
          <Mouth x={32} y={39.4} s={1.1} mood={mood} />
        </g>
      );
  }
}

function lighten(hex: string, k = 0.55): string {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex);
  if (!m) return "#ffffff";
  const n = parseInt(m[1], 16);
  const mix = (c: number) => Math.round(c + (255 - c) * k).toString(16).padStart(2, "0");
  return `#${mix(n >> 16)}${mix((n >> 8) & 255)}${mix(n & 255)}`;
}

function LookBody({ look, mood, fill }: { look: Look; mood: Move; fill: string }) {
  const body = look.body && FRAMES[look.body] ? look.body : "blob";
  const f = FRAMES[body];
  const acc = look.accessory ?? "none";
  const ink = f.screen ? "#7dfbd3" : INK;
  return (
    <g>
      <AccessoryBack accessory={acc} f={f} />
      <BodyShape body={body} fill={fill} />
      <Eyes x1={f.x1} x2={f.x2} y={f.y} r={f.r} mood={mood} ink={ink} style={look.eyes} />
      {!f.screen && <Blush x1={f.bx1} x2={f.bx2} y={f.blush} r={2.4} />}
      <Mouth x={32} y={f.mouth} s={f.screen ? 0.85 : 1.05} mood={mood} ink={ink} />
      <AccessoryFront accessory={acc} f={f} mood={mood} />
    </g>
  );
}

// `personality` (a bot people built, or a built-in given another one) changes how it idles; see .pers-* in index.css
export function Mascot({ id, move = "idle", size = 36, title, look, personality }: { id: string; move?: Move; size?: number; title?: string; look?: Look | null; personality?: string | null }) {
  const uid = useId().replace(/:/g, "");
  const built = look && Object.keys(look).length ? look : null;
  const colour = built?.colour && built.colour !== "rainbow" ? built.colour : botColor(id);
  const [top, bottom] = built ? [lighten(colour), colour] : BODY[id] ?? ["#ffffff", botColor(id)];
  const known = id in BODY ? id : "custom";
  return (
    <svg className={`mascot move-${move} p-${known}${personality ? ` pers-${personality}` : ""}`} width={size} height={size} viewBox="0 0 64 64" role="img" aria-label={title}>
      {title && <title>{title}</title>}
      <defs>
        {built?.colour === "rainbow" ? (
          <linearGradient id={`b${uid}`} x1="0" y1="0" x2="1" y2="1">
            {["#ff8fb3", "#ffd45c", "#8af5d6", "#7bb8ff", "#c9a8ff"].map((c, i) => <stop key={c} offset={i / 4} stopColor={c} />)}
          </linearGradient>
        ) : (
          <linearGradient id={`b${uid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={top} />
            <stop offset="1" stopColor={bottom} />
          </linearGradient>
        )}
        <radialGradient id={`h${uid}`} cx="32%" cy="22%" r="55%">
          <stop offset="0" stopColor="#fff" stopOpacity=".55" />
          <stop offset="1" stopColor="#fff" stopOpacity="0" />
        </radialGradient>
      </defs>
      <ellipse className="ground" cx="32" cy="59.5" rx="15" ry="2.6" fill="#000" opacity=".2" />
      <g className="bod">
        {built ? <LookBody look={built} mood={move} fill={`url(#b${uid})`} /> : <Body id={id} mood={move} fill={`url(#b${uid})`} />}
        <ellipse cx="25" cy="22" rx="9" ry="5" fill={`url(#h${uid})`} pointerEvents="none" />
      </g>
    </svg>
  );
}

// What a bot is up to, as a little sign over its head.
export const SIGNS: Partial<Record<Move, string>> = {
  listen: "👂", think: "💭", talk: "💬", ask: "🙋", cheer: "✨", oops: "💦", sleep: "💤",
};
const TOOL_SIGNS: [RegExp, string][] = [
  [/search|fetch_page|research/, "🔎"], [/^browser|web/, "🌐"], [/write_file|note|draft/, "✍️"],
  [/read_file|list_files|open_file/, "📄"], [/run_command|job/, "⌨️"], [/open_app|close_app|window|focus|ui_/, "🖥️"],
  [/type_text|press_keys/, "⌨️"], [/screenshot|screen/, "📸"], [/volume/, "🔊"], [/brightness/, "☀️"], [/wifi/, "📶"],
  [/power|lock/, "🔒"], [/routine/, "⏰"], [/delegate/, "📨"], [/memory|remember|recall/, "🧠"], [/status/, "🔋"],
];

export function toolSign(tool: string): string {
  return TOOL_SIGNS.find(([re]) => re.test(tool))?.[1] ?? "🛠️";
}

// A built-in bot with its own personality keeps its own habits (compass, flicker, hops...); any other gets the
// personality's idle animation.
export function ownPersonality(bot?: Bot): string | null {
  if (!bot?.personality) return null;
  return bot.custom || bot.personality !== bot.default_personality ? bot.personality : null;
}

export function Avatar({ bot, move = "idle", size = 36, sign }: { bot?: Bot; move?: Move; size?: number; sign?: string | null }) {
  const id = bot?.id ?? "?";
  return (
    <span className="avatar" style={{ width: size, height: size }} title={bot ? `${bot.name} · ${bot.role}` : ""}>
      <Mascot id={id} move={move} size={size} title={bot?.name} look={bot?.look} personality={ownPersonality(bot)} />
      {sign && size >= 26 && <span key={sign} className="sign" style={{ fontSize: Math.max(10, Math.round(size * 0.34)) }} aria-hidden="true">{sign}</span>}
    </span>
  );
}
