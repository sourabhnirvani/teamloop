import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type Bot, type Chat } from "./api";
import { Avatar, botColor, SIGNS, toolSign, type Move } from "./Avatar";
import { BoardView } from "./BoardView";
import { NewBotSheet } from "./BotBuilder";
import { BotProfile } from "./BotProfile";
import { ChatView } from "./ChatView";
import { CrewView } from "./CrewView";
import { JobsView } from "./JobsView";
import { go, href, useRoute, withOverlay, type Tab } from "./router";
import { SettingsView } from "./SettingsView";
import { Sheet } from "./Sheet";
import { useCrew } from "./store";
import { applyUpdate, updateAvailable } from "./update";

const PHONE = 760; // px: at or below this the app is one column with tabs at the bottom
const DEFAULT_CHAT = "team";

function useNarrow() {
  const [narrow, setNarrow] = useState(() => window.innerWidth <= PHONE);
  useEffect(() => {
    const on = () => setNarrow(window.innerWidth <= PHONE);
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);
  return narrow;
}

function stored(key: string, fallback: string) {
  try { return localStorage.getItem(key) ?? fallback; } catch { return fallback; }
}

function ago(ts?: number) {
  if (!ts) return "";
  const s = Date.now() / 1000 - ts;
  if (s < 60) return "now";
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

const TABS: { tab: Tab; icon: string; label: string }[] = [
  { tab: "chats", icon: "💬", label: "Chats" },
  { tab: "crew", icon: "🤖", label: "Crew" },
  { tab: "board", icon: "📋", label: "Board" },
  { tab: "jobs", icon: "⌨️", label: "Jobs" },
  { tab: "settings", icon: "⚙", label: "Settings" },
];

export default function App() {
  const route = useRoute();
  const narrow = useNarrow();
  const chatId = route.tab === "chats" ? route.id ?? (narrow ? null : DEFAULT_CHAT) : null;
  const crew = useCrew(chatId);
  const { bots, chats, items, typing, unread, moves, handoff, tools, asleep, tasks, live, ready } = crew;
  const [listening, setListening] = useState<string[]>([]);
  const quiet = useRef<number | undefined>(undefined);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [theme, setTheme] = useState(() => stored("tl-theme", "dark"));
  const [updateReady, setUpdateReady] = useState(false);
  const pushed = useRef(false); // an overlay we opened ourselves: closing it goes Back

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("tl-theme", theme); } catch { /* private mode */ }
  }, [theme]);

  useEffect(() => {
    // the laptop got a new build: offer Update (checked every minute and whenever the app comes back to the front)
    const check = () => updateAvailable().then((yes) => yes && setUpdateReady(true));
    check();
    const t = window.setInterval(check, 60000);
    const onShow = () => document.visibilityState === "visible" && check();
    document.addEventListener("visibilitychange", onShow);
    return () => { window.clearInterval(t); document.removeEventListener("visibilitychange", onShow); };
  }, []);

  const openOverlay = useCallback((key: "bot" | "new", value: string) => {
    pushed.current = true;
    go(withOverlay(route, key, value));
  }, [route]);
  const closeOverlay = useCallback(() => {
    if (pushed.current) {
      pushed.current = false;
      window.history.back();
    } else {
      go(href(route.tab, route.id), true);
    }
  }, [route.tab, route.id]);

  const openChat = (id: string) => go(href("chats", id), !narrow && route.tab === "chats");
  const chat = chats.find((c) => c.id === chatId);
  const lead = bots.s;
  const dms = chats.filter((c) => c.members.length === 1 && c.members[0] !== "s");
  const leadChat = chats.find((c) => c.members.length === 1 && c.members[0] === "s");
  const groups = chats.filter((c) => c.members.length > 1);
  const crewList = useMemo(() => Object.values(bots), [bots]);
  const working = useMemo(() => [...new Set(Object.values(typing).flat())], [typing]);
  const asking = useMemo(() => [...new Set(Object.values(items).flat()
    .filter((i) => i.kind === "approval" && !i.status).map((i) => (i as { bot: string }).bot))], [items]);
  const totalUnread = Object.values(unread).reduce((a, b) => a + b, 0);

  // You typing in a chat: the bot you're talking to perks up and listens (2.5 s after your last key it relaxes).
  const onTyping = useCallback((c: Chat, text: string) => {
    window.clearTimeout(quiet.current);
    if (!text.trim()) { setListening([]); return; }
    const named = [...text.matchAll(/@(\w+)|^\s*(\w+)[,:]/g)].map((m) => (m[1] || m[2]).toLowerCase())
      .map((n) => Object.values(bots).find((b) => b.id === n || b.name.toLowerCase() === n)?.id)
      .filter((id): id is string => !!id && c.members.includes(id));
    setListening(named.length ? named : c.members.length === 1 ? c.members : c.members.includes("s") ? ["s"] : [c.members[0]]);
    quiet.current = window.setTimeout(() => setListening([]), 2500);
  }, [bots]);
  useEffect(() => () => window.clearTimeout(quiet.current), []);

  // what each bot looks like right now: its move, and the sign over its head
  const look = useCallback((id: string): { move: Move; sign: string | null } => {
    const m = moves[id] ?? "idle";
    if (asking.includes(id)) return { move: "ask", sign: SIGNS.ask! };
    if (tools[id]) return { move: m === "idle" ? "think" : m, sign: toolSign(tools[id]) };
    if (m !== "idle") return { move: m, sign: SIGNS[m] ?? null };
    if (listening.includes(id)) return { move: "listen", sign: SIGNS.listen! };
    if (asleep) return { move: "sleep", sign: SIGNS.sleep! };
    return { move: "idle", sign: null };
  }, [moves, asking, tools, listening, asleep]);

  const preview = (c: Chat) => {
    const busy = typing[c.id] ?? [];
    if (busy.length) return { text: `${busy.map((id) => bots[id]?.name ?? id).join(", ")} working…`, busy: true };
    const last = c.last;
    if (!last) return { text: c.members.length === 1 ? bots[c.members[0]]?.role ?? "" : `${c.members.length} bots`, busy: false };
    const who = last.sender === "user" ? "You: " : c.members.length > 1 ? `${bots[last.sender]?.name ?? last.sender}: ` : "";
    return { text: who + last.text.replace(/\s+/g, " "), busy: false };
  };

  const row = (c: Chat) => {
    const first = bots[c.members[0]];
    const p = preview(c);
    return (
      <button key={c.id} className={`chat-row ${c.id === chatId ? "on" : ""}`} onClick={() => openChat(c.id)}>
        {c.members.length === 1 ? (
          <Avatar bot={first} {...look(first?.id ?? "")} size={40} />
        ) : (
          <span className="group-badge">{c.members.slice(0, 4).map((m) => <Avatar key={m} bot={bots[m]} size={21} />)}</span>
        )}
        <span className="row-text">
          <span className="row-top"><b>{c.title}</b><time>{ago(c.last?.ts)}</time></span>
          <small className={p.busy ? "busy" : ""}>{p.text}</small>
        </span>
        {(unread[c.id] ?? 0) > 0 && <span className="badge">{unread[c.id]}</span>}
      </button>
    );
  };

  const chatList = (
    <aside className="sidebar">
      <div className="brand"><img src="/logo.svg" alt="" /><span><b>TeamLoop</b><small>your AI crew</small></span></div>
      {lead && leadChat && (
        <button className={`hero ${leadChat.id === chatId ? "on" : ""}`} style={{ "--bot": botColor("s") } as React.CSSProperties}
                onClick={() => openChat(leadChat.id)}>
          <Avatar bot={lead} {...look("s")} size={56} />
          <span className="row-text">
            <span className="row-top"><b>{lead.name} <em>LEAD</em></b><time>{ago(leadChat.last?.ts)}</time></span>
            <small className={preview(leadChat).busy ? "busy" : ""}>{preview(leadChat).text || "Plans jobs and hands steps to the crew"}</small>
          </span>
          {(unread[leadChat.id] ?? 0) > 0 && <span className="badge">{unread[leadChat.id]}</span>}
        </button>
      )}
      <div className="section">Group chats</div>
      {groups.map(row)}
      <button className="new-group" onClick={() => openOverlay("new", "group")}>＋ New group</button>
      <div className="section">Your crew</div>
      {dms.map(row)}
      <button className="new-group" onClick={() => openOverlay("new", "bot")}>＋ Build a bot</button>
    </aside>
  );

  let main: React.ReactNode;
  if (route.tab === "crew") {
    main = <CrewView bots={crewList} moves={moves} look={look} working={working} asking={asking} handoff={handoff} onBot={(id) => openOverlay("bot", id)} />;
  } else if (route.tab === "board") {
    main = <BoardView tasks={tasks} bots={bots} look={look} onChat={(id) => go(href("chats", id))} />;
  } else if (route.tab === "jobs") {
    main = <JobsView chats={chats} onChat={(id) => go(href("chats", id))} />;
  } else if (route.tab === "settings") {
    main = <SettingsView page={route.id} bots={bots} theme={theme} setTheme={setTheme} />;
  } else if (chat) {
    main = (
      <ChatView key={chat.id} chat={chat} bots={bots} items={items[chat.id] ?? []} typing={typing[chat.id] ?? []} moves={moves} look={look}
                draft={drafts[chat.id] ?? ""} setDraft={(t) => { setDrafts((d) => ({ ...d, [chat.id]: t })); onTyping(chat, t); }}
                onBack={() => go(href("chats"))} onBot={(id) => openOverlay("bot", id)}
                onAnswered={(id, status) => crew.markAnswered(chat.id, id, status)} />
    );
  } else if (!narrow) {
    main = <section className="chat loading">{live ? (ready ? "Pick a chat." : "Loading…") : "Connecting to TeamLoop on this laptop…"}</section>;
  }

  const inChat = route.tab === "chats" && !!chat;
  const showList = route.tab === "chats" && (!narrow || !chat);
  const profileBot = route.bot ? bots[route.bot] : undefined;

  return (
    <div className={`app tab-${route.tab} ${inChat ? "in-chat" : ""}`}>
      <nav className="rail" aria-label="TeamLoop">
        <img className="logo" src="/logo.svg" alt="" />
        {TABS.map((t) => (
          <button key={t.tab} className={`rail-btn ${route.tab === t.tab ? "on" : ""}`} aria-current={route.tab === t.tab ? "page" : undefined}
                  onClick={() => go(href(t.tab, t.tab === "chats" ? chatId : null))}>
            <span aria-hidden="true">{t.icon}</span><small>{t.label}</small>
            {t.tab === "chats" && totalUnread > 0 && <i className="dot-badge">{totalUnread}</i>}
          </button>
        ))}
        <div className="rail-spacer" />
        <span className={`live ${live ? "on" : ""}`} role="status" aria-label={live ? "Connected to the laptop" : "Reconnecting"} title={live ? "connected" : "reconnecting"} />
      </nav>

      {showList && chatList}

      <main className="main">
        {updateReady && (
          <div className="update-bar" role="status">
            <span>A new version of TeamLoop is ready.</span>
            <button className="primary" onClick={applyUpdate}>Update</button>
            <button onClick={() => setUpdateReady(false)}>Later</button>
          </div>
        )}
        {!live && ready && narrow && <div className="offline-bar" role="status">Reconnecting to the laptop…</div>}
        {main}
      </main>

      {!inChat && (
        <nav className="tabbar" aria-label="TeamLoop">
          {TABS.map((t) => (
            <button key={t.tab} className={route.tab === t.tab ? "on" : ""} aria-current={route.tab === t.tab ? "page" : undefined}
                    onClick={() => go(href(t.tab))}>
              <span aria-hidden="true">{t.icon}</span><small>{t.label}</small>
              {t.tab === "chats" && totalUnread > 0 && <i className="dot-badge">{totalUnread}</i>}
            </button>
          ))}
        </nav>
      )}

      {profileBot && (
        <BotProfile bot={profileBot} bots={bots} chats={chats} typing={typing} look={look} onClose={closeOverlay}
                    onBot={(id) => go(withOverlay(route, "bot", id), true)}
                    onChat={(id) => { pushed.current = false; go(href("chats", id), true); }}
                    onRemoved={() => { pushed.current = false; crew.loadChats(); go(href("chats"), true); }} />
      )}
      {route.overlay === "bot" && (
        <NewBotSheet onClose={closeOverlay} onMade={async (b) => {
          await Promise.all([crew.loadChats(), crew.loadBots()]);
          pushed.current = false;
          go(href("chats", `dm-${b.id}`), true);
        }} />
      )}
      {route.overlay === "group" && (
        <NewGroup bots={bots} onClose={closeOverlay} onMade={async (c) => {
          await crew.loadChats();
          pushed.current = false;
          go(href("chats", c.id), true);
        }} />
      )}
    </div>
  );
}

function NewGroup({ bots, onClose, onMade }: { bots: Record<string, Bot>; onClose: () => void; onMade: (c: Chat) => void }) {
  const [title, setTitle] = useState("");
  const [picked, setPicked] = useState<string[]>(["s"]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  return (
    <Sheet title="New group" onClose={onClose}>
      <div className="form">
        <label className="field">Group name
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Weekend plans" />
        </label>
        <div className="field">Who's in it (S leads the group)</div>
        <div className="pick">
          {Object.values(bots).map((b) => (
            <button key={b.id} className={picked.includes(b.id) ? "on" : ""} aria-pressed={picked.includes(b.id)} onClick={() => toggle(b.id)}>
              <Avatar bot={b} size={30} /> {b.name}
            </button>
          ))}
        </div>
        {error && <div className="error">{error}</div>}
        <div className="dialog-btns">
          <button onClick={onClose}>Cancel</button>
          <button className="primary" disabled={picked.length < 2 || busy} onClick={async () => {
            setBusy(true);
            try { onMade(await api.newChat(title.trim() || "New group", picked)); } catch (e) { setError((e as Error).message); setBusy(false); }
          }}>{busy ? "Creating…" : "Create"}</button>
        </div>
      </div>
    </Sheet>
  );
}
