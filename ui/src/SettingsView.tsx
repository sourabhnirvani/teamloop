import { useCallback, useEffect, useState } from "react";
import { api, onLaptop, type AllowRule, type Bot, type HubStatus, type KeyInfo, type ModelInfo, type Pairing, type Phone, type Routine, type Settings, type Usage } from "./api";
import { Avatar } from "./Avatar";
import { go, href } from "./router";
import { applyUpdate, askToNotify, runningVersion, updateAvailable } from "./update";

// Settings: a home page of cards (each with a live status line) that open their own page, on laptop and phone.

type Page = "keys" | "models" | "usage" | "routines" | "phone" | "chrome" | "allowed" | "appearance";

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

const SIGN_IN: { name: string; url: string; note?: string }[] = [
  { name: "Gmail", url: "https://mail.google.com" },
  { name: "WhatsApp Web", url: "https://web.whatsapp.com" },
  { name: "Telegram Web", url: "https://web.telegram.org" },
  { name: "LinkedIn", url: "https://www.linkedin.com/login" },
  { name: "Discord", url: "https://discord.com/login", note: "Discord's rules forbid automating user accounts; it could get banned." },
];

export function SettingsView({ page, bots, theme, setTheme }: {
  page: string | null; bots: Record<string, Bot>; theme: string; setTheme: (t: string) => void;
}) {
  const [keys, setKeys] = useState<KeyInfo[]>([]);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [usage, setUsage] = useState<Usage[]>([]);
  const [routines, setRoutines] = useState<Routine[]>([]);
  const [phones, setPhones] = useState<Phone[] | null>(null);
  const [rules, setRules] = useState<AllowRule[]>([]);
  const [hub, setHub] = useState<HubStatus | null>(null);
  const [note, setNote] = useState("");

  const refresh = useCallback(() => {
    api.keys().then(setKeys).catch(() => {});
    api.models().then(setModels).catch(() => {});
    api.settings().then(setSettings).catch(() => {});
    api.usage().then(setUsage).catch(() => {});
    api.routines().then(setRoutines).catch(() => {});
    api.allowed().then(setRules).catch(() => {});
    api.hub().then(setHub).catch(() => {});
    if (onLaptop) api.phones().then(setPhones).catch(() => setPhones(null));
  }, []);
  useEffect(refresh, [refresh, page]);
  useEffect(() => setNote(""), [page]);

  const totals = usage.reduce((a, u) => ({ req: a.req + u.requests, tok: a.tok + u.tokens_in + u.tokens_out }), { req: 0, tok: 0 });
  const keyCount = keys.reduce((n, k) => n + k.keys.length, 0);
  const ready = models.filter((m) => m.has_key && m.models.some((x) => !x.dead)).length;
  const providerName = (id: string | null | undefined) => models.find((m) => m.provider === id)?.name ?? "Auto";
  const version = runningVersion()?.replace(/^index-|\.js$/g, "") ?? "dev";

  async function save(patch: Partial<Settings>) {
    const before = settings;
    try {
      setSettings(await api.setSettings(patch));
    } catch (e) {
      setSettings(before);
      setNote(`Couldn't save: ${(e as Error).message}`);
    }
  }

  if (!page || !(["keys", "models", "usage", "routines", "phone", "chrome", "allowed", "appearance"] as string[]).includes(page)) {
    const card = (p: Page, icon: string, title: string, status: string) => (
      <button className="set-card" onClick={() => go(href("settings", p))}>
        <span className="set-icon">{icon}</span>
        <span className="set-text"><b>{title}</b><small>{status}</small></span>
        <span className="chev">›</span>
      </button>
    );
    return (
      <div className="page settings-page">
        <h1>Settings</h1>
        <h2>AI</h2>
        {card("keys", "🔑", "API keys", keyCount ? `${keyCount} key${keyCount > 1 ? "s" : ""} for ${plural(keys.filter((k) => k.keys.length).length, "service")} · locked in the vault` : "No keys yet: paste a free Gemini or Groq key")}
        {card("models", "🧠", "AI models", `${ready} free provider${ready === 1 ? "" : "s"} ready · crew uses ${providerName(settings?.crew_model)}`)}
        {card("usage", "📊", "Usage & Save tokens", `Save tokens ${settings?.save_tokens ? "ON" : "OFF"} · ${totals.req} requests today · $0`)}
        <h2>Crew</h2>
        {card("routines", "⏰", "Routines", routines.length ? `${routines.length} scheduled` : "None yet: “every Monday at 9am, …”")}
        <h2>Devices</h2>
        {card("phone", "📱", "Your phone", `${onLaptop ? (phones ? `${plural(phones.length, "phone")} paired` : "Pair a phone with a QR code") : "This phone is paired"} · ${hub?.connected ? "fixed link on" : hub?.configured ? "fixed link connecting" : "fixed link not set up"}`)}
        {card("chrome", "🌐", "Crew's Chrome", "Sign in to sites once; bots read and draft, you send")}
        <h2>Safety</h2>
        {card("allowed", "✅", "Always-allowed actions", rules.length ? `${plural(rules.length, "rule")} · the crew goes ahead without asking` : "None: every risky action asks first")}
        <h2>App</h2>
        {card("appearance", "🎨", "Appearance & updates", `${theme === "dark" ? "Dark" : "Light"} · version ${version}`)}
      </div>
    );
  }

  const header = (title: string) => (
    <div className="page-head">
      <button className="icon" onClick={() => go(href("settings"))} aria-label="Back to Settings">‹</button>
      <h1>{title}</h1>
    </div>
  );

  return (
    <div className="page settings-page">
      {page === "keys" && <KeysPage header={header("🔑 API keys")} keys={keys} onSaved={(text) => { setNote(text); refresh(); }} note={note} />}
      {page === "models" && settings && (
        <ModelsPage header={header("🧠 AI models")} models={models} settings={settings} bots={bots} save={save} note={note} setNote={setNote} refresh={refresh} />
      )}
      {page === "usage" && settings && (
        <>
          {header("📊 Usage & Save tokens")}
          {note && <div className="note">{note}</div>}
          <label className="switch-row">
            <span><b>Save tokens</b><small>Shorter chat history, fewer steps per job, no group rounds. Turn it on when your free keys run low. You can also say “save tokens on” in any chat.</small></span>
            <input type="checkbox" role="switch" checked={settings.save_tokens} onChange={(e) => save({ save_tokens: e.target.checked })} />
          </label>
          <div className="stat-row">
            <div><b>{totals.req}</b><small>model calls today</small></div>
            <div><b>{totals.tok >= 1000 ? `${(totals.tok / 1000).toFixed(1)}k` : totals.tok}</b><small>tokens</small></div>
            <div><b className="free">$0</b><small>free models only</small></div>
          </div>
          <ul className="list">
            {usage.length === 0 && <li><span>No model calls yet today.</span></li>}
            {usage.map((u) => (
              <li key={u.provider + u.model}><b>{providerName(u.provider) === "Auto" ? u.provider : providerName(u.provider)}</b>
                <span>{u.model}: {u.requests} calls · {(u.tokens_in + u.tokens_out).toLocaleString()} tokens</span></li>
            ))}
          </ul>
        </>
      )}
      {page === "routines" && (
        <>
          {header("⏰ Routines")}
          <p className="lead">Ask in any chat, for example “every Monday at 9am, remind me about the report” or “in 30 minutes, check the build”.</p>
          <ul className="list">
            {routines.length === 0 && <li><span>No routines yet.</span></li>}
            {routines.map((r) => (
              <li key={r.id}>
                <b>{r.schedule}</b>
                <span>{r.text}<br /><small>next {new Date(r.next_run * 1000).toLocaleString([], { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</small></span>
                <button onClick={() => window.confirm(`Cancel “${r.text}”?`) && api.cancelRoutine(r.id).then(refresh).catch((e) => setNote(String(e.message)))}>Cancel</button>
              </li>
            ))}
          </ul>
          {note && <div className="note">{note}</div>}
        </>
      )}
      {page === "phone" && <PhonePage header={header("📱 Your phone")} phones={phones} refresh={refresh} hub={hub} setHub={setHub} />}
      {page === "chrome" && (
        <>
          {header("🌐 Crew's Chrome")}
          <p className="lead">The bots have their own Chrome window on the laptop (its own profile). Sign in to a site there once, and Web and Inbox can read and draft there. They never press Send without your OK, and you always type passwords yourself.</p>
          {!onLaptop && <div className="note">These open on the laptop's screen.</div>}
          <ul className="list">
            {SIGN_IN.map((s) => (
              <li key={s.name}>
                <b>{s.name}</b>
                <span>{s.note ?? s.url.replace("https://", "")}</span>
                <button onClick={async () => {
                  setNote(`Opening ${s.name} in the crew's Chrome…`);
                  try { setNote((await api.signIn(s.url)).text); } catch (e) { setNote((e as Error).message); }
                }}>Open sign-in</button>
              </li>
            ))}
          </ul>
          {note && <div className="note">{note}</div>}
        </>
      )}
      {page === "allowed" && (
        <>
          {header("✅ Always-allowed actions")}
          <p className="lead">“Always allow” on an approval card adds a rule here, and the crew then does that exact action without asking. It's never offered for sending, posting, buying, deleting, replacing files or power. Remove a rule and the card comes back.</p>
          <ul className="list">
            {rules.length === 0 && <li><span>None yet.</span></li>}
            {rules.map((r) => (
              <li key={r.id}>
                <span>{r.label}<br /><small>added {new Date(r.added * 1000).toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</small></span>
                <button className="deny" onClick={() => api.forgetAllowed(r.id).then(refresh).catch((e) => setNote(String(e.message)))}>Remove</button>
              </li>
            ))}
          </ul>
          {note && <div className="note">{note}</div>}
        </>
      )}
      {page === "appearance" && (
        <>
          {header("🎨 Appearance & updates")}
          <div className="seg" role="radiogroup" aria-label="Theme">
            {["dark", "light"].map((t) => (
              <button key={t} role="radio" aria-checked={theme === t} className={theme === t ? "on" : ""} onClick={() => setTheme(t)}>
                {t === "dark" ? "☾ Dark" : "☀ Light"}
              </button>
            ))}
          </div>
          <div className="switch-row">
            <span><b>Notifications</b><small>A note on this device's screen when an update is ready or a bot needs your OK while TeamLoop is in the background.{"Notification" in window ? ` Now: ${Notification.permission === "granted" ? "on" : Notification.permission === "denied" ? "blocked in the browser's site settings" : "off"}.` : " This browser can't show them."}</small></span>
            {"Notification" in window && Notification.permission === "default" && (
              <button onClick={async () => { const r = await askToNotify(); setNote(r === "granted" ? "Notifications are on." : "Notifications stay off."); refresh(); }}>Turn on</button>
            )}
          </div>
          <div className="switch-row">
            <span><b>Version</b><small><code>{version}</code> · updates are checked by themselves; you're asked when one is ready</small></span>
            <button onClick={async () => {
              setNote("Checking for a new version…");
              if (await updateAvailable()) { setNote("Updating…"); await applyUpdate(); } else setNote("You have the latest version.");
            }}>Check for updates</button>
          </div>
          {note && <div className="note">{note}</div>}
        </>
      )}
    </div>
  );
}

function KeysPage({ header, keys, onSaved, note }: { header: React.ReactNode; keys: KeyInfo[]; onSaved: (text: string) => void; note: string }) {
  const [paste, setPaste] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <>
      {header}
      <p className="lead">Paste free keys here, or straight into any chat: Gemini, Groq, OpenRouter, NVIDIA, Cerebras, or “neatlogs key: …”. Each one is recognised, tested, then locked in the vault, and it's hidden everywhere after that.</p>
      <textarea value={paste} onChange={(e) => setPaste(e.target.value)} rows={3} placeholder="Paste keys here" aria-label="Paste keys" />
      <button className="primary" disabled={!paste.trim() || busy} onClick={async () => {
        setBusy(true);
        try {
          const out = await api.addKeys(paste);
          setPaste("");
          onSaved(out.map((o) => o.text).join(" "));
        } catch (e) {
          onSaved((e as Error).message);
        } finally {
          setBusy(false);
        }
      }}>{busy ? "Checking…" : "Save keys"}</button>
      {note && <div className="note">{note}</div>}
      <ul className="list">
        {keys.map((k) => (
          <li key={k.id}><b>{k.name}</b><span>{k.needs_key ? (k.keys.length ? k.keys.join(", ") : "no key") : "runs on this laptop"}</span></li>
        ))}
      </ul>
    </>
  );
}

function ModelsPage({ header, models, settings, bots, save, note, setNote, refresh }: {
  header: React.ReactNode; models: ModelInfo[]; settings: Settings; bots: Record<string, Bot>;
  save: (p: Partial<Settings>) => Promise<void>; note: string; setNote: (s: string) => void; refresh: () => void;
}) {
  const [checking, setChecking] = useState(false);
  const usable = models.filter((m) => m.has_key);
  return (
    <>
      {header}
      <p className="lead">The bots try these in order. All free: when one is busy or out of today's quota, the next one answers.</p>
      <label className="field">Model for the whole crew
        <select value={settings.crew_model ?? ""} onChange={(e) => save({ crew_model: e.target.value || null })}>
          <option value="">Auto: the best free model that answers</option>
          {usable.map((m) => <option key={m.provider} value={m.provider}>{m.name}</option>)}
        </select>
      </label>
      <h3>Each bot</h3>
      {Object.values(bots).map((b) => (
        <label key={b.id} className="field inline">
          <span className="who-inline"><Avatar bot={b} size={24} /> {b.name}</span>
          <select value={settings.bot_models[b.id] ?? ""} onChange={(e) => {
            const next = { ...settings.bot_models };
            if (e.target.value) next[b.id] = e.target.value;
            else delete next[b.id];
            save({ bot_models: next });
          }}>
            <option value="">same as the crew</option>
            {usable.map((m) => <option key={m.provider} value={m.provider}>{m.name}</option>)}
          </select>
        </label>
      ))}
      <button className="primary" disabled={checking} onClick={async () => {
        setChecking(true);
        setNote("Asking every model a tiny question…");
        try { setNote((await api.checkModels()).summary); refresh(); } catch (e) { setNote(`The check failed: ${(e as Error).message}`); } finally { setChecking(false); }
      }}>{checking ? "Checking…" : "Check which models work"}</button>
      {note && <div className="note">{note}</div>}
      <ul className="list">
        {models.map((m) => {
          const live = m.models.filter((x) => !x.dead);
          return (
            <li key={m.provider}>
              <b>{m.name}</b>
              <span className={m.has_key && live.length ? "ok" : ""}>
                {!m.has_key ? "No key: add one in API keys" : live.length ? `Ready · ${live.map((x) => x.id).join(", ")}` : "Not answering right now"}
              </span>
            </li>
          );
        })}
      </ul>
    </>
  );
}

function HubBox({ hub, setHub }: { hub: HubStatus | null; setHub: (h: HubStatus) => void }) {
  const running = !!hub?.setup && !/^(Done|Failed)/.test(hub.setup);
  useEffect(() => {
    if (!running) return;
    const t = window.setInterval(() => api.hub().then(setHub).catch(() => {}), 2000); // follow the setup steps
    return () => window.clearInterval(t);
  }, [running, setHub]);
  if (!hub) return null;
  return (
    <div className="hub-box">
      <div className="switch-row">
        <span>
          <b>Fixed phone link {hub.connected ? "· on ✅" : hub.configured ? "· connecting…" : ""}</b>
          <small>{hub.connected && hub.url ? <>The phone app's permanent address: <a href={hub.url} target="_blank" rel="noreferrer">{hub.url}</a>. It keeps working after the laptop restarts.</>
            : hub.configured ? `Set up at ${hub.url}; this laptop is reconnecting${hub.error ? ` (${hub.error})` : ""}.`
            : "Without it the phone link changes every time the laptop restarts. With it, the phone app keeps one address: a tiny free hub on your own Cloudflare account that this laptop dials out to (nothing at home is opened, $0)."}</small>
        </span>
        {onLaptop && !hub.connected && (
          <button className="primary" disabled={running} onClick={() => api.hubSetup().then(setHub).catch((e: Error) => setHub({ ...hub, setup: `Failed: ${e.message}` }))}>
            {running ? "Setting up…" : hub.configured ? "Set up again" : "Set up"}
          </button>
        )}
      </div>
      {hub.setup && <div className="note">{hub.setup}</div>}
      {onLaptop && !hub.configured && !running && (
        <p className="quiet">Set up opens your browser once: sign in to a free Cloudflare account (or make one, no card) and press Allow. The rest runs by itself.</p>
      )}
    </div>
  );
}

function PhonePage({ header, phones, refresh, hub, setHub }: {
  header: React.ReactNode; phones: Phone[] | null; refresh: () => void; hub: HubStatus | null; setHub: (h: HubStatus) => void;
}) {
  const [pairing, setPairing] = useState<Pairing | null>(null);
  const [note, setNote] = useState("");
  useEffect(() => {
    if (!pairing) return;
    const t = window.setInterval(refresh, 3000); // show the phone as soon as it pairs
    const stop = window.setTimeout(() => setPairing(null), Math.max(0, pairing.expires * 1000 - Date.now()));
    return () => { window.clearInterval(t); window.clearTimeout(stop); };
  }, [pairing, refresh]);

  if (!onLaptop) {
    return (
      <>
        {header}
        <p className="lead">This phone is paired with the laptop. Chats, approvals, routines and every setting work here while the laptop is on. Pairing or removing phones is done on the laptop: Settings → Your phone.</p>
        <HubBox hub={hub} setHub={setHub} />
        <p className="lead">New version on the laptop? You'll see “A new version is ready · Update” at the top, or use Settings → Appearance & updates.</p>
      </>
    );
  }
  return (
    <>
      {header}
      <HubBox hub={hub} setHub={setHub} />
      <p className="lead">Use TeamLoop on your phone while this laptop is on. Press Pair, scan the code with the phone camera (or open the link and type the code), then “Add to Home screen”.{hub?.connected ? " The code uses the fixed link." : ""}</p>
      <button className="primary" onClick={async () => {
        setNote("Opening a secure link to this laptop…");
        try { setPairing(await api.pairPhone()); setNote(""); } catch (e) { setNote((e as Error).message); }
      }}>{pairing ? "New code" : "Pair a phone"}</button>
      {note && <div className="note">{note}</div>}
      {pairing && (
        <div className="pairing">
          {/* the QR is an SVG made by our own server */}
          <div className="qr" dangerouslySetInnerHTML={{ __html: pairing.qr }} />
          <p><b className="code">{pairing.code}</b><br />Works once, until {new Date(pairing.expires * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}.<br />
            <a href={pairing.link} target="_blank" rel="noreferrer">{pairing.link.split("/pair")[0]}</a></p>
        </div>
      )}
      <ul className="list">
        {(phones ?? []).length === 0 && <li><span>No phones paired yet.</span></li>}
        {(phones ?? []).map((p) => (
          <li key={p.id}>
            <b>{p.name}</b>
            <span>paired {new Date(p.paired * 1000).toLocaleDateString()} · last seen {new Date(p.last_seen * 1000).toLocaleString()}</span>
            <button className="deny" onClick={() => window.confirm(`Remove ${p.name}? It will have to pair again.`) && api.removePhone(p.id).then(refresh)}>Remove</button>
          </li>
        ))}
      </ul>
    </>
  );
}
