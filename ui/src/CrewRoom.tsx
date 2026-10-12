import { useEffect, useRef, useState } from "react";
import type { Bot } from "./api";
import { Avatar, mascotSrc, S_FRAMES, Sign, type Move } from "./Avatar";
import { Icon } from "./Icon";
import "./hoodie-crew.css";

// The Crew Room: one flat room. S stands in the middle of the floor; the others sit at their desks either side, two
// rows deep. Each bot's tag says whether it needs your OK, is working, is done or is free; a sign over its head says
// what it is doing. A hand-off makes the sender hop and the teammate catch it. Tap a bot to open it.

export type Handoff = { from: string; to: string; key: number };
export type TodayJob = { title: string; done: number; total: number };

type Props = {
  bots: Bot[];
  moves: Record<string, Move>;
  working: string[];
  asking: string[];
  handoff: Handoff | null;
  signs?: Record<string, string | null>; // the same signs the chats show (Icon names)
  onPick?: (botId: string) => void;
  height?: number | string;
  job?: TodayJob | null; // the running (or latest) job: shown on the wall card, left out when there is none
};

// x (percent of the room) and row for each bot beside S: split left and right, the outermost seat on each side in
// the front row, then alternating rows inward
function seats(n: number): { x: number; back: boolean }[] {
  const left = Math.ceil(n / 2), right = n - left;
  const side = (k: number, from: number, to: number) => Array.from({ length: k }, (_, i) => from + ((i + 0.5) * (to - from)) / k);
  return [
    ...side(left, 4, 38).map((x, i) => ({ x, back: i % 2 === 1 })),
    ...side(right, 64, 96).map((x, i) => ({ x, back: (right - 1 - i) % 2 === 1 })),
  ];
}

type Status = "ask" | "busy" | "done" | "free";
const SAYS: Record<Status, string> = { ask: "needs your OK", busy: "working", done: "done", free: "free" };

export function CrewRoom({ bots, moves, working, asking, handoff, signs, onPick, height = 300, job }: Props) {
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
    const status: Status = asking.includes(id) || move === "ask" ? "ask"
      : working.includes(id) || move === "think" ? "busy" : move === "cheer" ? "done" : "free";
    return { move, status, sign: signs?.[id] ?? (status === "ask" ? "ask" : null) };
  };
  const tag = (status: Status, lead = false) => (
    <span className={`hd-tag ${status}${lead ? " lead" : ""}`}>
      {status === "done" && <Icon name="ok" size={14} />}{SAYS[status]}
    </span>
  );
  const fx = (id: string) => (hop?.from === id ? " hd-hop" : hop?.to === id ? " hd-catch" : "");

  const lead = bots.find((b) => b.id === "s");
  const others = bots.filter((b) => b !== lead);
  const spots = seats(others.length);
  const pct = job && job.total > 0 ? Math.min(100, Math.round((job.done / job.total) * 100)) : 0;

  return (
    <section className="room hd-room" style={{ "--room-h": typeof height === "number" ? `${height}px` : height } as React.CSSProperties}
             aria-label="The Crew Room: the bots at work">
      <div className="hd-floor" aria-hidden="true" />
      {job && (
        <div className="hd-job">
          <span className="hd-job-k">TODAY'S JOB</span>
          <b>{job.title}{job.total > 0 && ` · ${job.done} of ${job.total} done`}</b>
          {job.total > 0 && <span className="hd-job-bar" aria-hidden="true"><i style={{ width: `${pct}%` }} /></span>}
        </div>
      )}
      <span className="hd-spark a" aria-hidden="true"><Icon name="spark" size={22} /></span>
      <span className="hd-spark b" aria-hidden="true"><Icon name="spark" size={14} /></span>
      {lead && (() => {
        const { move, status, sign } = state(lead.id);
        const frame = hop?.from === lead.id ? "handoff" : S_FRAMES[move] ?? "idle";
        return (
          <button className={`hd-bot hd-lead${fx(lead.id)}`} onClick={() => onPick?.(lead.id)} aria-label={`${lead.name}, ${SAYS[status]}`}>
            {tag(status, true)}
            <span className="hd-figure">
              <img src={mascotSrc(frame)} alt="" width={180} height={240} draggable={false} />
              {sign && <Sign key={sign} name={sign} size={20} />}
            </span>
            <b className="hd-name">{lead.name}{lead.role ? ` · ${lead.role}` : ""}</b>
          </button>
        );
      })()}
      <div className="hd-others">
        {others.map((b, i) => {
          const { move, status, sign } = state(b.id);
          return (
            <button key={b.id} className={`hd-bot${spots[i].back ? " back" : " front"}${fx(b.id)}`} style={{ left: `${spots[i].x}%` }}
                    onClick={() => onPick?.(b.id)} aria-label={`${b.name}, ${SAYS[status]}`}>
              {tag(status)}
              <Avatar bot={b} move={move} size={100} sign={sign} />
              <span className="hd-desk" aria-hidden="true" />
              <b className="hd-name">{b.name}</b>
            </button>
          );
        })}
      </div>
    </section>
  );
}
