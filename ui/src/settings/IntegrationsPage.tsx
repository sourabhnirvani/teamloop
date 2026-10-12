import { useEffect, useState } from "react";

type Integrations = {
  telegram: { on: boolean; bot_name: string; allowed_ids_count: number; error: string };
  tracing: { on: boolean };
  default_provider: string | null;
};

async function send<T>(path: string, method: "GET" | "POST" | "DELETE", body?: unknown): Promise<T> {
  const res = await fetch(path, method === "GET" ? undefined : {
    method, headers: { "content-type": "application/json" }, body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) window.location.assign("/pair");
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch { /* not JSON */ }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

// Settings > Telegram and tracing: status rows, a bot token box, the allowed people, and how to make a bot.
export function IntegrationsPage({ header }: { header: React.ReactNode }) {
  const [info, setInfo] = useState<Integrations | null>(null);
  const [token, setToken] = useState("");
  const [ids, setIds] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  const load = () => send<Integrations>("/api/integrations", "GET").then(setInfo).catch((e) => setNote((e as Error).message));
  useEffect(() => { load(); }, []);

  const save = async () => {
    setBusy(true);
    setNote("");
    try {
      const body: Record<string, string> = {};
      if (token.trim()) body.token = token.trim();
      if (ids.trim()) body.allowed_ids = ids.trim();
      const t = await send<Integrations["telegram"]>("/api/integrations/telegram", "POST", body);
      setToken("");
      setNote(t.on ? `Telegram is on as ${t.bot_name}. Message your bot to talk to the crew.` : (t.error || "Saved."));
      await load();
    } catch (e) {
      setNote((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const turnOff = async () => {
    setBusy(true);
    try {
      await send("/api/integrations/telegram", "DELETE");
      setNote("Telegram is off.");
      await load();
    } catch (e) {
      setNote((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const tg = info?.telegram;
  return (
    <>
      {header}
      <ul className="list">
        <li>
          <span>
            <b>Telegram</b><br />
            <small>
              {!tg ? "Checking…" : tg.on ? `On as ${tg.bot_name} · ${tg.allowed_ids_count} allowed ${tg.allowed_ids_count === 1 ? "person" : "people"}`
                : tg.error ? `Off: ${tg.error}` : "Off"}
            </small>
          </span>
          {tg?.on && <button className="deny" disabled={busy} onClick={turnOff}>Turn off</button>}
        </li>
        <li>
          <span><b>neatlogs tracing</b><br /><small>{info ? (info.tracing.on ? "On: every job is traced" : "Off: add a neatlogs key under API keys") : "Checking…"}</small></span>
        </li>
        <li>
          <span><b>Models</b><br /><small>{info ? (info.default_provider ? `First choice: ${info.default_provider}` : "No model key yet") : "Checking…"}</small></span>
        </li>
      </ul>

      <h3>Telegram bot</h3>
      <input type="password" autoComplete="off" placeholder={tg?.on ? "Paste a new bot token to replace it" : "Bot token from @BotFather"}
        value={token} onChange={(e) => setToken(e.target.value)} />
      <input inputMode="numeric" autoComplete="off" placeholder="Allowed people: Telegram user ids, comma-separated"
        value={ids} onChange={(e) => setIds(e.target.value)} />
      <button className="primary" disabled={busy || (!token.trim() && !ids.trim())} onClick={save}>
        {busy ? "Checking with Telegram…" : "Save and connect"}
      </button>
      {note && <div className="note">{note}</div>}

      <p className="lead">
        How to make a bot: in Telegram, open <b>@BotFather</b>, send <b>/newbot</b>, pick a name, and copy the token it
        gives you into the box above. Then send your bot any message: it replies with your user id, which goes in
        "Allowed people". Only those people can talk to the crew, because the bot can use this laptop.
      </p>
      <p className="lead">
        In Telegram: /chat to pick a chat, /chat scout to talk to one bot, /stop, /sleep and /wake, /crew. Approval cards
        arrive with Approve and Deny buttons.
      </p>
    </>
  );
}
