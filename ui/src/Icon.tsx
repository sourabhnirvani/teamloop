import type { ReactElement } from "react";

// Line icons drawn for TeamLoop (24px grid, 1.8 stroke, round ends). They replace every emoji and stock glyph in
// the UI, so the app looks the same on every OS. Colour comes from `currentColor`.
const S = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round" } as const;

const PATHS: Record<string, ReactElement> = {
  chat: <path {...S} d="M5 6.5A2.5 2.5 0 0 1 7.5 4h9A2.5 2.5 0 0 1 19 6.5v6a2.5 2.5 0 0 1-2.5 2.5H11l-4 3.5V15A2.5 2.5 0 0 1 5 12.5z" />,
  crew: <><path {...S} d="M5.5 20C4.4 17.8 4.2 15 5 12.5 6.3 8.6 9.2 6.5 12.5 6.5c1.5-1.6 3.4-2.6 5.6-3-.6 1.2-.9 2.6-.7 4 2.4 2 3.6 4.9 3.3 8.1-.2 1.8-.8 3.2-1.5 4.4z" /><ellipse {...S} strokeWidth={1.6} cx="12.3" cy="15.2" rx="3.3" ry="2.6" /></>,
  board: <path {...S} d="M4.5 5.5h15v13h-15z M9.5 5.5v13 M14.5 5.5v13" />,
  jobs: <path {...S} d="M4.5 5.5h15v13h-15z M8 10l2.5 2L8 14 M12.5 14.5h3.5" />,
  settings: <><path {...S} d="M4 7h3 M11 7h9 M4 12h9 M17 12h3 M4 17h1 M9 17h11" /><circle {...S} cx="9" cy="7" r="2" /><circle {...S} cx="15" cy="12" r="2" /><circle {...S} cx="7" cy="17" r="2" /></>,
  send: <path {...S} strokeWidth={1.9} d="M5 12h12 M12.5 7l5 5-5 5" />,
  stop: <rect {...S} x="7" y="7" width="10" height="10" rx="2.2" />,
  add: <path {...S} strokeWidth={1.9} d="M12 6v12 M6 12h12" />,
  ok: <path {...S} strokeWidth={2.2} d="M6 12.5l4 4 8-9" />,
  no: <path {...S} strokeWidth={2} d="M7.5 7.5l9 9 M16.5 7.5l-9 9" />,
  routine: <><circle {...S} cx="12" cy="13" r="7" /><path {...S} d="M12 9.5V13l2.5 1.6 M9.5 3.5h5" /></>,
  phone: <path {...S} d="M8.5 3.5h7a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2h-7a2 2 0 0 1-2-2v-13a2 2 0 0 1 2-2z M11 17.5h2" />,
  key: <><circle {...S} cx="8.5" cy="15.5" r="3.5" /><path {...S} d="M11 13L19 5 M15.5 8.5l2 2 M13.5 10.5l1.3 1.3" /></>,
  model: <><rect {...S} x="7" y="7" width="10" height="10" rx="2" /><path {...S} strokeWidth={1.6} d="M10 4v3 M14 4v3 M10 17v3 M14 17v3 M4 10h3 M4 14h3 M17 10h3 M17 14h3" /></>,
  shield: <path {...S} d="M12 3.5l7 2.6v5.4c0 4.4-2.9 7.5-7 9-4.1-1.5-7-4.6-7-9V6.1z M9 12l2.2 2.2L15.3 10" />,
  search: <><circle {...S} cx="10.5" cy="10.5" r="5.5" /><path {...S} strokeWidth={1.9} d="M15 15l4.5 4.5" /></>,
  file: <path {...S} d="M7 3.5h6.5L18 8v12.5H7z M13.5 3.5V8H18 M9.5 12.5h6 M9.5 16h4" />,
  mouse: <path {...S} d="M12 3.5a5.5 5.5 0 0 1 5.5 5.5v6a5.5 5.5 0 0 1-11 0V9A5.5 5.5 0 0 1 12 3.5z M12 7v3" />,
  globe: <><circle {...S} cx="12" cy="12" r="8" /><path {...S} strokeWidth={1.6} d="M4 12h16 M12 4c2.4 2.4 3.4 5 3.4 8s-1 5.6-3.4 8c-2.4-2.4-3.4-5-3.4-8s1-5.6 3.4-8z" /></>,
  trace: <path {...S} d="M3.5 12h4l2-5 4 10 2-5h5" />,
  lock: <><rect {...S} x="6" y="11" width="12" height="9" rx="2" /><path {...S} d="M9 11V8.5a3 3 0 0 1 6 0V11" /></>,
  spark: <path fill="currentColor" d="M12 3.5c.7 4.3 2.2 5.8 6.5 6.5-4.3.7-5.8 2.2-6.5 6.5-.7-4.3-2.2-5.8-6.5-6.5 4.3-.7 5.8-2.2 6.5-6.5z" />,
  back: <path {...S} strokeWidth={2} d="M14.5 6l-6 6 6 6" />,
  next: <path {...S} strokeWidth={2} d="M9.5 6l6 6-6 6" />,
  down: <path {...S} strokeWidth={2} d="M6 9.5l6 6 6-6" />,
  arrow: <path {...S} d="M4 12h14 M13.5 7.5L18 12l-4.5 4.5" />,
  retry: <path {...S} d="M5 12a7 7 0 1 0 2.1-5 M5 4.5V8h3.5" />,
  ask: <><circle {...S} cx="12" cy="12" r="7.5" /><path {...S} strokeWidth={1.9} d="M12 8v4.5 M12 15.5v.5" /></>,
  warn: <path {...S} d="M12 4.5l8.5 15h-17z M12 10v4 M12 16.8v.2" />,
  look: <><path {...S} d="M12 4a8 8 0 1 0 0 16c1.3 0 1.8-.9 1.3-1.8-.6-1.1.2-2.4 1.5-2.4H17a3 3 0 0 0 3-3C20 7.6 16.4 4 12 4z" /><circle fill="currentColor" cx="8.5" cy="11" r="1.2" /><circle fill="currentColor" cx="12" cy="8" r="1.2" /><circle fill="currentColor" cx="15.5" cy="10" r="1.2" /></>,
  mute: <path {...S} d="M6.5 16.5h11c-1.2-1.3-1.8-2.8-1.8-5V10a3.7 3.7 0 0 0-7.4 0v1.5c0 2.2-.6 3.7-1.8 5z M10.5 19.5h3 M4.5 4.5l15 15" />,
  bell: <path {...S} d="M6.5 16.5h11c-1.2-1.3-1.8-2.8-1.8-5V10a3.7 3.7 0 0 0-7.4 0v1.5c0 2.2-.6 3.7-1.8 5z M10.5 19.5h3" />,
  dice: <><rect {...S} x="4.5" y="4.5" width="15" height="15" rx="3.5" /><circle fill="currentColor" cx="9" cy="9" r="1.3" /><circle fill="currentColor" cx="15" cy="15" r="1.3" /><circle fill="currentColor" cx="12" cy="12" r="1.3" /></>,
  usage: <path {...S} strokeWidth={1.9} d="M5 19.5V13 M10 19.5V8 M15 19.5v-9 M20 19.5V5" />,
  plane: <path {...S} d="M4 11.5l15.5-6.5-4.5 14-3.5-5.5z M11.5 13.5L19.5 5" />,
  moon: <path {...S} d="M19 14.5A7.5 7.5 0 0 1 9.5 5a7.5 7.5 0 1 0 9.5 9.5z" />,
  sun: <><circle {...S} cx="12" cy="12" r="3.8" /><path {...S} d="M12 3.5v2 M12 18.5v2 M3.5 12h2 M18.5 12h2 M6 6l1.4 1.4 M16.6 16.6L18 18 M6 18l1.4-1.4 M16.6 7.4L18 6" /></>,
  pause: <path {...S} strokeWidth={2} d="M9 6.5v11 M15 6.5v11" />,
  bolt: <path {...S} d="M13 3.5L6 13.5h5.5L10.5 20.5 18 10h-5.5z" />,
  type: <><rect {...S} x="3.5" y="7" width="17" height="10" rx="2" /><path {...S} d="M7 10.5h.5 M10 10.5h.5 M13 10.5h.5 M16 10.5h.5 M8 13.5h8" /></>,
  screen: <><rect {...S} x="3.5" y="5" width="17" height="11" rx="2" /><path {...S} d="M9 19.5h6 M12 16v3.5" /></>,
  camera: <><path {...S} d="M4 8.5A1.5 1.5 0 0 1 5.5 7h2.3L9.5 5h5l1.7 2h2.3A1.5 1.5 0 0 1 20 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5z" /><circle {...S} cx="12" cy="13" r="3.2" /></>,
  sound: <path {...S} d="M5 10v4h3l4 3.5v-11L8 10z M15.5 9.5a3.5 3.5 0 0 1 0 5 M17.8 7.2a6.8 6.8 0 0 1 0 9.6" />,
  wifi: <path {...S} d="M4.5 10a11 11 0 0 1 15 0 M7.3 13a7 7 0 0 1 9.4 0 M10.2 16a3 3 0 0 1 3.6 0 M12 18.8v.2" />,
  battery: <><rect {...S} x="3.5" y="8" width="15" height="8" rx="2" /><path {...S} d="M20.5 11v2 M6.5 11v2" /></>,
  mail: <><rect {...S} x="4" y="6" width="16" height="12" rx="2" /><path {...S} d="M4.5 7.5l7.5 6 7.5-6" /></>,
  brain: <path {...S} d="M9 5.5a3 3 0 0 0-3 3 3 3 0 0 0-1.5 5.5A3 3 0 0 0 9 18.5h.5V5.5z M15 5.5a3 3 0 0 1 3 3 3 3 0 0 1 1.5 5.5A3 3 0 0 1 15 18.5h-.5V5.5z" />,
  pen: <path {...S} d="M5 19l1-4L16 5l3 3L9 18z M14 7l3 3" />,
  pointer: <path {...S} d="M7 4.5l10 7-4.5 1 2.5 5-2 1-2.5-5L7 16z" />,
  dots: <><circle fill="currentColor" cx="6.5" cy="12" r="1.5" /><circle fill="currentColor" cx="12" cy="12" r="1.5" /><circle fill="currentColor" cx="17.5" cy="12" r="1.5" /></>,
  tool: <path {...S} d="M14.5 5.5a4 4 0 0 0-5 5L4.5 15.5l4 4 5-5a4 4 0 0 0 5-5l-2.5 2.5-2.5-.5-.5-2.5z" />,
};

export type IconName = keyof typeof PATHS;
export const ICON_NAMES = Object.keys(PATHS) as IconName[];

export function Icon({ name, size = 18, className, label }: { name: IconName; size?: number; className?: string; label?: string }) {
  return (
    <svg className={className ? `icon ${className}` : "icon"} width={size} height={size} viewBox="0 0 24 24"
      role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      {PATHS[name] ?? PATHS.tool}
    </svg>
  );
}
