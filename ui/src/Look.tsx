// Looks for bots you build (or restyle): a body, an accessory, eyes and a colour. Every combination is drawn in
// the same soft, glossy style as the built-in crew, with the same moving face.

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

// where the face and the top of the head are, for each body
type Frame = { x1: number; x2: number; y: number; r: number; mouth: number; blush: number; bx1: number; bx2: number; top: number; screen?: boolean };
export const FRAMES: Record<string, Frame> = {
  blob: { x1: 25, x2: 39, y: 31, r: 4, mouth: 39, blush: 38, bx1: 20.5, bx2: 43.5, top: 14 },
  monitor: { x1: 25.5, x2: 38.5, y: 29, r: 3.6, mouth: 36, blush: 35, bx1: 20.5, bx2: 43.5, top: 13, screen: true },
  planet: { x1: 25.5, x2: 38.5, y: 31, r: 3.9, mouth: 39.4, blush: 38.5, bx1: 21, bx2: 43, top: 15 },
  bean: { x1: 25.5, x2: 38.5, y: 33, r: 3.9, mouth: 42.6, blush: 41, bx1: 21, bx2: 44, top: 17 },
  envelope: { x1: 22.5, x2: 41.5, y: 40, r: 3.6, mouth: 46.2, blush: 46, bx1: 17, bx2: 47, top: 17 },
  pill: { x1: 25.5, x2: 38.5, y: 30, r: 3.3, mouth: 40.5, blush: 39, bx1: 21.5, bx2: 42.5, top: 10 },
};

export function BodyShape({ body, fill }: { body: string; fill: string }) {
  switch (body) {
    case "monitor":
      return (
        <g>
          <rect x="24" y="48" width="16" height="6" rx="3" fill="#0f2a33" opacity=".7" />
          <rect x="10" y="13" width="44" height="37" rx="11" fill={fill} />
          <rect x="15.5" y="18.5" width="33" height="25" rx="7" fill="#0e2b33" />
        </g>
      );
    case "planet":
      return <circle cx="32" cy="34" r="19" fill={fill} />;
    case "bean":
      return <path d="M32 17c11 0 18 9 18 20.5S43 55 32 55s-18-6.5-18-18S21 17 32 17z" fill={fill} />;
    case "envelope":
      return (
        <g>
          <rect x="9" y="17" width="46" height="36" rx="13" fill={fill} />
          <path d="M11.5 21.5 L32 33 L52.5 21.5" fill="#fff" fillOpacity=".25" stroke="#fff" strokeOpacity=".7" strokeWidth="2" strokeLinejoin="round" />
        </g>
      );
    case "pill":
      return <rect x="15" y="10" width="34" height="46" rx="17" fill={fill} />;
    default:
      return <path d="M32 14c12.4 0 20 8.6 20 20.4 0 11.4-7.4 18.3-20 18.3s-20-6.9-20-18.3C12 22.6 19.6 14 32 14z" fill={fill} />;
  }
}

// drawn behind the body (a ring's back half, a feather behind the head)
export function AccessoryBack({ accessory, f }: { accessory: string; f: Frame }) {
  if (accessory === "ring") return <path d="M5.5 37.5 Q32 22 58.5 30.5" fill="none" stroke="#fff" strokeOpacity=".45" strokeWidth="2.6" strokeLinecap="round" />;
  if (accessory === "feather") {
    return (
      <g className="quirk quill">
        <path d={`M46.5 ${f.top + 8.5}C48 ${f.top - 0.5} 53.5 ${f.top - 7} 60 ${f.top - 9.5}c-.6 6.8-5 13.2-12 19.6z`} fill="#cfe8ff" stroke="#8fbbe8" strokeWidth=".9" />
      </g>
    );
  }
  return null;
}

// drawn over the body and face
export function AccessoryFront({ accessory, f, mood }: { accessory: string; f: Frame; mood: string }) {
  const t = f.top;
  switch (accessory) {
    case "antenna":
      return (
        <g>
          <line x1="32" y1={t + 1} x2="32" y2={t - 5.5} stroke="#fff" strokeOpacity=".8" strokeWidth="2" strokeLinecap="round" />
          <circle className="quirk bulb" cx="32" cy={t - 7} r="3.2" fill="#ffd45c" />
        </g>
      );
    case "hat":
      return (
        <g>
          <ellipse cx="32" cy={t + 2} rx="19" ry="4.2" fill="#d9a94e" />
          <path d={`M20 ${t + 2} Q21 ${t - 9.5} 32 ${t - 9.5} Q43 ${t - 9.5} 44 ${t + 2} Z`} fill="#efc46d" />
          <rect x="20.4" y={t - 2} width="23.2" height="3.4" rx="1.7" fill="#8a5a2b" />
        </g>
      );
    case "crown":
      return (
        <g>
          <path d={`M21 ${t + 2} L22 ${t - 6} L27 ${t - 1} L32 ${t - 8} L37 ${t - 1} L42 ${t - 6} L43 ${t + 2} Z`} fill="#ffd45c" stroke="#e0a800" strokeWidth=".8" strokeLinejoin="round" />
          <circle cx="32" cy={t - 1.5} r="1.6" fill="#ff5c8a" />
        </g>
      );
    case "bow":
      return (
        <g fill="#ff5c8a">
          <path d={`M32 ${t + 1} L23 ${t - 4} Q21 ${t + 1} 23 ${t + 5} Z`} />
          <path d={`M32 ${t + 1} L41 ${t - 4} Q43 ${t + 1} 41 ${t + 5} Z`} />
          <circle cx="32" cy={t + 1} r="2.4" fill="#ff8fb3" />
        </g>
      );
    case "flower":
      return (
        <g transform={`translate(42 ${t + 2})`}>
          {[0, 72, 144, 216, 288].map((a) => <ellipse key={a} cx="0" cy="-3.4" rx="2.4" ry="3.4" fill="#fff" transform={`rotate(${a})`} />)}
          <circle r="2.2" fill="#ffd45c" />
        </g>
      );
    case "leaf":
      return (
        <g>
          <line x1="32" y1={t + 1} x2="32" y2={t - 5} stroke="#3aa65a" strokeWidth="1.6" strokeLinecap="round" />
          <path d={`M32 ${t - 4} q-7 -2 -8 -8 q7 0 8 8z`} fill="#5fd17a" />
          <path d={`M32 ${t - 5} q6 -3 9 -7 q-6 -1 -9 7z`} fill="#7be592" />
        </g>
      );
    case "headphones":
      return (
        <g>
          <path d={`M14 ${f.y + 2} Q14 ${t - 4} 32 ${t - 4} Q50 ${t - 4} 50 ${f.y + 2}`} fill="none" stroke="#2b3157" strokeWidth="3" strokeLinecap="round" />
          <rect x="10" y={f.y - 2} width="7" height="11" rx="3.5" fill="#5b6bff" />
          <rect x="47" y={f.y - 2} width="7" height="11" rx="3.5" fill="#5b6bff" />
        </g>
      );
    case "glasses":
      return (
        <g fill="none" stroke="#2b2416" strokeWidth="1.5" opacity=".85">
          <circle cx={f.x1} cy={f.y} r={f.r * 1.85} />
          <circle cx={f.x2} cy={f.y} r={f.r * 1.85} />
          <path d={`M${f.x1 + f.r * 1.85} ${f.y} H${f.x2 - f.r * 1.85}`} />
        </g>
      );
    case "monocle":
      return mood === "cheer" || mood === "sleep" || mood === "oops" ? null : (
        <g className="quirk monocle">
          <circle cx={f.x2} cy={f.y} r={f.r * 1.75} fill="none" stroke="#f6c453" strokeWidth="1.8" />
          <path d={`M${f.x2 + f.r * 1.6} ${f.y + 3} q3 4 0 9`} fill="none" stroke="#f6c453" strokeWidth="1.1" />
        </g>
      );
    case "ring":
      return <path d="M58.5 30.5 Q40 44 5.5 37.5" fill="none" stroke="#fff" strokeOpacity=".9" strokeWidth="2.6" strokeLinecap="round" />;
    default:
      return null;
  }
}
