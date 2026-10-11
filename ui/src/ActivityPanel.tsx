import { useEffect, useState } from "react";
import { api, type Bot, type Chat, type Routine } from "./api";
import { Avatar, botColor, type Move } from "./Avatar";
import type { Item } from "./ChatView";

// What the crew is doing, at a glance: cards waiting for your OK, who is working on what right now,
// what's scheduled, what just finished, and today's (free) model use.

type Props = {
  bots: Record<string, Bot>;
  chats: Chat[];
  items: Record<string, Item[]>;
  typing: Record<string, string[]>;
  moves: Record<string, Move>;
  usage: { req: number; tok: number };
  onOpenChat: (chatId: string) => void;
  onOpenBot: (botId: string) => void;
};

export function ActivityPanel({ bots, chats, items, typing, moves, usage, onOpenChat, onOpenBot }: Props) {
  const [routines, setRoutines] = useState<Routine[]>([]);
  useEffect(() => {
    const load = () => api.routines().then(setRoutines).catch(() => {});
    load();
    const t = window.setInterval(load, 30000);
    return () => window.clearInterval(t);
  }, []);

  const title = (id: string) => chats.find((c) => c.id === id)?.title ?? id;
  const waiting = Object.entries(items).flatMap(([chat, list]) =>
    list.filter((i): i is Extract<Item, { kind: "approval" }> => i.kind === "approval" && !i.status).map((i) => ({ chat, i })));
  const now = Object.entries(typing).flatMap(([chat, ids]) => ids.map((id) => {
    const steps = (items[chat] ?? []).filter((i): i is Extract<Item, { kind: "step" }> => i.kind === "step" && i.bot === id);
    const last = steps[steps.length - 1];
    return { chat, id, doing: last ? (last.status === "start" ? `using ${last.tool}…` : last.text ?? last.tool) : "thinking…" };
  }));
  const done = Object.entries(items).flatMap(([chat, list]) =>
    list.filter((i): i is Extract<Item, { kind: "step" }> => i.kind === "step" && i.status !== "start").map((i) => ({ chat, i })))
    .slice(-6).reverse();

  return (
    <div className="activity-panel">
      <section>
        <h3>Waiting for you {waiting.length > 0 && <span className="count warn">{waiting.length}</span>}</h3>
        {waiting.length === 0 && <p className="quiet">Nothing needs your OK.</p>}
        {waiting.map(({ chat, i }) => (
          <div key={i.key} className="card ask" style={{ "--bot": botColor(i.bot) } as React.CSSProperties}>
            <div className="card-head" onClick={() => onOpenChat(chat)}>
              <Avatar bot={bots[i.bot]} move="ask" size={26} />
              <span><b>{bots[i.bot]?.name}</b> · {i.title}<small>{title(chat)}</small></span>
            </div>
            <p>{i.details}</p>
            <div className="card-btns">
              <button className="primary" onClick={() => api.answer(i.id, true)}>Approve</button>
              <button className="deny" onClick={() => api.answer(i.id, false)}>Deny</button>
            </div>
          </div>
        ))}
      </section>

      <section>
        <h3>Working now {now.length > 0 && <span className="count">{now.length}</span>}</h3>
        {now.length === 0 && <p className="quiet">The crew is free. Ask for something.</p>}
        {now.map(({ chat, id, doing }) => (
          <button key={chat + id} className="line" onClick={() => onOpenChat(chat)} style={{ "--bot": botColor(id) } as React.CSSProperties}>
            <Avatar bot={bots[id]} move={moves[id] ?? "think"} size={26} />
            <span><b>{bots[id]?.name}</b> {doing}<small>{title(chat)}</small></span>
            <i className="pulse" />
          </button>
        ))}
      </section>

      <section>
        <h3>Scheduled {routines.length > 0 && <span className="count">{routines.length}</span>}</h3>
        {routines.length === 0 && <p className="quiet">No routines yet. Try “every Monday at 9am…”.</p>}
        {routines.slice(0, 5).map((r) => (
          <button key={r.id} className="line" onClick={() => onOpenChat(r.chat_id)}>
            <span className="clock">⏰</span>
            <span>{r.text}<small>{r.schedule} · next {new Date(r.next_run * 1000).toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit" })}</small></span>
          </button>
        ))}
      </section>

      <section>
        <h3>Just done</h3>
        {done.length === 0 && <p className="quiet">Finished steps show up here.</p>}
        {done.map(({ chat, i }) => (
          <button key={i.key} className={`line step-line ${i.status}`} onClick={() => onOpenChat(chat)}>
            <span className="mark">{i.status === "done" ? "✓" : "✗"}</span>
            <span><b style={{ color: botColor(i.bot) }}>{bots[i.bot]?.name}</b> <code>{i.tool}</code><small>{i.text}</small></span>
          </button>
        ))}
      </section>

      <section className="usage-box">
        <div><b>{usage.req}</b><small>model calls today</small></div>
        <div><b>{usage.tok >= 1000 ? `${(usage.tok / 1000).toFixed(1)}k` : usage.tok}</b><small>tokens</small></div>
        <div><b className="free">$0</b><small>free models only</small></div>
      </section>
      <button className="line" onClick={() => onOpenBot("s")}><span className="clock">ℹ</span><span>Meet the crew<small>who does what, and what each bot may do</small></span></button>
    </div>
  );
}

export const RULES: Record<string, { alone: string[]; asks: string[]; never: string[] }> = {
  s: { alone: ["plan jobs and hand steps to teammates", "remember things you tell it", "set routines"],
    asks: ["anything risky goes through the teammate's card"], never: ["approve its own cards"] },
  desk: { alone: ["open apps and files you name", "volume, brightness, Wi-Fi on", "read the screen", "run safe commands"],
    asks: ["close apps", "delete, kill processes, registry, services", "lock, sleep, restart, Wi-Fi off", "open a file"],
    never: ["Windows-key shortcuts or Enter in a terminal", "type passwords, card numbers or codes", "touch TeamLoop's own window"] },
  web: { alone: ["open and read pages", "click links, type in search boxes"],
    asks: ["send, post, buy, submit a form", "checkout pages, local-network pages"],
    never: ["type passwords or card numbers", "upload files, download files"] },
  scout: { alone: ["search the web", "read pages and summarise with links"], asks: [], never: ["act as you anywhere"] },
  inbox: { alone: ["read, sort and summarise email", "draft replies"], asks: ["send anything"], never: ["type passwords"] },
  writer: { alone: ["write new files on Desktop, Documents, Downloads", "notes, reports, messages"],
    asks: ["replace an existing file"], never: ["write outside those folders"] },
};

export function BotProfile({ bot, bots, chats, typing, onChat, onClose }: {
  bot: Bot; bots: Record<string, Bot>; chats: Chat[]; typing: Record<string, string[]>;
  onChat: (chatId: string) => void; onClose: () => void;
}) {
  const [routines, setRoutines] = useState<Routine[]>([]);
  useEffect(() => { api.routines().then(setRoutines).catch(() => {}); }, []);
  const rules = RULES[bot.id] ?? { alone: [], asks: [], never: [] };
  const busyIn = Object.entries(typing).filter(([, ids]) => ids.includes(bot.id)).map(([c]) => c);
  const dm = chats.find((c) => c.members.length === 1 && c.members[0] === bot.id);
  const mine = routines.filter((r) => r.chat_id === dm?.id);
  const others = Object.values(bots);
  return (
    <div className="overlay" onClick={onClose}>
      <div className="profile" onClick={(e) => e.stopPropagation()} style={{ "--bot": botColor(bot.id) } as React.CSSProperties}>
        <button className="icon close" onClick={onClose} aria-label="Close">✕</button>
        <div className="profile-hero">
          <Avatar bot={bot} move={busyIn.length ? "think" : "cheer"} size={112} />
          <div>
            <h2>{bot.name}</h2>
            <div className="role">{bot.role}</div>
            <div className="model">model: {bot.model === "auto" ? "best free model available" : bot.model}</div>
            <div className={`state ${busyIn.length ? "busy" : ""}`}>{busyIn.length ? `working in ${busyIn.length} chat${busyIn.length > 1 ? "s" : ""}` : "free"}</div>
          </div>
        </div>
        <div className="rules">
          <div><h4>On its own</h4><ul>{rules.alone.map((r) => <li key={r}>{r}</li>)}</ul></div>
          <div><h4>Asks you first</h4><ul>{rules.asks.length ? rules.asks.map((r) => <li key={r}>{r}</li>) : <li className="quiet">nothing it does needs your OK</li>}</ul></div>
          <div><h4>Never</h4><ul>{rules.never.map((r) => <li key={r}>{r}</li>)}</ul></div>
        </div>
        {mine.length > 0 && (
          <div className="profile-sched"><h4>Scheduled</h4>{mine.map((r) => <div key={r.id}>⏰ {r.text} <small>({r.schedule})</small></div>)}</div>
        )}
        <div className="profile-crew">
          {others.map((b) => (
            <button key={b.id} className={b.id === bot.id ? "on" : ""} title={b.name} onClick={(e) => { e.stopPropagation(); onChat(`__profile:${b.id}`); }}>
              <Avatar bot={b} size={34} />
            </button>
          ))}
        </div>
        {dm && <button className="primary wide" onClick={() => onChat(dm.id)}>Chat with {bot.name}</button>}
      </div>
    </div>
  );
}
