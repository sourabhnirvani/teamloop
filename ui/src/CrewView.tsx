import type { Bot } from "./api";
import { Avatar, botColor, type Move } from "./Avatar";
import { CrewRoom, type Handoff } from "./CrewRoom";
import "./hoodie-crew.css";

export function CrewView({ bots, moves, look, working, asking, handoff, onBot }: {
  bots: Bot[]; moves: Record<string, Move>; look: (id: string) => { move: Move; sign: string | null };
  working: string[]; asking: string[]; handoff: Handoff | null; onBot: (id: string) => void;
}) {
  const status = (id: string) => (asking.includes(id) ? "waiting for your OK" : working.includes(id) ? "working…" : "free");
  return (
    <div className="crew-page hd-crew-page">
      <div className="crew-stage hd-stage">
        <div className="room-head"><b>Crew Room</b><small>{working.length ? `${working.length} working` : asking.length ? "waiting for you" : "all free"} · tap a bot</small></div>
        <CrewRoom bots={bots} moves={moves} working={working} asking={asking} handoff={handoff} onPick={onBot} height={440}
                  signs={Object.fromEntries(bots.map((b) => [b.id, look(b.id).sign]))} />
      </div>
      <div className="crew-strip hd-strip">
        {bots.map((b) => (
          <button key={b.id} className={`crew-card ${asking.includes(b.id) ? "ask" : working.includes(b.id) ? "busy" : ""}`}
                  style={{ "--bot": botColor(b.id) } as React.CSSProperties} onClick={() => onBot(b.id)}>
            <Avatar bot={b} {...look(b.id)} size={52} />
            <span><b>{b.name}</b><small><span className="crew-role">{b.role} · </span>{status(b.id)}</small></span>
          </button>
        ))}
      </div>
    </div>
  );
}
