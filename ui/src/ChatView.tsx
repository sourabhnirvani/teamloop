import { useEffect, useRef, useState } from "react";
import { api, type Bot, type Chat } from "./api";
import { Avatar, type Move } from "./Avatar";

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
};

const HINTS = ["team, plan my evening", "@desk what's my battery?", "@web open news.ycombinator.com", "check models", "remember I like short answers"];

function time(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function ChatView({ chat, bots, items, typing, moves, onMenu }: Props) {
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

  return (
    <section className="chat">
      <header className="chat-head">
        <button className="icon menu" onClick={onMenu} aria-label="Chats">☰</button>
        <div className="crew">
          {members.map((b) => <Avatar key={b.id} bot={b} move={moves[b.id]} size={30} />)}
        </div>
        <div className="chat-title">
          <b>{chat.title}</b>
          <small>{members.map((b) => b.name).join(", ")}</small>
        </div>
        {busy && <button className="stop" onClick={() => api.stop(chat.id)}>Stop</button>}
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
            return (
              <div key={item.key} className={`row ${mine ? "mine" : ""} ${item.mkind}`}>
                {!mine && <Avatar bot={bot} move={moves[item.sender]} size={32} />}
                <div className="bubble">
                  {!mine && <div className="who">{bot?.name ?? item.sender}{item.mkind === "handoff" && " → handoff"}</div>}
                  <div className="text">{item.text}</div>
                  <div className="ts">{time(item.ts)}</div>
                </div>
              </div>
            );
          }
          if (item.kind === "step") {
            const mark = item.status === "start" ? "⋯" : item.status === "done" ? "✓" : "✗";
            return (
              <div key={item.key} className={`step ${item.status}`}>
                <span className="mark">{mark}</span> {bots[item.bot]?.name ?? item.bot} · <code>{item.tool}</code>
                {item.text && <span className="step-text"> {item.text}</span>}
              </div>
            );
          }
          if (item.kind === "shot") {
            return <img key={item.key} className="shot" src={item.url} alt="screenshot" />;
          }
          return (
            <div key={item.key} className={`approval ${item.status ?? "waiting"}`}>
              <div className="approval-head">
                <Avatar bot={bots[item.bot]} move={item.status ? "idle" : "ask"} size={28} />
                <b>{bots[item.bot]?.name ?? item.bot} asks: {item.title}</b>
              </div>
              <p>{item.details}</p>
              {item.screenshot && <img src={item.screenshot} alt="what will be affected" />}
              {item.status ? (
                <div className="approval-done">{item.status}</div>
              ) : (
                <div className="approval-btns">
                  <button className="primary" onClick={() => api.answer(item.id, true)}>Approve</button>
                  <button onClick={() => api.answer(item.id, false)}>Deny</button>
                </div>
              )}
            </div>
          );
        })}
        {typing.length > 0 && (
          <div className="typing">
            {typing.map((id) => <Avatar key={id} bot={bots[id]} move="think" size={22} />)}
            <span>{typing.map((id) => bots[id]?.name ?? id).join(", ")} working</span>
            <span className="dots"><i /><i /><i /></span>
          </div>
        )}
      </div>

      {error && <div className="error">{error}</div>}
      <form className="composer" onSubmit={send}>
        <textarea
          value={text}
          rows={1}
          placeholder={`Message ${chat.title}… (@name to ask one bot, paste a key to save it)`}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        />
        <button className="primary send" disabled={!text.trim()}>Send</button>
      </form>
    </section>
  );
}
