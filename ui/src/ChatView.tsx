import { useEffect, useRef, useState } from "react";
import { api, type Bot, type Chat } from "./api";
import { Avatar, botColor, type Move } from "./Avatar";
import { RichText } from "./RichText";

export type Item =
  | { kind: "msg"; key: string; sender: string; text: string; mkind: string; ts: number }
  | { kind: "step"; key: string; bot: string; tool: string; status: "start" | "done" | "fail"; text?: string }
  | { kind: "approval"; key: string; id: string; bot: string; title: string; details: string; screenshot?: string | null; status?: string }
  | { kind: "shot"; key: string; bot: string; url: string };

type Props = {
  chat: Chat;
  bots: Record<string, Bot>;
  items: Item[];
  typing: string[];
  moves: Record<string, Move>;
  onMenu: () => void;
  onBot: (botId: string) => void;
};

const HINTS = ["team, plan my evening", "@desk what's my battery?", "@web open news.ycombinator.com", "check models", "remember I like short answers"];

const SHORT = 180;
const GROUP_GAP = 5 * 60; // seconds: messages from the same bot closer than this share one header

// "Failed: ..." replies keep the first part readable and fold the raw error (codes, JSON) away.
function Failure({ text }: { text: string }) {
  if (text.length <= SHORT) return <RichText text={text} />;
  const cut = text.lastIndexOf(" ", SHORT);
  return (
    <div className="text">
      <p>{text.slice(0, cut > 40 ? cut : SHORT)}…</p>
      <details>
        <summary>details</summary>
        <pre>{text}</pre>
      </details>
    </div>
  );
}

function time(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// "@Scout find ..." -> the bot it was handed to, and the instruction without the mention.
function handoffTarget(text: string, bots: Record<string, Bot>): { to?: Bot; rest: string } {
  const m = text.match(/^@(\w+)\s*([\s\S]*)$/);
  if (!m) return { rest: text };
  const to = Object.values(bots).find((b) => b.name.toLowerCase() === m[1].toLowerCase() || b.id === m[1].toLowerCase());
  return { to, rest: to ? m[2] : text };
}

function Handoff({ from, text, bots, ts }: { from?: Bot; text: string; bots: Record<string, Bot>; ts: number }) {
  const [open, setOpen] = useState(false);
  const { to, rest } = handoffTarget(text, bots);
  return (
    <div className="activity handoff" onClick={() => setOpen(!open)} title="A job one bot handed to another">
      <span className="flow">
        <Avatar bot={from} size={20} /> <b>{from?.name ?? "?"}</b>
        <span className="arrow" style={{ color: botColor(to?.id ?? "") }}>→</span>
        <Avatar bot={to} size={20} /> <b>{to?.name ?? "teammate"}</b>
      </span>
      <span className={`handoff-text ${open ? "open" : ""}`}>{rest}</span>
      <span className="ts">{time(ts)}</span>
    </div>
  );
}

function Step({ item, bots }: { item: Extract<Item, { kind: "step" }>; bots: Record<string, Bot> }) {
  const bot = bots[item.bot];
  return (
    <div className={`activity step ${item.status}`}>
      <span className="mark">{item.status === "start" ? <i className="spin" /> : item.status === "done" ? "✓" : "✗"}</span>
      <span className="step-who" style={{ color: botColor(item.bot) }}>{bot?.name ?? item.bot}</span>
      <code>{item.tool}</code>
      {item.text && <span className="step-text">{item.text}</span>}
    </div>
  );
}

export function ChatView({ chat, bots, items, typing, moves, onMenu, onBot }: Props) {
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const log = useRef<HTMLDivElement>(null);
  const busy = typing.length > 0 || items.some((i) => i.kind === "approval" && !i.status);

  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" });
  }, [items, typing]);

  async function send(e?: React.FormEvent) {
    e?.preventDefault();
    const value = text.trim();
    if (!value) return;
    setText("");
    setError("");
    try {
      await api.send(chat.id, value);
    } catch (err) {
      setError(String((err as Error).message));
      setText(value);
    }
  }

  const members = chat.members.map((m) => bots[m]).filter(Boolean);

  // A bot's header (avatar, name, role) shows once per run of its messages, like a real team chat.
  let lastSender = "";
  let lastTs = 0;

  return (
    <section className="chat">
      <header className="chat-head">
        <button className="icon menu" onClick={onMenu} aria-label="Chats">☰</button>
        <div className="crew">
          {members.map((b) => (
            <button key={b.id} className="crew-btn" title={`${b.name}: what it does`} onClick={() => onBot(b.id)}>
              <Avatar bot={b} move={moves[b.id]} size={30} />
            </button>
          ))}
        </div>
        <div className="chat-title">
          <b>{chat.title}</b>
          <small>{members.map((b) => b.name).join(" · ")}</small>
        </div>
        {busy && <button className="stop" onClick={() => api.stop(chat.id)}>■ Stop</button>}
      </header>

      <div className="log" ref={log}>
        {items.length === 0 && (
          <div className="empty">
            <p>Say hi to {members.length > 1 ? "the crew" : members[0]?.name}. Try:</p>
            {HINTS.map((h) => <button key={h} className="hint" onClick={() => setText(h)}>{h}</button>)}
          </div>
        )}
        {items.map((item) => {
          if (item.kind === "msg") {
            const mine = item.sender === "user";
            const bot = bots[item.sender];
            if (item.mkind === "handoff") {
              lastSender = "";
              return <Handoff key={item.key} from={bot} text={item.text} bots={bots} ts={item.ts} />;
            }
            if (item.mkind === "routine") {
              lastSender = "";
              return <div key={item.key} className="activity routine">{item.text}<span className="ts">{time(item.ts)}</span></div>;
            }
            const failed = !mine && /^failed\b/i.test(item.text);
            const head = !mine && (item.sender !== lastSender || item.ts - lastTs > GROUP_GAP);
            lastSender = item.sender;
            lastTs = item.ts;
            if (mine) {
              return (
                <div key={item.key} className="row mine">
                  <div className="bubble"><div className="text">{item.text}</div><div className="ts">{time(item.ts)}</div></div>
                </div>
              );
            }
            return (
              <div key={item.key} className={`row bot ${head ? "head" : "cont"} ${failed ? "failed" : ""}`}
                   style={{ "--bot": botColor(item.sender) } as React.CSSProperties}>
                <div className="gutter">
                  {head && bot && <button className="crew-btn" title={`${bot.name}: what it does`} onClick={() => onBot(bot.id)}><Avatar bot={bot} move={moves[item.sender]} size={38} /></button>}
                </div>
                <div className="body">
                  {head && (
                    <div className="who">
                      <b>{bot?.name ?? item.sender}</b>
                      <span className="role">{bot?.role}</span>
                      <span className="ts">{time(item.ts)}</span>
                    </div>
                  )}
                  <div className="bubble">
                    {item.mkind === "fast" && <span className="tag" title="Done directly, without calling an AI model">⚡ instant · no model</span>}
                    {failed ? <Failure text={item.text} /> : <RichText text={item.text} />}
                  </div>
                </div>
              </div>
            );
          }
          lastSender = "";
          if (item.kind === "step") return <Step key={item.key} item={item} bots={bots} />;
          if (item.kind === "shot") {
            return <img key={item.key} className="shot" src={item.url} alt="screenshot" />;
          }
          return (
            <div key={item.key} className={`approval ${item.status ?? "waiting"}`}
                 style={{ "--bot": botColor(item.bot) } as React.CSSProperties}>
              <div className="approval-head">
                <Avatar bot={bots[item.bot]} move={item.status ? "idle" : "ask"} size={30} />
                <div>
                  <b>{bots[item.bot]?.name ?? item.bot} needs your OK</b>
                  <div className="approval-title">{item.title}</div>
                </div>
              </div>
              <p>{item.details}</p>
              {item.screenshot && <img src={item.screenshot} alt="what will be affected" />}
              {item.status ? (
                <div className={`approval-done ${item.status}`}>{item.status === "approved" ? "✓ Approved" : item.status === "expired" ? "No answer: not done" : item.status === "stopped" ? "Stopped" : "✗ Denied"}</div>
              ) : (
                <div className="approval-btns">
                  <button className="primary" onClick={() => api.answer(item.id, true)}>Approve</button>
                  <button className="deny" onClick={() => api.answer(item.id, false)}>Deny</button>
                </div>
              )}
            </div>
          );
        })}
        {typing.length > 0 && (
          <div className="typing">
            <span className="typing-avatars">{typing.map((id) => <Avatar key={id} bot={bots[id]} move="think" size={24} />)}</span>
            <span>{typing.map((id) => bots[id]?.name ?? id).join(", ")} {typing.length > 1 ? "are" : "is"} working</span>
            <span className="dots"><i /><i /><i /></span>
          </div>
        )}
      </div>

      {error && <div className="error">{error}</div>}
      <form className="composer" onSubmit={send}>
        <textarea
          value={text}
          rows={1}
          placeholder={window.innerWidth < 720 ? `Message ${chat.title}…` : `Message ${chat.title}…  (@name to ask one bot · paste a key to save it)`}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        />
        <button className="primary send" disabled={!text.trim()}>Send ➤</button>
      </form>
    </section>
  );
}
