import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { api, type Bot, type Chat } from "./api";
import { Avatar, botColor, colorOf, type Move } from "./Avatar";
import { ModelChip } from "./ModelChip";
import { RichText } from "./RichText";
import type { Item } from "./store";

type Props = {
  chat: Chat;
  bots: Record<string, Bot>;
  items: Item[];
  typing: string[];
  moves: Record<string, Move>;
  look: (botId: string) => { move: Move; sign: string | null };
  draft: string;
  setDraft: (text: string) => void;
  onBack: () => void;
  onBot: (botId: string) => void;
  onAnswered: (approvalId: string, status: string) => void;
};

const HINTS = ["team, plan my evening", "@desk what's my battery?", "@web open news.ycombinator.com", "check models", "remember I like short answers"];
const SHORT = 180;
const GROUP_GAP = 5 * 60; // seconds: messages from the same bot closer than this share one header
const NEAR_BOTTOM = 80; // px: closer than this to the end counts as "reading the newest"
const touch = window.matchMedia?.("(pointer: coarse)").matches ?? false;

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
    <button className="activity handoff" onClick={() => setOpen(!open)} aria-expanded={open} title="A job one bot handed to another">
      <span className="flow">
        <Avatar bot={from} size={20} /> <b>{from?.name ?? "?"}</b>
        <span className="arrow" style={{ color: botColor(to?.id ?? "") }}>→</span>
        <Avatar bot={to} size={20} /> <b>{to?.name ?? "teammate"}</b>
      </span>
      <span className={`handoff-text ${open ? "open" : ""}`}>{rest}</span>
      <span className="ts">{time(ts)}</span>
    </button>
  );
}

function Step({ item, bots }: { item: Extract<Item, { kind: "step" }>; bots: Record<string, Bot> }) {
  return (
    <div className={`activity step ${item.status}`}>
      <span className="mark">{item.status === "start" ? <i className="spin" /> : item.status === "done" ? "✓" : "✗"}</span>
      <span className="step-who" style={{ color: botColor(item.bot) }}>{bots[item.bot]?.name ?? item.bot}</span>
      <code>{item.tool}</code>
      {item.text && <span className="step-text">{item.text}</span>}
    </div>
  );
}

const DONE_LABEL: Record<string, string> = {
  approved: "✓ Approved", denied: "✗ Denied", expired: "No answer: not done", stopped: "Stopped", answered: "Answered",
};

function Approval({ item, bots, onAnswered }: { item: Extract<Item, { kind: "approval" }>; bots: Record<string, Bot>; onAnswered: (id: string, status: string) => void }) {
  const [sending, setSending] = useState(false);
  const answer = async (ok: boolean, always = false) => {
    setSending(true); // one press only: a second click can't send a second answer
    try {
      await api.answer(item.id, ok, always);
    } catch {
      onAnswered(item.id, "answered"); // it was already answered (on the phone, by typing yes/no, or it expired)
    }
  };
  return (
    <div className={`approval ${item.status ?? "waiting"}`} style={{ "--bot": botColor(item.bot) } as React.CSSProperties}>
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
        <div className={`approval-done ${item.status}`}>{DONE_LABEL[item.status] ?? item.status}</div>
      ) : (
        <div className="approval-btns">
          <button className="primary" disabled={sending} onClick={() => answer(true)}>Approve</button>
          {item.canAlways && (
            <button disabled={sending} title="Do this again without asking. You can undo it in Settings → Always-allowed actions."
                    onClick={() => answer(true, true)}>Always allow</button>
          )}
          <button className="deny" disabled={sending} onClick={() => answer(false)}>Deny</button>
        </div>
      )}
    </div>
  );
}

export function ChatView({ chat, bots, items, typing, moves, look, draft, setDraft, onBack, onBot, onAnswered }: Props) {
  const [error, setError] = useState("");
  const [behind, setBehind] = useState(false);
  const log = useRef<HTMLDivElement>(null);
  const atEnd = useRef(true);
  const box = useRef<HTMLTextAreaElement>(null);
  const busy = typing.length > 0 || items.some((i) => i.kind === "approval" && !i.status);
  const count = items.length + typing.length;

  const toEnd = (smooth: boolean) => {
    const el = log.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: smooth ? "smooth" : "auto" });
    atEnd.current = true;
    setBehind(false);
  };
  useLayoutEffect(() => toEnd(false), [chat.id]);
  useEffect(() => {
    // follow new messages only while reading the newest (instantly: a smooth scroll still moving when the next
    // message lands would look like "scrolled up"); otherwise show the "New messages" pill
    if (atEnd.current) toEnd(false);
    else setBehind(true);
  }, [count]);

  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 6 * 24 + 16)}px`; // grows up to 6 lines
  }, [draft]);

  async function send(e?: React.FormEvent) {
    e?.preventDefault();
    const value = draft.trim();
    if (!value) return;
    setDraft("");
    setError("");
    atEnd.current = true;
    try {
      await api.send(chat.id, value);
    } catch (err) {
      setError(String((err as Error).message));
      setDraft(value);
    }
  }

  const members = chat.members.map((m) => bots[m]).filter(Boolean);
  let lastSender = "";
  let lastTs = 0;

  return (
    <section className="chat">
      <header className="chat-head">
        <button className="icon back" onClick={onBack} aria-label="Back to chats">‹</button>
        <div className="crew">
          {members.map((b) => (
            <button key={b.id} className="crew-btn" title={`${b.name}: profile`} aria-label={`${b.name} profile`} onClick={() => onBot(b.id)}>
              <Avatar bot={b} {...look(b.id)} size={34} />
            </button>
          ))}
        </div>
        <div className="chat-title">
          <b>{chat.title}</b>
          <small>{typing.length ? `${typing.map((id) => bots[id]?.name ?? id).join(", ")} working…` : members.map((b) => b.name).join(" · ")}</small>
        </div>
        <ModelChip bot={members.length === 1 ? members[0] : undefined} />
        {busy && <button className="stop" onClick={() => api.stop(chat.id)}>■ Stop</button>}
      </header>

      <div className="log" ref={log} aria-live="polite"
           onScroll={(e) => {
             const el = e.currentTarget;
             atEnd.current = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM;
             if (atEnd.current) setBehind(false);
           }}>
        {items.length === 0 && (
          <div className="empty">
            <p>Say hi to {members.length > 1 ? "the crew" : members[0]?.name}. Try:</p>
            {HINTS.map((h) => <button key={h} className="hint" onClick={() => setDraft(h)}>{h}</button>)}
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
              <div key={item.key} className={`row bot ${head ? "head" : "cont"} ${failed ? "failed" : ""} ${item.mkind === "stopped" ? "stopped" : ""}`}
                   style={{ "--bot": colorOf(bot) } as React.CSSProperties}>
                <div className="gutter">
                  {head && bot && (
                    <button className="crew-btn" title={`${bot.name}: profile`} aria-label={`${bot.name} profile`} onClick={() => onBot(bot.id)}>
                      <Avatar bot={bot} move={moves[item.sender]} size={38} />
                    </button>
                  )}
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
          if (item.kind === "shot") return <img key={item.key} className="shot" src={item.url} alt="screenshot" />;
          if (item.kind === "allowed") {
            return (
              <div key={item.key} className="activity allowed">
                <span className="mark">✓</span>
                <span><b style={{ color: botColor(item.bot) }}>{bots[item.bot]?.name ?? item.bot}</b> went ahead: {item.title} (you always allow this)</span>
                <a href="#/settings/allowed">change</a>
              </div>
            );
          }
          return <Approval key={item.key} item={item} bots={bots} onAnswered={onAnswered} />;
        })}
        {typing.length > 0 && (
          <div className="typing">
            <span className="typing-avatars">{typing.map((id) => <Avatar key={id} bot={bots[id]} {...look(id)} size={30} />)}</span>
            <span>{typing.map((id) => bots[id]?.name ?? id).join(", ")} {typing.length > 1 ? "are" : "is"} working</span>
            <span className="dots"><i /><i /><i /></span>
          </div>
        )}
      </div>
      {behind && <button className="new-pill" onClick={() => toEnd(true)}>New messages ↓</button>}

      {error && <div className="error">{error}</div>}
      <form className="composer" onSubmit={send}>
        <textarea
          ref={box}
          value={draft}
          rows={1}
          aria-label={`Message ${chat.title}`}
          placeholder={`Message ${chat.title}…`}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !touch) { // on phones Enter is a new line; the Send button sends
              e.preventDefault();
              send();
            }
          }}
        />
        <button className="primary send" disabled={!draft.trim()} aria-label="Send">Send ➤</button>
      </form>
      <div className="composer-hint">@name asks one bot · paste a key to save it · “stop” stops everything</div>
    </section>
  );
}
