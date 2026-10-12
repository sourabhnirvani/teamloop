// Looks for bots you build (or restyle): a face shape, an accessory, eyes and a colour. Every bot wears Agent S's
// hood (40x40 grid), in its own colour; the "body" picks the face shape under the hood.

export type Look = { body?: string; accessory?: string; eyes?: string; colour?: string };

export const BODIES: { id: string; label: string }[] = [
  { id: "blob", label: "Blob" }, { id: "monitor", label: "Screen" }, { id: "planet", label: "Planet" },
  { id: "bean", label: "Bean" }, { id: "envelope", label: "Envelope" }, { id: "pill", label: "Marshmallow" },
];
export const ACCESSORIES: { id: string; label: string }[] = [
  { id: "none", label: "None" }, { id: "antenna", label: "Antenna" }, { id: "hat", label: "Safari hat" }, { id: "crown", label: "Crown" },
  { id: "bow", label: "Bow" }, { id: "flower", label: "Flower" }, { id: "glasses", label: "Glasses" }, { id: "monocle", label: "Monocle" },
  { id: "feather", label: "Feather" }, { id: "ring", label: "Ring" }, { id: "headphones", label: "Headphones" }, { id: "leaf", label: "Sprout" },
];
export const EYES: { id: string; label: string }[] = [
  { id: "shiny", label: "Shiny" }, { id: "sparkle", label: "Sparkly" }, { id: "sleepy", label: "Sleepy" }, { id: "dot", label: "Dots" },
];
export const PALETTE = ["#7b8cff", "#16b38a", "#ff8a3d", "#9b6bff", "#ff5c8a", "#f2b705", "#2bb5f5", "#ff6b6b", "#8bd450", "#f78fd8",
  "#6c757d", "#20c997", "#c084fc", "rainbow"];

export function randomLook(): Look {
  const pick = <T,>(xs: T[]) => xs[Math.floor(Math.random() * xs.length)];
  return { body: pick(BODIES).id, accessory: pick(ACCESSORIES).id, eyes: pick(EYES).id, colour: pick(PALETTE) };
}

export const HOOD = "M5 37C3.5 31 3.6 24.5 6 19.5 9 13 14.5 9.5 21 9.5c2.6-2.6 6-4.4 10-5-1.2 2.2-1.6 4.6-1.3 7.2 4.3 3.3 6.6 8.3 6.3 14.3-.2 4-1.4 7.8-3 11z";
export const FACE = "#F6EEDF";
export const INK = "#18171B";

// where the eyes, mouth, blush and the top of the hood are, for each face shape
type Frame = { x1: number; x2: number; y: number; r: number; mouth: number; blush: number; bx1: number; bx2: number; top: number; screen?: boolean };
export const FRAMES: Record<string, Frame> = {
  blob: { x1: 15.5, x2: 24.5, y: 26, r: 2.4, mouth: 30.4, blush: 30, bx1: 12, bx2: 28, top: 9.5 },
  monitor: { x1: 16, x2: 24, y: 24.6, r: 2.1, mouth: 28.6, blush: 0, bx1: 0, bx2: 0, top: 9.5, screen: true },
  planet: { x1: 16, x2: 24, y: 25.6, r: 2.3, mouth: 30, blush: 29.6, bx1: 12.8, bx2: 27.2, top: 9.5 },
  bean: { x1: 15.8, x2: 24.4, y: 26.3, r: 2.3, mouth: 30.8, blush: 30.4, bx1: 12.4, bx2: 27.8, top: 9.5 },
  envelope: { x1: 15.5, x2: 24.5, y: 27.4, r: 2.2, mouth: 31.4, blush: 31, bx1: 11.6, bx2: 28.4, top: 9.5 },
  pill: { x1: 16.2, x2: 23.8, y: 25, r: 2.1, mouth: 29.8, blush: 29.4, bx1: 13.4, bx2: 26.6, top: 9.5 },
};

// the hood in the bot's colour, and the face under it
export function BodyShape({ body, fill }: { body: string; fill: string }) {
  let face;
  switch (body) {
    case "monitor": face = <rect x="9.5" y="18" width="21" height="15" rx="4" fill={INK} />; break;
    case "planet": face = <circle cx="20" cy="26" r="9.6" fill={FACE} />; break;
    case "bean": face = <ellipse cx="20" cy="26.5" rx="10" ry="9.4" transform="rotate(-10 20 26.5)" fill={FACE} />; break;
    case "envelope":
      face = (
        <g>
          <rect x="8.5" y="18" width="23" height="16" rx="4" fill={FACE} />
          <path d="M10 19.5 L20 25 L30 19.5" fill="none" stroke={INK} strokeOpacity=".25" strokeWidth=".8" strokeLinejoin="round" />
        </g>
      );
      break;
    case "pill": face = <rect x="11" y="16" width="18" height="19.5" rx="9" fill={FACE} />; break;
    default: face = <ellipse cx="20" cy="26" rx="11" ry="9" fill={FACE} />;
  }
  return <g><path d={HOOD} fill={fill} />{face}</g>;
}

// drawn behind the hood (a ring's back half, a feather out of the tip)
export function AccessoryBack({ accessory }: { accessory: string; f: Frame }) {
  if (accessory === "ring") return <path d="M2 25 Q20 15 38 20" fill="none" stroke={INK} strokeOpacity=".35" strokeWidth="1.4" strokeLinecap="round" />;
  if (accessory === "feather") {
    return <path className="quirk quill" d="M29.5 9.5C30.6 4.6 33.6 2 38 1c-.4 3.8-2.8 7-7 9.6z" fill={FACE} stroke={INK} strokeWidth=".6" />;
  }
  return null;
}

// drawn over the hood and face
export function AccessoryFront({ accessory, f, mood }: { accessory: string; f: Frame; mood: string }) {
  const t = f.top;
  switch (accessory) {
    case "antenna":
      return (
        <g>
          <line x1="15" y1={t + 1.5} x2="13.6" y2={t - 4} stroke={INK} strokeWidth="1.1" strokeLinecap="round" />
          <circle className="quirk bulb" cx="13.4" cy={t - 5} r="1.7" fill="#F2B32B" />
        </g>
      );
    case "hat":
      return (
        <g>
          <path d={`M11.6 ${t + 1.4} Q12 ${t - 5} 18 ${t - 5} Q24 ${t - 5} 24.4 ${t + 1.4} Z`} fill="#D9A94E" />
          <rect x="11.8" y={t - 1.4} width="12.4" height="1.8" rx=".9" fill={INK} />
          <ellipse cx="18" cy={t + 1.4} rx="10" ry="1.9" fill="#C99A12" />
        </g>
      );
    case "crown":
      return <path d={`M11.5 ${t + 1.5} L12.2 ${t - 4} L15.2 ${t - 1} L18 ${t - 5.2} L20.8 ${t - 1} L23.8 ${t - 4} L24.5 ${t + 1.5} Z`} fill="#F2B32B" stroke={INK} strokeWidth=".6" strokeLinejoin="round" />;
    case "bow":
      return (
        <g fill="#F4B7B0" stroke={INK} strokeWidth=".5" strokeLinejoin="round">
          <path d="M10 14 L5.6 11 Q4.6 14 5.6 17 Z" />
          <path d="M10 14 L14.4 11 Q15.4 14 14.4 17 Z" />
          <circle cx="10" cy="14" r="1.3" fill="#D9557A" />
        </g>
      );
    case "flower":
      return (
        <g transform="translate(9.6 14.6)">
          {[0, 72, 144, 216, 288].map((a) => <ellipse key={a} cx="0" cy="-2" rx="1.3" ry="1.9" fill={FACE} stroke={INK} strokeWidth=".35" transform={`rotate(${a})`} />)}
          <circle r="1.2" fill="#F2B32B" />
        </g>
      );
    case "leaf":
      return (
        <g>
          <line x1="17" y1={t + 1} x2="17" y2={t - 3} stroke="#1E9E7E" strokeWidth="1" strokeLinecap="round" />
          <path d={`M17 ${t - 2.6} q-4 -1 -4.6 -4.6 q4 0 4.6 4.6z`} fill="#1E9E7E" />
          <path d={`M17 ${t - 3} q3.4 -1.8 5.2 -4.2 q-3.6 -.6 -5.2 4.2z`} fill="#8FD3BE" />
        </g>
      );
    case "headphones":
      return (
        <g>
          <path d={`M7.6 ${f.y} Q7.6 ${t - 1.5} 20 ${t - 1.5} Q32.4 ${t - 1.5} 32.4 ${f.y}`} fill="none" stroke={INK} strokeWidth="1.8" strokeLinecap="round" />
          <rect x="5.4" y={f.y - 3.4} width="4.4" height="7.4" rx="2.2" fill={INK} />
          <rect x="30.2" y={f.y - 3.4} width="4.4" height="7.4" rx="2.2" fill={INK} />
        </g>
      );
    case "glasses":
      return (
        <g fill="none" stroke={INK} strokeWidth=".9">
          <circle cx={f.x1} cy={f.y} r={f.r * 1.6} />
          <circle cx={f.x2} cy={f.y} r={f.r * 1.6} />
          <path d={`M${f.x1 + f.r * 1.6} ${f.y} H${f.x2 - f.r * 1.6}`} />
        </g>
      );
    case "monocle":
      return mood === "cheer" || mood === "sleep" || mood === "oops" ? null : (
        <g className="quirk monocle" fill="none" stroke="#F2B32B" strokeWidth="1">
          <circle cx={f.x2} cy={f.y} r={f.r * 1.6} />
          <path d={`M${f.x2 + f.r * 1.4} ${f.y + 2} q2 2.6 0 5.6`} strokeWidth=".7" />
        </g>
      );
    case "ring":
      return <path d="M38 20 Q24 31 2 25" fill="none" stroke={INK} strokeWidth="1.4" strokeLinecap="round" />;
    default:
      return null;
  }
}
