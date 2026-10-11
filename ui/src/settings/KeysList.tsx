import { useEffect, useState } from "react";
import { req } from "./http";

export type KeyEntry = {
  env: string;
  provider: string;
  provider_name: string;
  masked: string;
  status: "works" | "rejected" | "unchecked";
  reason: string;
  source: "vault" | "env";
};

const LABEL = { works: "✅ Works", rejected: "❌ Rejected", unchecked: "⏳ Not tested yet" } as const;

// One row per saved key: works or rejected (and why), remove, test all again, clean up rejected ones.
// `onChanged` lets the page around it refresh its own key list after a remove or clean-up.
export function KeysList({ header, onChanged }: { header?: React.ReactNode; onChanged?: () => void }) {
  const [rows, setRows] = useState<KeyEntry[] | null>(null);
  const [busy, setBusy] = useState("");
  const [note, setNote] = useState("");

  const load = () => req<KeyEntry[]>("/api/keys/entries").then(setRows).catch((e) => setNote((e as Error).message));
  useEffect(() => { load(); }, []);

  const act = async (what: string, run: () => Promise<string>) => {
    setBusy(what);
    setNote("");
    try {
      setNote(await run());
      await load();
      onChanged?.();
    } catch (e) {
      setNote((e as Error).message);
    } finally {
      setBusy("");
    }
  };

  const testAll = () => act("test", async () => {
    const fresh = await req<KeyEntry[]>("/api/keys/test", "POST");
    const bad = fresh.filter((r) => r.status === "rejected").length;
    return `Tested ${fresh.length} key${fresh.length === 1 ? "" : "s"}: ${bad ? `${bad} rejected` : "none rejected"}.`;
  });
  const remove = (r: KeyEntry) => act(r.env, async () => {
    await req(`/api/keys/${encodeURIComponent(r.env)}`, "DELETE");
    return `Removed the ${r.provider_name} key ${r.masked}.`;
  });
  const cleanUp = () => act("cleanup", async () => {
    const done = await req<{ removed: string[]; kept_env: string[] }>("/api/keys/cleanup", "POST");
    const kept = done.kept_env.length ? ` ${done.kept_env.join(", ")} come${done.kept_env.length === 1 ? "s" : ""} from .env: remove ${done.kept_env.length === 1 ? "it" : "them"} there.` : "";
    return `Removed ${done.removed.length} rejected key${done.removed.length === 1 ? "" : "s"}.${kept}`;
  });

  const rejected = (rows ?? []).filter((r) => r.status === "rejected");

  return (
    <>
      {header}
      <ul className="list">
        {rows === null && <li><span>Loading keys…</span></li>}
        {rows?.length === 0 && <li><span>No keys saved yet. Paste one above.</span></li>}
        {rows?.map((r) => (
          <li key={r.env}>
            <span>
              <b>{r.provider_name}</b> {r.masked}
              <br />
              <small>
                {r.status === "unchecked" && r.reason !== "not tested yet" ? "⚠️ No clear answer" : LABEL[r.status]}
                {r.status !== "works" && r.reason && r.reason !== "not tested yet" ? `: ${r.reason}` : ""}
                {r.source === "env" ? " · from .env" : ""}
              </small>
            </span>
            <button className="deny" disabled={!!busy || r.source === "env"}
              title={r.source === "env" ? "This key is set in .env; remove it there" : undefined}
              onClick={() => remove(r)}>{busy === r.env ? "Removing…" : "Remove"}</button>
          </li>
        ))}
      </ul>
      <button disabled={!!busy || !rows?.length} onClick={testAll}>{busy === "test" ? "Testing…" : "Test all again"}</button>
      {rejected.length > 0 && (
        <>
          <h2>Worth cleaning up</h2>
          <ul className="list">
            {rejected.map((r) => (
              <li key={r.env}><span>{r.provider_name} {r.masked}<br /><small>{r.reason}</small></span></li>
            ))}
          </ul>
          <button className="primary" disabled={!!busy} onClick={cleanUp}>{busy === "cleanup" ? "Cleaning up…" : "Clean up"}</button>
        </>
      )}
      {note && <div className="note">{note}</div>}
    </>
  );
}
