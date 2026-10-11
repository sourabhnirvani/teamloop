import { useCallback, useEffect, useRef, useState } from "react";
import { api, listen, type Bot, type Chat, type Message, type ServerEvent } from "./api";
import { Avatar, type Move } from "./Avatar";
import { ChatView, type Item } from "./ChatView";
import { SettingsPanel } from "./SettingsPanel";

const msgItem = (m: Message): Item => ({ kind: "msg", key: `m${m.id}`, sender: m.sender, text: m.text, mkind: m.kind, ts: m.ts });

export default function App() {
  const [bots, setBots] = useState<Record<string, Bot>>({});
  const [chats, setChats] = useState<Chat[]>([]);
  const [active, setActive] = useState<string>("team");
  const [items, setItems] = useState<Record<string, Item[]>>({});
  const [typing, setTyping] = useState<Record<string, string[]>>({});
  const [unread, setUnread] = useState<Record<string, number>>({});
  const [moves, setMoves] = useState<Record<string, Move>>({});
  const [live, setLive] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const activeRef = useRef(active);
  const timers = useRef<Record<string, number>>({});
  activeRef.current = active;

  const move = useCallback((bot: string, m: Move, ms = 1400) => {
    setMoves((all) => ({ ...all, [bot]: m }));
    window.clearTimeout(timers.current[bot]);
    if (m !== "think" && m !== "ask") {
      timers.current[bot] = window.setTimeout(() => setMoves((all) => ({ ...all, [bot]: "idle" })), ms);
    }
  }, []);

  const loadChats = useCallback(async () => {
    const [b, c] = await Promise.all([api.bots(), api.chats()]);
    setBots(Object.fromEntries(b.map((x) => [x.id, x])));
    setChats(c);
  }, []);

  useEffect(() => {
    loadChats().catch(() => setLive(false));
  }, [loadChats]);

  // Today's model calls: loaded once, then counted live from usage events, so free-tier use stays visible.
  const [usage, setUsage] = useState({ req: 0, tok: 0 });
  const loadUsage = useCallback(() => {
    api.usage().then((rows) => setUsage(rows.reduce(
      (a, u) => ({ req: a.req + u.requests, tok: a.tok + u.tokens_in + u.tokens_out }), { req: 0, tok: 0 }))).catch(() => {});
  }, []);
  useEffect(loadUsage, [loadUsage]);

  useEffect(() => {
    api.messages(active).then((ms) =>
      setItems((all) => {
        const extra = (all[active] ?? []).filter((i) => i.kind !== "msg");
        return { ...all, [active]: [...ms.map(msgItem), ...extra] };
      }),
    ).catch(() => {});
    setUnread((u) => ({ ...u, [active]: 0 }));
    setMenuOpen(false);
  }, [active]);

  useEffect(() => {
    const add = (chat: string, item: Item) => setItems((all) => ({ ...all, [chat]: [...(all[chat] ?? []), item] }));
    const onEvent = (e: ServerEvent) => {
      if (e.type === "usage") {
        setUsage((u) => ({ req: u.req + 1, tok: u.tok + e.tokens_in + e.tokens_out }));
        return;
      }
      const chat = e.chat_id;
      switch (e.type) {
        case "message": {
          setItems((all) => {
            const list = all[chat] ?? [];
            if (list.some((i) => i.key === `m${e.message.id}`)) return all;
            return { ...all, [chat]: [...list, msgItem(e.message)] };
          });
          if (e.message.sender !== "user") {
            const failed = /^(failed:|not mine:)/i.test(e.message.text);
            move(e.message.sender, failed ? "oops" : e.message.kind === "handoff" ? "talk" : "cheer");
          }
          if (chat !== activeRef.current) setUnread((u) => ({ ...u, [chat]: (u[chat] ?? 0) + 1 }));
          break;
        }
        case "typing":
          setTyping((t) => {
            const now = new Set(t[chat] ?? []);
            if (e.on) now.add(e.bot);
            else now.delete(e.bot);
            return { ...t, [chat]: [...now] };
          });
          if (e.on) move(e.bot, "think");
          break;
        case "step":
          if (e.status === "start") {
            add(chat, { kind: "step", key: `s${Date.now()}${Math.random()}`, bot: e.bot, tool: e.tool, status: "start" });
          } else {
            setItems((all) => {
              const list = [...(all[chat] ?? [])];
              for (let i = list.length - 1; i >= 0; i--) {
                const it = list[i];
                if (it.kind === "step" && it.status === "start" && it.bot === e.bot && it.tool === e.tool) {
                  list[i] = { ...it, status: e.status, text: e.text };
                  break;
                }
              }
              return { ...all, [chat]: list };
            });
          }
          break;
        case "approval":
          add(chat, { kind: "approval", key: `a${e.id}`, id: e.id, bot: e.bot, title: e.title, details: e.details, screenshot: e.screenshot });
          move(e.bot, "ask");
          if (chat !== activeRef.current) setUnread((u) => ({ ...u, [chat]: (u[chat] ?? 0) + 1 }));
          break;
        case "approval_done":
          setItems((all) => ({
            ...all,
            [chat]: (all[chat] ?? []).map((i) => (i.kind === "approval" && i.id === e.id ? { ...i, status: e.status } : i)),
          }));
          break;
        case "screenshot":
          add(chat, { kind: "shot", key: `p${e.url}`, bot: e.bot, url: e.url });
          break;
      }
    };
    return listen(onEvent, setLive);
  }, [move]);

  const chat = chats.find((c) => c.id === active);
  const dms = chats.filter((c) => c.members.length === 1);
  const groups = chats.filter((c) => c.members.length > 1);

  const row = (c: Chat) => {
    const first = bots[c.members[0]];
    const working = (typing[c.id] ?? []).length > 0;
    return (
      <button key={c.id} className={`chat-row ${c.id === active ? "on" : ""}`} onClick={() => setActive(c.id)}>
        {c.members.length === 1 ? (
          <Avatar bot={first} move={moves[first?.id ?? ""]} size={34} />
        ) : (
          <span className="group-badge">{c.members.slice(0, 3).map((m) => <Avatar key={m} bot={bots[m]} size={20} />)}</span>
        )}
        <span className="row-text">
          <b>{c.title}</b>
          <small>{working ? "working…" : c.members.length === 1 ? first?.role : `${c.members.length} bots`}</small>
        </span>
        {(unread[c.id] ?? 0) > 0 && <span className="badge">{unread[c.id]}</span>}
      </button>
    );
  };

  return (
    <div className={`app ${menuOpen ? "menu-open" : ""}`}>
      <aside className="sidebar">
        <div className="brand">
          <span>🧭 TeamLoop</span>
          <span className="usage-chip" title="Model requests and tokens used today">
            {usage.req} calls · {usage.tok >= 1000 ? `${(usage.tok / 1000).toFixed(1)}k` : usage.tok} tok
          </span>
          <span className={`live ${live ? "on" : ""}`} title={live ? "connected" : "reconnecting"} />
        </div>
        <div className="section">Team</div>
        {groups.map(row)}
        <button className="new-group" onClick={() => setShowNew(true)}>+ New group</button>
        <div className="section">Bots</div>
        {dms.map(row)}
        <button className="settings-btn" onClick={() => setShowSettings(true)}>⚙ Settings</button>
      </aside>
      <div className="scrim" onClick={() => setMenuOpen(false)} />
      {chat ? (
        <ChatView chat={chat} bots={bots} items={items[active] ?? []} typing={typing[active] ?? []} moves={moves}
                  onMenu={() => setMenuOpen(true)} />
      ) : (
        <section className="chat loading">{live ? "Loading…" : "Waiting for the TeamLoop server on port 8790…"}</section>
      )}
      {showSettings && <SettingsPanel bots={bots} onClose={() => setShowSettings(false)} />}
      {showNew && (
        <NewGroup bots={bots} onClose={() => setShowNew(false)} onMade={async (c) => {
          setShowNew(false);
          await loadChats();
          setActive(c.id);
        }} />
      )}
    </div>
  );
}

function NewGroup({ bots, onClose, onMade }: { bots: Record<string, Bot>; onClose: () => void; onMade: (c: Chat) => void }) {
  const [title, setTitle] = useState("");
  const [picked, setPicked] = useState<string[]>(["s"]);
  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  return (
    <div className="overlay" onClick={onClose}>
      <div className="dialog" onClick={(e) => e.stopPropagation()}>
        <b>New group</b>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Group name" autoFocus />
        <div className="pick">
          {Object.values(bots).map((b) => (
            <button key={b.id} className={picked.includes(b.id) ? "on" : ""} onClick={() => toggle(b.id)}>
              <Avatar bot={b} size={26} /> {b.name}
            </button>
          ))}
        </div>
        <div className="dialog-btns">
          <button onClick={onClose}>Cancel</button>
          <button className="primary" disabled={picked.length < 2}
                  onClick={async () => onMade(await api.newChat(title || "New group", picked))}>Create</button>
        </div>
      </div>
    </div>
  );
}
