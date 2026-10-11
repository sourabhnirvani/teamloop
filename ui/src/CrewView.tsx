import { lazy, Suspense } from "react";
import type { Bot } from "./api";
import { Avatar, botColor, type Move } from "./Avatar";
import type { Handoff } from "./CrewRoom";

// three.js only loads when someone opens this tab, so the chat app stays small on phones
const CrewRoom = lazy(() => import("./CrewRoom").then((m) => ({ default: m.CrewRoom })));

export function CrewView({ bots, moves, look, working, asking, handoff, onBot }: {
  bots: Bot[]; moves: Record<string, Move>; look: (id: string) => { move: Move; sign: string | null };
  working: string[]; asking: string[]; handoff: Handoff | null; onBot: (id: string) => void;
}) {
  const status = (id: string) => (asking.includes(id) ? "waiting for your OK" : working.includes(id) ? "working…" : "free");
  return (
    <div className="crew-page">
      <div className="crew-stage">
        <div className="room-head"><b>Crew Room</b><small>{working.length ? `${working.length} working` : asking.length ? "waiting for you" : "all free"} · tap a bot</small></div>
        <Suspense fallback={<div className="room room-loading">Opening the Crew Room…</div>}>
          <CrewRoom bots={bots} moves={moves} working={working} asking={asking} handoff={handoff} onPick={onBot} height="100%" />
        </Suspense>
      </div>
      <div className="crew-strip">
        {bots.map((b) => (
          <button key={b.id} className={`crew-card ${asking.includes(b.id) ? "ask" : working.includes(b.id) ? "busy" : ""}`}
                  style={{ "--bot": botColor(b.id) } as React.CSSProperties} onClick={() => onBot(b.id)}>
            <Avatar bot={b} {...look(b.id)} size={42} />
            <span><b>{b.name}</b><small>{b.role} · {status(b.id)}</small></span>
          </button>
        ))}
      </div>
    </div>
  );
}
