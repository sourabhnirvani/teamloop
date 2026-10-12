import { useEffect, useState } from "react";
import { api, type SecurityInfo } from "../api";
import { Icon } from "../Icon";

const PROMISES = [
  "Keys are locked in an encrypted vault on this PC and never shown in full",
  "A tool call that carries a key is refused before it runs",
  "Programs the crew starts get no keys in their environment",
  "Bots can't open the vault, .env files or databases",
  "Keys are hidden from chat, logs, traces and approval cards",
];

export function SecurityPage({ header }: { header: React.ReactNode }) {
  const [info, setInfo] = useState<SecurityInfo | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.security().then(setInfo).catch((e) => setError((e as Error).message));
  }, []);

  const when = (ts: number) =>
    new Date(ts * 1000).toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

  return (
    <>
      {header}
      <p className="lead">
        {info ? `${info.locked} key${info.locked === 1 ? "" : "s"} locked` : "Checking the vault…"}
        {info && info.names.length > 0 && <><br /><small>{info.names.join(" · ")}</small></>}
      </p>
      <ul className="list">
        {PROMISES.map((p) => <li key={p}><Icon name="ok" size={16} className="ok-mark" /><span>{p}</span></li>)}
      </ul>
      <h3>Blocked</h3>
      <ul className="list">
        {info && info.blocked.length === 0 && <li><span>Nothing blocked yet.</span></li>}
        {info && [...info.blocked].reverse().map((b, i) => (
          <li key={`${b.ts}-${i}`}>
            <span><b>{b.tool}</b> by {b.bot || "a bot"}: {b.what}<br /><small>{when(b.ts)}</small></span>
          </li>
        ))}
      </ul>
      {error && <div className="note">{error}</div>}
    </>
  );
}
