import { useState } from "react";
import { api, type Bot, type Task, type TaskStatus } from "./api";
import { Avatar, type Move } from "./Avatar";

// The Board: every step S hands to a teammate shows up here by itself (Doing -> Done, or Blocked with the
// reason), next to your own to-dos. Cards move with the status menu; a to-do can be handed to the crew.

const COLUMNS: { status: TaskStatus; title: string; empty: string }[] = [
  { status: "todo", title: "To do", empty: "Your own to-dos. Add one above." },
  { status: "doing", title: "Doing", empty: "Steps the crew is working on right now." },
  { status: "blocked", title: "Blocked", empty: "Steps that failed, were stopped, or got a no." },
  { status: "done", title: "Done", empty: "Finished steps land here." },
];

function ago(ts: number) {
  const s = Date.now() / 1000 - ts;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(ts * 1000).toLocaleDateString();
}

export function BoardView({ tasks, bots, look, onChat }: {
  tasks: Task[]; bots: Record<string, Bot>; look: (id: string) => { move: Move; sign: string | null }; onChat: (id: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [show, setShow] = useState<TaskStatus>("doing"); // phones show one column at a time

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    setError("");
    try {
      await api.addTask(title.trim());
      setTitle("");
      setShow("todo");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const act = (p: Promise<unknown>) => p.catch((err: Error) => setError(err.message));

  const card = (t: Task) => {
    const bot = t.bot ? bots[t.bot] : undefined;
    const by = t.by && t.by !== "user" ? bots[t.by] : undefined;
    return (
      <article key={t.id} className={`task ${t.status}`}>
        <header>
          <span className="task-id">#{t.id}</span>
          <b>{t.title}</b>
          <button className="icon" aria-label={`Remove task ${t.id}`} title="Remove" onClick={() => act(api.deleteTask(t.id))}>✕</button>
        </header>
        {(bot || by) && (
          <div className="task-who">
            {by && <><Avatar bot={by} size={20} /><span>{by.name}</span><span className="arrow">→</span></>}
            {bot && <><Avatar bot={bot} {...(t.status === "doing" ? look(bot.id) : { move: "idle" as Move, sign: null })} size={20} /><span>{bot.name}</span></>}
          </div>
        )}
        {t.note && <p className="task-note">{t.note}</p>}
        <footer>
          <select aria-label={`Status of task ${t.id}`} value={t.status} onChange={(e) => act(api.patchTask(t.id, { status: e.target.value as TaskStatus }))}>
            {COLUMNS.map((c) => <option key={c.status} value={c.status}>{c.title}</option>)}
          </select>
          {t.status === "todo" && (
            <button onClick={() => act(api.send("team", t.title).then(() => api.patchTask(t.id, { status: "doing", note: "Sent to the Team chat." })))}>
              Ask the crew
            </button>
          )}
          {t.chat_id && <button className="link" onClick={() => onChat(t.chat_id!)}>Open chat</button>}
          <time>{ago(t.updated)}</time>
        </footer>
      </article>
    );
  };

  return (
    <div className="board-page">
      <div className="board-head">
        <h1>Board</h1>
        <form onSubmit={add} className="board-add">
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="New to-do…" aria-label="New to-do" maxLength={200} />
          <button className="primary" disabled={!title.trim() || busy}>Add</button>
        </form>
      </div>
      {error && <div className="error">{error}</div>}
      <div className="seg board-tabs" role="tablist">
        {COLUMNS.map((c) => (
          <button key={c.status} role="tab" aria-selected={show === c.status} className={show === c.status ? "on" : ""} onClick={() => setShow(c.status)}>
            {c.title} <span className="count">{tasks.filter((t) => t.status === c.status).length}</span>
          </button>
        ))}
      </div>
      <div className="columns">
        {COLUMNS.map((c) => {
          const list = tasks.filter((t) => t.status === c.status);
          return (
            <section key={c.status} className={`column ${show === c.status ? "shown" : ""}`} aria-label={c.title}>
              <h2>{c.title} <span className="count">{list.length}</span></h2>
              {list.length === 0 && <p className="quiet">{c.empty}</p>}
              {list.map(card)}
            </section>
          );
        })}
      </div>
    </div>
  );
}
