import { useId, useState } from "react";
import type { Bot } from "./api";
import { Icon } from "./Icon";
import { AccessoryBack, AccessoryFront, BodyShape, FRAMES, INK, type Look } from "./Look";
import "./hoodie-crew.css";

// The crew are drawn mascots: S's frames are in /mascot, each teammate's recoloured frames in /mascot/<id>. Bots you
// build wear Agent S's hood in their own colour, with eyes that blink and a mouth that shows what the bot is doing.
// A small paper sign above the head says what it's up to: listening, thinking, a tool, talking...
export type Move = "idle" | "listen" | "think" | "talk" | "ask" | "cheer" | "oops" | "sleep";

export const COLORS: Record<string, string> = {
  s: "#18171B", desk: "#1E9E7E", web: "#E07B34", scout: "#7E5FD6", inbox: "#D9557A", writer: "#C99A12",
};

export function botColor(id: string): string {
  if (id === "s") return "var(--text)"; // S's hoodie is charcoal: follow the text colour so it reads in dark mode too
  if (COLORS[id]) return COLORS[id];
  let h = 0;
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) % 360;
  return `hsl(${h} 60% 55%)`;
}

// a bot's colour: the one picked for a built bot, else the crew colour
export function colorOf(bot?: Bot | null): string {
  const c = bot?.look?.colour;
  return c && c !== "rainbow" ? c : botColor(bot?.id ?? "?");
}

// the drawn frame for each move (the same names for S and every teammate)
export const S_FRAMES: Record<Move, string> = {
  idle: "idle", listen: "listen", think: "think", talk: "talk", ask: "click", cheer: "cheer", oops: "oops", sleep: "sleep",
};
// S's frames sit in /mascot; a teammate's recoloured ones in /mascot/<id>
export const mascotSrc = (frame: string, id = "s") => `${import.meta.env.BASE_URL}mascot/${id === "s" ? "" : `${id}/`}${frame}.webp`;

function Eyes({ x1, x2, y, r, mood, ink = INK, style = "dot" }: { x1: number; x2: number; y: number; r: number; mood: Move; ink?: string; style?: string }) {
  const w = r * 0.5;
  if (mood === "cheer") { // happy closed eyes: ^ ^
    return (
      <g fill="none" stroke={ink} strokeWidth={w} strokeLinecap="round">
        {[x1, x2].map((x) => <path key={x} d={`M${x - r} ${y + 0.6} Q${x} ${y - r} ${x + r} ${y + 0.6}`} />)}
      </g>
    );
  }
  if (mood === "oops") { // squeezed > <
    return (
      <g fill="none" stroke={ink} strokeWidth={w} strokeLinecap="round" strokeLinejoin="round">
        <path d={`M${x1 - r * 0.7} ${y - r * 0.8} L${x1 + r * 0.6} ${y} L${x1 - r * 0.7} ${y + r * 0.8}`} />
        <path d={`M${x2 + r * 0.7} ${y - r * 0.8} L${x2 - r * 0.6} ${y} L${x2 + r * 0.7} ${y + r * 0.8}`} />
      </g>
    );
  }
  if (mood === "sleep" || (style === "sleepy" && mood !== "ask" && mood !== "listen")) { // closed or half-closed
    return (
      <g className="eyes" fill="none" stroke={ink} strokeWidth={w} strokeLinecap="round">
        {[x1, x2].map((x) => <path key={x} d={`M${x - r} ${y} Q${x} ${y + r * 0.9} ${x + r} ${y}`} />)}
      </g>
    );
  }
  const up = mood === "think" ? -r * 0.35 : 0; // thinking looks up a little
  const big = mood === "ask" || mood === "listen" ? 1.12 : 1; // asking / listening: wide-eyed
  const rr = r * big * (style === "dots" ? 0.7 : 1);
  return (
    <g className="eyes">
      {[x1, x2].map((x) => (
        <g key={x}>
          <circle cx={x} cy={y + up} r={rr} fill={ink} />
          {style === "shiny" && <circle cx={x + rr * 0.35} cy={y + up - rr * 0.35} r={rr * 0.32} fill="#fff" />}
          {style === "sparkle" && (
            <path d={`M${x + rr * 0.3} ${y + up - rr * 0.75} l${rr * 0.14} ${rr * 0.3} ${rr * 0.3} ${rr * 0.14} -${rr * 0.3} ${rr * 0.14} -${rr * 0.14} ${rr * 0.3} -${rr * 0.14} -${rr * 0.3} -${rr * 0.3} -${rr * 0.14} ${rr * 0.3} -${rr * 0.14}z`} fill="#fff" />
          )}
        </g>
      ))}
    </g>
  );
}

function Mouth({ x, y, mood, ink = INK }: { x: number; y: number; mood: Move; ink?: string }) {
  switch (mood) {
    case "talk": return <ellipse className="mouth-talk" cx={x} cy={y + 0.4} rx={1.2} ry={1} fill={ink} />;
    case "cheer": return <path d={`M${x - 2} ${y - 0.3} Q${x} ${y + 2.8} ${x + 2} ${y - 0.3} Z`} fill={ink} />;
    case "think": return <circle cx={x + 1} cy={y + 0.3} r={0.6} fill={ink} />;
    case "ask": return <ellipse cx={x} cy={y + 0.4} rx={0.8} ry={1} fill={ink} />;
    case "oops": return <path d={`M${x - 2} ${y + 0.8} q.5 -.8 1 0 t1 0 t1 0 t1 0`} fill="none" stroke={ink} strokeWidth={0.7} strokeLinecap="round" />;
    case "sleep": return <circle cx={x} cy={y + 0.4} r={0.5} fill={ink} />;
    default: return <path d={`M${x - 1.5} ${y} Q${x} ${y + 1.4} ${x + 1.5} ${y}`} fill="none" stroke={ink} strokeWidth={0.8} strokeLinecap="round" />;
  }
}

// `personality` (a bot people built, or a built-in given another one) changes how it idles; see .pers-* in index.css
export function Mascot({ id, move = "idle", size = 36, title, look, personality }: { id: string; move?: Move; size?: number; title?: string; look?: Look | null; personality?: string | null }) {
  const uid = useId().replace(/:/g, "");
  const [missing, setMissing] = useState<string | null>(null); // a frame that failed to load: show the hood instead
  const cls = `mascot move-${move} p-${id in COLORS ? id : "custom"}${personality ? ` pers-${personality}` : ""}`;
  const built = look && Object.keys(look).length ? look : null;
  const src = mascotSrc(S_FRAMES[move] ?? "idle", id);
  // the crew are drawn mascots (a teammate you restyled wears its hood): the full figure when it's big, the head when small
  if (id in COLORS && (id === "s" || !built) && missing !== src) {
    const lost = () => setMissing(src);
    return size >= 96
      ? <img className={`${cls} s-full`} src={src} width={size} height={size} alt={title ?? ""} draggable={false} onError={lost} />
      : (
        <span className={`${cls} s-head`} role="img" aria-label={title}
              style={{ width: size, height: size, borderRadius: "50%",
                background: `${id === "s" ? "#18171B" : `color-mix(in srgb, ${COLORS[id]} 22%, #F6F1E8)`} url("${src}") 50% 34% / 150% auto no-repeat` }}>
          <img src={src} alt="" hidden onError={lost} />
        </span>
      );
  }
  const rainbow = built?.colour === "rainbow";
  const colour = built?.colour && !rainbow ? built.colour : botColor(id);
  const body = built?.body && FRAMES[built.body] ? built.body : "blob";
  const f = FRAMES[body];
  const acc = built?.accessory ?? "none";
  const ink = f.screen ? "#F6EEDF" : INK;
  return (
    <svg className={`${cls} hood`} width={size} height={size} viewBox="0 0 40 40" role="img" aria-label={title}>
      {title && <title>{title}</title>}
      {rainbow && (
        <defs>
          <pattern id={`r${uid}`} patternUnits="userSpaceOnUse" width="40" height="40">
            {["#D9557A", "#E07B34", "#F2B32B", "#1E9E7E", "#7E5FD6"].map((c, i) => <rect key={c} x={i * 8} width="8" height="40" fill={c} />)}
          </pattern>
        </defs>
      )}
      <g className="bod">
        <AccessoryBack accessory={acc} f={f} />
        <BodyShape body={body} fill={rainbow ? `url(#r${uid})` : colour} />
        <Eyes x1={f.x1} x2={f.x2} y={f.y} r={f.r} mood={move} ink={ink} style={built ? built.eyes === "dot" ? "dots" : built.eyes : "dot"} />
        {!f.screen && (
          <g fill="#F4B7B0">
            <ellipse cx={f.bx1} cy={f.blush} rx="2" ry="1.2" />
            <ellipse cx={f.bx2} cy={f.blush} rx="2" ry="1.2" />
          </g>
        )}
        <Mouth x={20} y={f.mouth} mood={move} ink={ink} />
        <AccessoryFront accessory={acc} f={f} mood={move} />
      </g>
    </svg>
  );
}

// What a bot is up to, as a little sign over its head: an Icon name.
export const SIGNS: Partial<Record<Move, string>> = {
  listen: "sound", think: "dots", talk: "chat", ask: "ask", cheer: "spark", oops: "warn", sleep: "moon",
};
const TOOL_SIGNS: [RegExp, string][] = [
  [/^click_on$/, "pointer"], [/^mouse$/, "mouse"],
  [/search|fetch_page|research/, "search"], [/^browser|web/, "globe"], [/write_file|note|draft/, "pen"],
  [/read_file|list_files|open_file/, "file"], [/run_command|job/, "jobs"], [/open_app|close_app|window|focus|ui_/, "screen"],
  [/type_text|press_keys/, "type"], [/screenshot|screen/, "camera"], [/volume/, "sound"], [/brightness/, "sun"], [/wifi/, "wifi"],
  [/power|lock/, "lock"], [/routine/, "routine"], [/delegate/, "mail"], [/memory|remember|recall/, "brain"], [/status/, "battery"],
];

const TOOL_NAMES: Record<string, string> = {
  web_search: "Web search", fetch_page: "Read a page", write_file: "Save a file", read_file: "Read a file",
  list_files: "Look in a folder", open_file: "Open a file", open_app: "Open an app", close_app: "Close an app",
  run_command: "Run a command", start_job: "Start a job", job_status: "Check a job", stop_job: "Stop a job",
  schedule_routine: "Set a routine", cancel_routine: "Cancel a routine", list_routines: "Look at routines",
  delegate: "Hand off", remember: "Remember", recall: "Recall", forget: "Forget", system_status: "Check the laptop",
  set_volume: "Volume", set_brightness: "Brightness", screenshot: "Look at the screen", read_screen: "Read the screen",
  type_text: "Type", press_keys: "Press keys", browser_open: "Open a site", browser_snapshot: "Read the site",
  browser_act: "Use the site", focus_window: "Switch window", lock_screen: "Lock the screen",
  click_on: "Click", mouse: "Use the mouse", find_on_screen: "Look on screen",
};

// "Set a routine" for schedule_routine; any other tool's name, made readable
export function toolName(tool: string): string {
  const name = TOOL_NAMES[tool] ?? tool.replace(/_/g, " ");
  return name.charAt(0).toUpperCase() + name.slice(1);
}

// the Icon name for a tool: render it with <Icon name={toolSign(tool)} />
export function toolSign(tool: string): string {
  return TOOL_SIGNS.find(([re]) => re.test(tool))?.[1] ?? "tool";
}

// A built-in bot with its own personality keeps its own habits; any other gets the personality's idle animation.
export function ownPersonality(bot?: Bot): string | null {
  if (!bot?.personality) return null;
  return bot.custom || bot.personality !== bot.default_personality ? bot.personality : null;
}

// the paper sign over a bot's head
export function Sign({ name, size }: { name: string; size: number }) {
  return <span className="sign hd-sign" aria-hidden="true"><Icon name={name} size={size} /></span>;
}

export function Avatar({ bot, move = "idle", size = 36, sign }: { bot?: Bot; move?: Move; size?: number; sign?: string | null }) {
  const id = bot?.id ?? "?";
  return (
    <span className="avatar" style={{ width: size, height: size }} title={bot ? `${bot.name} · ${bot.role}` : ""}>
      <Mascot id={id} move={move} size={size} title={bot?.name} look={bot?.look} personality={ownPersonality(bot)} />
      {sign && size >= 26 && <Sign key={sign} name={sign} size={Math.max(10, Math.round(size * 0.3))} />}
    </span>
  );
}
