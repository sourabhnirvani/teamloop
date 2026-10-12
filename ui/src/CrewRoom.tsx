import { useEffect, useRef, useState } from "react";
import type { Bot } from "./api";
import { Avatar, mascotSrc, S_FRAMES, Sign, type Move } from "./Avatar";
import { Icon } from "./Icon";
import "./hoodie-crew.css";

// The Crew Room: one flat room. S stands in the middle of the floor; the others sit at their desks either side, two
// rows deep. Each bot's tag says whether it is working or needs your OK; a sign over its head says what it is doing.
// A hand-off makes the sender hop and the teammate catch it. Tap a bot to open it.

export type Handoff = { from: string; to: string; key: number };

type Props = {
  bots: Bot[];
  moves: Record<string, Move>;
  working: string[];
  asking: string[];
  handoff: Handoff | null;
  signs?: Record<string, string | null>; // the same signs the chats show (Icon names)
  onPick?: (botId: string) => void;
  height?: number | string;
};

// x (percent of the room) and row for each bot beside S: split left and right, alternating rows outward
function seats(n: number): { x: number; back: boolean }[] {
  const left = Math.ceil(n / 2), right = n - left;
  const side = (k: number, from: number, to: number) => Array.from({ length: k }, (_, i) => from + ((i + 0.5) * (to - from)) / k);
  return [
    ...side(left, 5, 37).map((x, i) => ({ x, back: (left - 1 - i) % 2 === 1 })),
    ...side(right, 63, 95).map((x, i) => ({ x, back: i % 2 === 1 })),
  ];
}

export function CrewRoom({ bots, moves, working, asking, handoff, signs, onPick, height = 300 }: Props) {
  const openedAt = useRef(Date.now());
  const [hop, setHop] = useState<Handoff | null>(null);
  useEffect(() => {
    if (!handoff || handoff.key < openedAt.current) return; // not old ones when the tab opens
    setHop(handoff);
    const t = setTimeout(() => setHop(null), 900);
    return () => clearTimeout(t);
  }, [handoff]);

  const state = (id: string) => {
    const move = moves[id] ?? "idle";
    const busy = working.includes(id) || move === "think";
    const asks = asking.includes(id) || move === "ask";
    return { move, busy, asks, sign: signs?.[id] ?? (asks ? "ask" : null) };
  };
  const tag = (busy: boolean, asks: boolean) => (
    <span className={`hd-tag${asks ? " ask" : busy ? " busy" : " idle"}`}>{asks ? "needs your OK" : busy ? "working…" : "say hi"}</span>
  );
  const fx = (id: string) => (hop?.from === id ? " hd-hop" : hop?.to === id ? " hd-catch" : "");

  const lead = bots.find((b) => b.id === "s");
  const others = bots.filter((b) => b !== lead);
  const spots = seats(others.length);

  return (
    <div className="room hd-room" style={{ "--room-h": typeof height === "number" ? `${height}px` : height } as React.CSSProperties}
         aria-label="The Crew Room: the bots at work">
      <div className="hd-floor" aria-hidden="true" />
      <span className="hd-spark a" aria-hidden="true"><Icon name="spark" size={18} /></span>
      <span className="hd-spark b" aria-hidden="true"><Icon name="spark" size={12} /></span>
      {lead && (() => {
        const { move, busy, asks, sign } = state(lead.id);
        const frame = hop?.from === lead.id ? "handoff" : S_FRAMES[move] ?? "idle";
        return (
          <button className={`hd-bot hd-lead${fx(lead.id)}`} onClick={() => onPick?.(lead.id)}
                  aria-label={`${lead.name}, ${asks ? "needs your OK" : busy ? "working" : "free"}`}>
            {tag(busy, asks)}
            <span className="hd-figure">
              <img src={mascotSrc(frame)} alt="" width={180} height={240} draggable={false} />
              {sign && <Sign key={sign} name={sign} size={20} />}
            </span>
            <b className="hd-name">{lead.name}</b>
          </button>
        );
      })()}
      <div className="hd-others">
        {others.map((b, i) => {
          const { move, busy, asks, sign } = state(b.id);
          return (
            <button key={b.id} className={`hd-bot${spots[i].back ? " back" : " front"}${fx(b.id)}`} style={{ left: `${spots[i].x}%` }}
                    onClick={() => onPick?.(b.id)} aria-label={`${b.name}, ${asks ? "needs your OK" : busy ? "working" : "free"}`}>
              {tag(busy, asks)}
              <Avatar bot={b} move={move} size={100} sign={sign} />
              <span className="hd-desk" aria-hidden="true" />
              <b className="hd-name">{b.name}</b>
            </button>
          );
        })}
      </div>
    </div>
  );
}
