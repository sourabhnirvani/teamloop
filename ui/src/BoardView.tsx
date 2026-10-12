import { useLayoutEffect, useRef, useState } from "react";
import { api, type Bot, type Task, type TaskStatus } from "./api";
import { Avatar, type Move } from "./Avatar";
import { Icon } from "./Icon";
import "./hoodie-views.css";

// The Board: every step S hands to a teammate shows up here by itself (Doing -> Done, or Blocked with the
// reason), next to your own to-dos. Cards move with the status menu; a to-do can be handed to the crew.

const COLUMNS: { status: TaskStatus; title: string; empty: string }[] = [
  { status: "todo", title: "To do", empty: "Your own to-dos. Add one above." },
  { status: "doing", title: "Doing", empty: "Steps the crew is working on right now." },
  { status: "blocked", title: "Blocked", empty: "Steps that failed, were stopped, or got a no." },
  { status: "done", title: "Done", empty: "Finished steps land here." },
];

// A card's note, four lines at most; "Show all" appears only when the text really is cut off
function Note({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const [cut, setCut] = useState(false);
  const box = useRef<HTMLParagraphElement>(null);
  useLayoutEffect(() => {
    // measured again whenever its size changes: on a phone the column starts hidden (0 px), then a tab shows it
    const el = box.current;
    if (!el || open) return;
    const check = () => setCut(el.scrollHeight > el.clientHeight + 1);
    check();
    const watch = new ResizeObserver(check);
    watch.observe(el);
    return () => watch.disconnect();
  }, [text, open]);
  return (
    <>
      <p ref={box} className={`task-note ${open ? "open" : ""}`}>{text}</p>
      {(cut || open) && <button className="link note-more" onClick={() => setOpen(!open)}>{open ? "Show less" : "Show all"}</button>}
    </>
  );
}

function ago(ts: number) {
  const s = Date.now() / 1000 - ts;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(ts * 1000).toLocaleDateString();
}

// a card's time: the clock today, "yesterday", else the date
function stamp(ts: number) {
  const d = new Date(ts * 1000), now = new Date();
  if (d.toDateString() === now.toDateString()) return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  if (d.toDateString() === new Date(now.getTime() - 86400000).toDateString()) return "yesterday";
  return d.toLocaleDateString();
}

const WORDS = ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve"];
const word = (n: number) => WORDS[n] ?? String(n);

// The job that just finished, if the board shows one: the newest Done card is a crew step, and every step of that
// run (same chat, created within 10 minutes of the next) is Done too. Nothing is shown otherwise.
function finishedJob(tasks: Task[]) {
  const newest = tasks.filter((t) => t.status === "done").sort((a, b) => b.updated - a.updated)[0];
  if (!newest?.chat_id || newest.source !== "delegate") return null;
  const mine = tasks.filter((t) => t.chat_id === newest.chat_id && t.source === "delegate").sort((a, b) => b.created - a.created);
  const job = [mine[0]];
  for (let i = 1; i < mine.length && job[job.length - 1].created - mine[i].created < 600; i++) job.push(mine[i]);
  if (!job.includes(newest) || job.some((t) => t.status !== "done")) return null;
  job.reverse();
  const secs = Math.max(0, Math.max(...job.map((t) => t.updated)) - job[0].created);
  return { chat: newest.chat_id, steps: job, took: secs < 60 ? `${Math.round(secs)} s` : `${Math.round(secs / 60)} min` };
}

// The newest run of crew steps (same chat, created within 10 minutes of the next), finished or not: the Crew Room's
// "today's job" card.
export function latestRun(tasks: Task[]) {
  const mine = tasks.filter((t) => t.chat_id && t.source === "delegate").sort((a, b) => b.created - a.created);
  if (!mine.length) return null;
  const run = [mine[0]];
  for (let i = 1; i < mine.length && mine[i].chat_id === run[0].chat_id && run[run.length - 1].created - mine[i].created < 600; i++) run.push(mine[i]);
  return { chat: run[0].chat_id as string, steps: run.reverse() };
}

export function BoardView({ tasks, bots, look, onChat, titles }: {
  tasks: Task[]; bots: Record<string, Bot>; look: (id: string) => { move: Move; sign: string | null }; onChat: (id: string) => void;
  titles?: Record<string, string>; // chat id -> title, to name the finished job
}) {
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // phones show one column at a time: the one you picked, else the first with something in it (not an empty "Doing")
  const [picked, setShow] = useState<TaskStatus | null>(null);
  const show = picked ?? (["doing", "blocked", "todo", "done"] as TaskStatus[]).find((s) => tasks.some((t) => t.status === s)) ?? "doing";

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
    const sorry = t.status === "blocked" && /^not done:/i.test(t.note);
    const yours = t.source === "manual" && t.status === "todo";
    return (
      <article key={t.id} className={`task hv-task ${t.status}`}>
        <header>
          <span className="task-id hv-id">#{t.id} · {yours ? "yours" : stamp(t.updated)}</span>
          <button className="icon task-remove" aria-label={`Remove task ${t.id}`} title="Remove"
                  onClick={() => window.confirm(`Remove “${t.title}” from the Board?`) && act(api.deleteTask(t.id))}><Icon name="no" size={16} /></button>
        </header>
        <b className="hv-task-title">{t.title}</b>
        {yours && <time className="hv-meta">added {ago(t.created)}</time>}
        {t.note && (sorry ? (
          <div className="hv-sorry">
            <img src="/mascot/oops.webp" alt="S looking sorry" width={46} height={62} />
            <div><Note text={t.note} /></div>
          </div>
        ) : <Note text={t.note} />)}
        {(bot || by) && (
          <div className="task-who hv-flow">
            {by && <><Avatar bot={by} size={22} /><span>{by.name}</span><span className="arrow"><Icon name="arrow" size={14} /></span></>}
            {bot && <><Avatar bot={bot} {...(t.status === "doing" ? look(bot.id) : { move: "idle" as Move, sign: null })} size={22} /><span>{bot.name}</span></>}
          </div>
        )}
        <footer>
          <select aria-label={`Status of task ${t.id}`} value={t.status} onChange={(e) => act(api.patchTask(t.id, { status: e.target.value as TaskStatus }))}>
            {COLUMNS.map((c) => <option key={c.status} value={c.status}>{c.title}</option>)}
          </select>
          {t.status === "todo" && (
            <button className="link hv-lnk" onClick={() => act(api.send("team", t.title).then(() => api.patchTask(t.id, { status: "doing", note: "Sent to the Team chat." })))}>
              Ask the crew
            </button>
          )}
          {t.chat_id && <button className="link hv-lnk" onClick={() => onChat(t.chat_id!)}>Open chat</button>}
        </footer>
      </article>
    );
  };

  const job = finishedJob(tasks);
  const doers = job ? [...new Set(job.steps.map((t) => (t.bot ? bots[t.bot]?.name : undefined)).filter(Boolean))] : [];

  return (
    <div className="board-page hv-board">
      <div className="board-head">
        <h1>Board</h1>
        <form onSubmit={add} className="board-add">
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="New to-do…" aria-label="New to-do" maxLength={200} />
          <button className="primary hv-add" disabled={!title.trim() || busy}><Icon name="add" size={18} />Add</button>
        </form>
      </div>
      {error && <div className="error">{error}</div>}
      {job && (
        <section className="hv-done" aria-label="Job done">
          <img src="/mascot/cheer.webp" alt="S cheering" />
          <div className="hv-done-text">
            <div className="hv-done-k"><Icon name="spark" size={14} />Job done · {job.took}</div>
            <div className="hv-done-h">{word(job.steps.length)} of {word(job.steps.length).toLowerCase()} {job.steps.length === 1 ? "step" : "steps"} done.</div>
            <div className="hv-done-s">{titles?.[job.chat] ? `${titles[job.chat]}: ` : ""}{job.steps.map((t) => t.title).join(" · ")}{doers.length ? `, by ${doers.join(", ")}` : ""}</div>
          </div>
          <button className="hv-done-open" onClick={() => onChat(job.chat)}>Open chat</button>
        </section>
      )}
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
            <section key={c.status} className={`column hv-col ${show === c.status ? "shown" : ""}`} aria-label={c.title}>
              <h2>{c.title} <span className="count">{list.length}</span></h2>
              {list.length === 0 && <p className="quiet hv-empty">{c.empty}</p>}
              {list.map(card)}
            </section>
          );
        })}
      </div>
    </div>
  );
}
