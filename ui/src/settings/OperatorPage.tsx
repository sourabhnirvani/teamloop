import { useEffect, useState } from "react";
import { req } from "./http";

type Step = { ts: number; bot: string; tool: string; ok: boolean; text: string };
type OperatorState = { paused: boolean; paused_since: number | null; quiet_seconds: number; recent: Step[] };

const RULES = [
  "Sends only when your words say send",
  "Pauses while you use the mouse or keyboard, then carries on by itself",
  "Ctrl+Alt+Q stops everything, from any app",
  "Never types passwords or keys",
];

// Settings > Operator safety: the rules, Paused or Ready (live), and the last screen steps.
export function OperatorPage({ header }: { header: React.ReactNode }) {
  const [state, setState] = useState<OperatorState | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => {
    let alive = true;
    const load = () => req<OperatorState>("/api/operator").then((s) => { if (alive) { setState(s); setError(""); } })
      .catch((e) => alive && setError((e as Error).message));
    load();
    const timer = setInterval(load, 1500); // pauses come and go in seconds
    return () => { alive = false; clearInterval(timer); };
  }, []);

  const stopAll = async () => {
    try {
      const r = await req<{ stopped: string[] }>("/api/stop-all", "POST");
      setNote(r.stopped.length ? `Stopped ${r.stopped.length} chat${r.stopped.length === 1 ? "" : "s"}.` : "Nothing was running.");
    } catch (e) {
      setNote((e as Error).message);
    }
  };

  const time = (ts: number) => new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

  return (
    <>
      {header}
      <p className="lead">
        {state === null ? "Checking…" : state.paused
          ? `⏸️ Paused: you're using the computer. The crew waits for ${state.quiet_seconds} quiet seconds, then carries on.`
          : "✅ Ready: the crew may use the mouse and keyboard when a job needs it."}
      </p>
      <ul className="list">
        {RULES.map((r) => <li key={r}><span>✅ {r}</span></li>)}
      </ul>
      <button className="deny" onClick={stopAll}>Stop everything now</button>
      <h3>Recent screen tasks</h3>
      <ul className="list">
        {state && state.recent.length === 0 && <li><span>No screen tasks yet.</span></li>}
        {state?.recent.map((s, i) => (
          <li key={`${s.ts}-${i}`}>
            <span>
              {s.ok ? "✅" : "❌"} <b>{s.bot || "a bot"}</b> · {s.tool}
              <br /><small>{time(s.ts)} · {s.text}</small>
            </span>
          </li>
        ))}
      </ul>
      {(note || error) && <div className="note">{note || error}</div>}
    </>
  );
}
