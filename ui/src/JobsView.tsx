import { useEffect, useState } from "react";
import { api, type Chat, type Job } from "./api";
import "./hoodie-views.css";

// Jobs: commands Desk left running in the background (servers, long builds), with their latest output.

const LABEL: Record<Job["state"], string> = { running: "Running", done: "Finished", failed: "Failed", stopped: "Stopped" };

export function JobsView({ chats, onChat }: { chats: Chat[]; onChat: (id: string) => void }) {
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [detail, setDetail] = useState<Job | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = () => api.jobs().then(setJobs).catch((e: Error) => setError(e.message));
    load();
    const t = window.setInterval(load, 3000);
    return () => window.clearInterval(t);
  }, []);

  useEffect(() => {
    if (!open) { setDetail(null); return; }
    const load = () => api.job(open).then(setDetail).catch(() => setDetail(null));
    load();
    const t = window.setInterval(load, 2000); // the output keeps coming while it runs
    return () => window.clearInterval(t);
  }, [open]);

  const chatTitle = (id: string) => chats.find((c) => c.id === id)?.title ?? id;

  return (
    <div className="page jobs-page hv-jobs">
      <h1>Jobs</h1>
      <p className="lead">Commands Desk runs in the background (servers, watchers, long builds). Their output is saved; stop any of them here.</p>
      {error && <div className="error">{error}</div>}
      {jobs && jobs.length === 0 && <p className="quiet">No background jobs. Desk starts one when a command needs to keep running, like “start the dev server”.</p>}
      <ul className="job-list">
        {(jobs ?? []).map((j) => (
          <li key={j.id} className={`job ${j.state}`}>
            <button className="job-row" aria-expanded={open === j.id} onClick={() => setOpen(open === j.id ? null : j.id)}>
              <span className={`pill ${j.state}`}>{LABEL[j.state]}{j.exit_code !== null && j.state !== "stopped" ? ` · ${j.exit_code}` : ""}</span>
              <code>{j.command}</code>
              <small>{new Date(j.started * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</small>
            </button>
            {open === j.id && (
              <div className="job-detail">
                <pre>{detail?.output || "(no output yet)"}</pre>
                <div className="job-actions">
                  <button className="link" onClick={() => onChat(j.chat_id)}>Open {chatTitle(j.chat_id)}</button>
                  {j.state === "running" && (
                    <button className="deny" onClick={() => api.stopJob(j.id).then(setDetail).catch((e: Error) => setError(e.message))}>Stop</button>
                  )}
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
