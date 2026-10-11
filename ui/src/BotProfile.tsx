import { useEffect, useState } from "react";
import { api, type Bot, type Chat, type Routine } from "./api";
import { Avatar, botColor } from "./Avatar";

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
