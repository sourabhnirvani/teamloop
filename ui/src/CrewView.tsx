import type { Bot } from "./api";
import { Avatar, botColor, type Move } from "./Avatar";
import { CrewRoom, type Handoff, type TodayJob } from "./CrewRoom";
import { go, href } from "./router";
import "./hoodie-crew.css";

export function CrewView({ bots, moves, look, working, asking, handoff, onBot, job, onAsk }: {
  bots: Bot[]; moves: Record<string, Move>; look: (id: string) => { move: Move; sign: string | null };
  working: string[]; asking: string[]; handoff: Handoff | null; onBot: (id: string) => void;
  job?: TodayJob | null; // the running or latest job, when the caller has one
  onAsk?: (botId: string) => void; // open the chat where that bot waits for your OK
}) {
  const done = (id: string) => (moves[id] ?? "idle") === "cheer";
  const status = (id: string) => (asking.includes(id) ? "waiting for your OK" : working.includes(id) ? "working…" : done(id) ? "done" : "free");
  const counts = { wait: 0, work: 0, done: 0, free: 0 };
  for (const b of bots) {
    if (asking.includes(b.id)) counts.wait++;
    else if (working.includes(b.id)) counts.work++;
    else if (done(b.id)) counts.done++;
    else counts.free++;
  }
  const line = [
    counts.wait && `${counts.wait} waiting for you`, counts.work && `${counts.work} working`,
    counts.done && `${counts.done} done`, counts.free && `${counts.free} free`, "tap a bot",
  ].filter(Boolean).join(" · ");
  const waiting = bots.find((b) => asking.includes(b.id));
  const openAsk = (id: string) => (onAsk ? onAsk(id) : go(href("chats", `dm-${id}`)));

  return (
    <div className="crew-page hd-crew-page">
      <header className="hd-crew-head">
        <div>
          <h1>Crew Room</h1>
          <div className="hd-crew-line">{line}</div>
        </div>
        {waiting && <button className="hd-ok-btn" onClick={() => openAsk(waiting.id)}>{waiting.name} needs your OK</button>}
      </header>
      <CrewRoom bots={bots} moves={moves} working={working} asking={asking} handoff={handoff} onPick={onBot} height={440} job={job}
                signs={Object.fromEntries(bots.map((b) => [b.id, look(b.id).sign]))} />
      <section className="hd-cards" aria-label="Crew">
        {bots.map((b) => (
          <button key={b.id} className={`hd-card${asking.includes(b.id) ? " ask" : working.includes(b.id) ? " busy" : ""}`}
                  style={{ "--bot": botColor(b.id) } as React.CSSProperties} onClick={() => onBot(b.id)}>
            <Avatar bot={b} {...look(b.id)} size={52} />
            <span><b>{b.name}</b><small>{b.role ? `${b.role} · ` : ""}{status(b.id)}</small></span>
          </button>
        ))}
      </section>
    </div>
  );
}
