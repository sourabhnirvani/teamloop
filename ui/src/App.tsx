import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, listen, type Bot, type Chat, type Message, type ServerEvent } from "./api";
import { ActivityPanel, BotProfile } from "./ActivityPanel";
import { Avatar, type Move } from "./Avatar";
import { ChatView, type Item } from "./ChatView";
import { CrewRoom, type Handoff } from "./CrewRoom";
import { SettingsPanel } from "./SettingsPanel";

const msgItem = (m: Message): Item => ({ kind: "msg", key: `m${m.id}`, sender: m.sender, text: m.text, mkind: m.kind, ts: m.ts });

function useWide(px: number) {
  const [wide, setWide] = useState(() => window.innerWidth >= px);
  useEffect(() => {
    const on = () => setWide(window.innerWidth >= px);
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, [px]);
  return wide;
}

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
  const [profile, setProfile] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [roomOpen, setRoomOpen] = useState(() => localStorage.getItem("tl-room") !== "0");
  const [handoff, setHandoff] = useState<Handoff | null>(null);
  const [theme, setTheme] = useState(() => localStorage.getItem("tl-theme") ?? "dark");
  const activeRef = useRef(active);
  const timers = useRef<Record<string, number>>({});
  const botsRef = useRef(bots);
  activeRef.current = active;
  botsRef.current = bots;
  const wide = useWide(1240);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("tl-theme", theme); } catch { /* private mode */ }
  }, [theme]);
  useEffect(() => {
    try { localStorage.setItem("tl-room", roomOpen ? "1" : "0"); } catch { /* private mode */ }
  }, [roomOpen]);

  const move = useCallback((bot: string, m: Move, ms = 1500) => {
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
  useEffect(() => { loadChats().catch(() => setLive(false)); }, [loadChats]);

  const [usage, setUsage] = useState({ req: 0, tok: 0 });
  useEffect(() => {
    api.usage().then((rows) => setUsage(rows.reduce(
      (a, u) => ({ req: a.req + u.requests, tok: a.tok + u.tokens_in + u.tokens_out }), { req: 0, tok: 0 }))).catch(() => {});
  }, []);

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
            if (e.message.kind === "handoff") {
              const name = e.message.text.match(/^@(\w+)/)?.[1]?.toLowerCase();
              const to = Object.values(botsRef.current).find((b) => b.id === name || b.name.toLowerCase() === name);
              if (to) setHandoff({ from: e.message.sender, to: to.id, key: Date.now() });
              move(e.message.sender, "talk");
            } else {
              move(e.message.sender, failed ? "oops" : "cheer");
            }
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
            if (e.status === "fail") move(e.bot, "oops");
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
          setMoves((all) => Object.fromEntries(Object.entries(all).map(([k, v]) => [k, v === "ask" ? "idle" : v])));
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
  const crew = useMemo(() => Object.values(bots), [bots]);
  const working = useMemo(() => [...new Set(Object.values(typing).flat())], [typing]);
  const asking = useMemo(() => [...new Set(Object.values(items).flat()
    .filter((i): i is Extract<Item, { kind: "approval" }> => i.kind === "approval" && !i.status).map((i) => i.bot))], [items]);

  const room = (h: number | string) => (
    <CrewRoom bots={crew} moves={moves} working={working} asking={asking} handoff={handoff} onPick={(id) => setProfile(id)} height={h} />
  );

  const row = (c: Chat) => {
    const first = bots[c.members[0]];
    const busy = (typing[c.id] ?? []).length > 0;
    return (
      <button key={c.id} className={`chat-row ${c.id === active ? "on" : ""}`} onClick={() => setActive(c.id)}>
        {c.members.length === 1 ? (
          <Avatar bot={first} move={moves[first?.id ?? ""]} size={38} />
        ) : (
          <span className="group-badge">{c.members.slice(0, 4).map((m) => <Avatar key={m} bot={bots[m]} size={22} />)}</span>
        )}
        <span className="row-text">
          <b>{c.title}</b>
          <small className={busy ? "busy" : ""}>{busy ? `${(typing[c.id] ?? []).map((id) => bots[id]?.name).join(", ")} working…` : c.members.length === 1 ? first?.role : `${c.members.length} bots`}</small>
        </span>
        {(unread[c.id] ?? 0) > 0 && <span className="badge">{unread[c.id]}</span>}
      </button>
    );
  };

  return (
    <div className={`app ${menuOpen ? "menu-open" : ""}`}>
      <nav className="rail">
        <div className="logo" title="TeamLoop"><span>⟳</span></div>
        <button className="rail-btn on" title="Chats" onClick={() => setMenuOpen(!menuOpen)}>💬</button>
        <button className={`rail-btn ${roomOpen ? "on" : ""}`} title="Crew Room" onClick={() => setRoomOpen(!roomOpen)}>🏠</button>
        <button className="rail-btn" title="Meet the crew" onClick={() => setProfile("s")}>👥</button>
        <div className="rail-spacer" />
        <button className="rail-btn" title={theme === "dark" ? "Light mode" : "Dark mode"} onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>{theme === "dark" ? "☀" : "☾"}</button>
        <button className="rail-btn" title="Settings" onClick={() => setShowSettings(true)}>⚙</button>
        <span className={`live ${live ? "on" : ""}`} title={live ? "connected" : "reconnecting"} />
      </nav>

      <aside className="sidebar">
        <div className="brand"><b>TeamLoop</b><small>your AI crew</small></div>
        <div className="section">Group chats</div>
        {groups.map(row)}
        <button className="new-group" onClick={() => setShowNew(true)}>＋ New group</button>
        <div className="section">The crew</div>
        {dms.map(row)}
      </aside>
      <div className="scrim" onClick={() => setMenuOpen(false)} />

      <main className="main">
        {chat ? (
          <ChatView chat={chat} bots={bots} items={items[active] ?? []} typing={typing[active] ?? []} moves={moves}
                    onMenu={() => setMenuOpen(true)}
                    stage={!wide && roomOpen ? <div className="room-strip">{room(230)}</div> : null} />
        ) : (
          <section className="chat loading">{live ? "Loading…" : "Waiting for the TeamLoop server on port 8790…"}</section>
        )}
      </main>

      {wide && (
        <aside className="crewpanel">
          {roomOpen && (
            <div className="room-card">
              <div className="room-head"><b>Crew Room</b><small>{working.length ? `${working.length} working` : asking.length ? "waiting for you" : "all free"}</small></div>
              {room("100%")}
            </div>
          )}
          <ActivityPanel bots={bots} chats={chats} items={items} typing={typing} moves={moves} usage={usage}
                         onOpenChat={setActive} onOpenBot={setProfile} />
        </aside>
      )}

      {showSettings && <SettingsPanel bots={bots} onClose={() => setShowSettings(false)} />}
      {profile && bots[profile] && (
        <BotProfile bot={bots[profile]} bots={bots} chats={chats} typing={typing} onClose={() => setProfile(null)}
                    onChat={(id) => {
                      if (id.startsWith("__profile:")) { setProfile(id.slice(10)); return; }
                      setProfile(null);
                      setActive(id);
                    }} />
      )}
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
              <Avatar bot={b} size={30} /> {b.name}
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
