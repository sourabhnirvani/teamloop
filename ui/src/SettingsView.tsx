import { useCallback, useEffect, useState } from "react";
import { canDo, choices, labelOf, localState, type Choice } from "./models";
import { api, onLaptop, type AllowRule, type Bot, type SecurityInfo, type HubStatus, type KeyInfo, type ModelInfo, type Pairing, type Phone, type Routine, type Settings, type Usage } from "./api";
import { Avatar } from "./Avatar";
import { Icon, type IconName } from "./Icon";
import { IntegrationsPage } from "./settings/IntegrationsPage";
import { KeysList } from "./settings/KeysList";
import { OperatorPage } from "./settings/OperatorPage";
import { SecurityPage } from "./settings/SecurityPage";
import { go, href } from "./router";
import { applyUpdate, askToNotify, runningVersion, updateAvailable } from "./update";
import "./hoodie-views.css";

// Settings: a home page of cards (each with a live status line) that open their own page, on laptop and phone.

type Page = "keys" | "models" | "usage" | "routines" | "phone" | "telegram" | "chrome" | "operator" | "allowed" | "security" | "appearance";
const PAGES: string[] = ["keys", "models", "usage", "routines", "phone", "telegram", "chrome", "operator", "allowed", "security", "appearance"];

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
  const [security, setSecurity] = useState<SecurityInfo | null>(null);
  const [links, setLinks] = useState<Awaited<ReturnType<typeof api.integrations>> | null>(null);
  const [note, setNote] = useState("");

  const refresh = useCallback(() => {
    api.keys().then(setKeys).catch(() => {});
    api.models().then(setModels).catch(() => {});
    api.settings().then(setSettings).catch(() => {});
    api.usage().then(setUsage).catch(() => {});
    api.routines().then(setRoutines).catch(() => {});
    api.allowed().then(setRules).catch(() => {});
    api.hub().then(setHub).catch(() => {});
    api.security().then(setSecurity).catch(() => {});
    api.integrations().then(setLinks).catch(() => {});
    if (onLaptop) api.phones().then(setPhones).catch(() => setPhones(null));
  }, []);
  useEffect(refresh, [refresh, page]);
  useEffect(() => setNote(""), [page]);

  const totals = usage.reduce((a, u) => ({ req: a.req + u.requests, tok: a.tok + u.tokens_in + u.tokens_out }), { req: 0, tok: 0 });
  const keyCount = keys.reduce((n, k) => n + k.keys.length, 0);
  const ready = models.filter((m) => m.has_key && m.running !== false && m.models.some((x) => !x.dead)).length;
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

  // the home list; on wide screens it stays on the left while a page is open on the right
  const card = (p: Page, icon: IconName, title: string, status: string) => (
    <button className={`set-card hv-set ${page === p ? "on" : ""}`} aria-current={page === p ? "page" : undefined} onClick={() => go(href("settings", p))}>
      <span className="set-icon"><Icon name={icon} size={22} /></span>
      <span className="set-text"><b>{title}</b><small>{status}</small></span>
      <span className="chev"><Icon name="next" size={18} /></span>
    </button>
  );
  const home = (
    <section className="hv-set-list">
      <h1>Settings</h1>
      <h2>AI</h2>
      {card("keys", "key", "API keys", keyCount ? `${keyCount} key${keyCount > 1 ? "s" : ""} for ${plural(keys.filter((k) => k.keys.length).length, "service")} · locked in the vault` : "No keys yet: paste a free Gemini or Groq key")}
      {card("models", "model", "AI models", `${ready} free provider${ready === 1 ? "" : "s"} ready · crew uses ${labelOf(models, settings?.crew_model)}`)}
      {card("usage", "usage", "Usage & Save tokens", `Save tokens ${settings?.save_tokens ? "ON" : "OFF"} · ${totals.req} requests today · $0`)}
      <h2>Crew</h2>
      {card("routines", "routine", "Routines", routines.length ? `${routines.length} scheduled` : "None yet: “every Monday at 9am, …”")}
      <h2>Devices</h2>
      {card("phone", "phone", "Your phone", `${onLaptop ? (phones ? `${plural(phones.length, "phone")} paired` : "Pair a phone with a QR code") : "This phone is paired"} · ${hub?.connected ? "fixed link on" : hub?.configured ? "fixed link connecting" : "fixed link not set up"}`)}
      {card("telegram", "plane", "Telegram & tracing", links ? `Telegram ${links.telegram.on ? `on as ${links.telegram.bot_name}` : "off"} · neatlogs tracing ${links.tracing.on ? "on" : "off"}` : "Talk to the crew from Telegram")}
      {card("chrome", "globe", "Crew's Chrome", "Sign in to sites once; bots read and draft, you send")}
      {card("operator", "mouse", "Operator safety", "Pauses while you use the mouse or keyboard · Ctrl+Alt+Q stops everything")}
      <h2>Safety</h2>
      {card("allowed", "shield", "Always-allowed actions", rules.length ? `${plural(rules.length, "rule")} · the crew goes ahead without asking` : "None: every risky action asks first")}
      {card("security", "lock", "Key security", security ? `${plural(security.locked, "key")} locked · ${security.blocked.length ? `${plural(security.blocked.length, "call")} blocked` : "nothing blocked"}` : "Keys stay in the vault, never in tools or programs")}
      <h2>App</h2>
      {card("appearance", "look", "Appearance & updates", `${theme === "dark" ? "Dark" : "Light"} · version ${version}`)}
    </section>
  );
  if (!page || !PAGES.includes(page)) return <div className="page settings-page hv-settings">{home}</div>;

  const header = (title: string, icon: IconName) => (
    <div className="page-head hv-head">
      <button className="icon hv-back" onClick={() => go(href("settings"))} aria-label="Back to Settings"><Icon name="back" size={24} /></button>
      <span className="head-icon"><Icon name={icon} size={24} /></span>
      <h1>{title}</h1>
    </div>
  );

  return (
    <div className="page settings-page hv-settings has-page">
      {home}
      <section className="hv-panel">
      {page === "keys" && <KeysPage header={header("API keys", "key")} keys={keys} onSaved={(text) => { setNote(text); refresh(); }} note={note} />}
      {page === "models" && settings && (
        <ModelsPage header={header("AI models", "model")} models={models} settings={settings} bots={bots} save={save} note={note} setNote={setNote} refresh={refresh} />
      )}
      {page === "usage" && settings && (
        <>
          {header("Usage & Save tokens", "usage")}
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
          {header("Routines", "routine")}
          <p className="lead">Ask in any chat, for example “every Monday at 9am, remind me about the report” or “in 30 minutes, check the build”.</p>
          <ul className="list">
            {routines.length === 0 && <li><span>No routines yet.</span></li>}
            {routines.map((r) => (
              <li key={r.id}>
                <b>{r.schedule.charAt(0).toUpperCase() + r.schedule.slice(1)}</b>
                <span>{r.text}<br /><small>next {new Date(r.next_run * 1000).toLocaleString([], { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</small></span>
                <button onClick={() => window.confirm(`Cancel “${r.text}”?`) && api.cancelRoutine(r.id).then(refresh).catch((e) => setNote(String(e.message)))}>Cancel</button>
              </li>
            ))}
          </ul>
          {note && <div className="note">{note}</div>}
        </>
      )}
      {page === "phone" && <PhonePage header={header("Your phone", "phone")} phones={phones} refresh={refresh} hub={hub} setHub={setHub} />}
      {page === "chrome" && (
        <>
          {header("Crew's Chrome", "globe")}
          <p className="lead">The bots have their own Chrome window on the laptop (its own profile). Sign in to a site there once, and Web and Inbox can read and draft there. They never press Send without your OK, and you always type passwords yourself.</p>
          {!onLaptop && <div className="note">These open on the laptop's screen.</div>}
          <ul className="list">
            {SIGN_IN.map((s) => (
              <li key={s.name}>
                <b>{s.name}</b>
                <span>{new URL(s.url).hostname.replace(/^www\./, "")}{s.note && <><br /><small className="warn-text mark-line"><Icon name="warn" size={14} /> {s.note}</small></>}</span>
                <button className={s.note ? "deny" : ""} onClick={async () => {
                  if (s.note && !window.confirm(`${s.note} Open it anyway?`)) return;
                  setNote(`Opening ${s.name} in the crew's Chrome…`);
                  try { setNote((await api.signIn(s.url)).text); } catch (e) { setNote((e as Error).message); }
                }}>{s.note ? "Open anyway" : "Open sign-in"}</button>
              </li>
            ))}
          </ul>
          {note && <div className="note">{note}</div>}
        </>
      )}
      {page === "allowed" && (
        <>
          {header("Always-allowed actions", "shield")}
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
      {page === "security" && <SecurityPage header={header("Key security", "lock")} />}
      {page === "telegram" && <IntegrationsPage header={header("Telegram & tracing", "plane")} />}
      {page === "operator" && <OperatorPage header={header("Operator safety", "mouse")} bots={bots} />}
      {page === "appearance" && (
        <>
          {header("Appearance & updates", "look")}
          <div className="seg" role="radiogroup" aria-label="Theme">
            {["dark", "light"].map((t) => (
              <button key={t} role="radio" aria-checked={theme === t} className={theme === t ? "on" : ""} onClick={() => setTheme(t)}>
                <Icon name={t === "dark" ? "moon" : "sun"} size={16} /> {t === "dark" ? "Dark" : "Light"}
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
      </section>
    </div>
  );
}

function KeysPage({ header, keys, onSaved, note }: { header: React.ReactNode; keys: KeyInfo[]; onSaved: (text: string) => void; note: string }) {
  const [paste, setPaste] = useState("");
  const [busy, setBusy] = useState(false);
  const missing = keys.filter((k) => k.needs_key && !k.keys.length).map((k) => k.name);
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
      <h3>Your keys</h3>
      {/* one row per key, with works / rejected (jrkrishh's KeysList); it reloads when a paste adds keys */}
      <KeysList version={keys.map((k) => k.keys.join()).join("|")} onChanged={() => onSaved("")} />
      {missing.length > 0 && <p className="quiet">No key yet for {missing.join(", ")}. They're free: paste one above.</p>}
    </>
  );
}

function ModelsPage({ header, models, settings, bots, save, note, setNote, refresh }: {
  header: React.ReactNode; models: ModelInfo[]; settings: Settings; bots: Record<string, Bot>;
  save: (p: Partial<Settings>) => Promise<void>; note: string; setNote: (s: string) => void; refresh: () => void;
}) {
  const [checking, setChecking] = useState(false);
  const usable = choices(models).filter((c) => !c.disabled);
  const option = (c: Choice) => <option key={c.value} value={c.value}>{c.label}{c.value.includes(":") ? "" : " (any free model)"}</option>;
  return (
    <>
      {header}
      <p className="lead">The bots try these in order. All free: when one is busy or out of today's quota, the next one answers.</p>
      <label className="field">Model for the whole crew
        <select value={settings.crew_model ?? ""} onChange={(e) => save({ crew_model: e.target.value || null })}>
          <option value="">Auto: the best free model that answers</option>
          {usable.map(option)}
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
            {usable.map(option)}
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
            <li key={m.provider} className={m.local ? "local-row" : ""}>
              <b>{m.name}</b>
              {m.local ? (
                <span className={m.running && live.length ? "ok" : ""}>
                  {localState(m)}
                  {m.running && m.models.map((x) => (
                    <small key={x.id} className="local-model"><code>{x.id}</code> {x.dead ? "not answering" : canDo(x)}</small>
                  ))}
                </span>
              ) : (
                <span className={m.has_key && live.length ? "ok" : ""}>
                  {!m.has_key ? "No key: add one in API keys" : live.length ? `Ready · ${live.map((x) => x.id).join(", ")}` : "Not answering right now"}
                </span>
              )}
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
    <div className="hub-box hv-hub">
      <div className="switch-row">
        <span>
          <b>Fixed phone link {hub.connected ? <>· on <Icon name="ok" size={15} className="ok-mark" /></> : hub.configured ? "· connecting…" : ""}</b>
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
        <p className="lead">This phone is paired with the laptop. Chats, approvals, routines and every setting work here while the laptop is on. Pairing or removing phones is done on the laptop, in Settings under Your phone.</p>
        <HubBox hub={hub} setHub={setHub} />
        <p className="lead">New version on the laptop? You'll see “A new version is ready · Update” at the top, or use Settings under Appearance & updates.</p>
      </>
    );
  }
  const pair = async () => {
    setNote("Opening a secure link to this laptop…");
    try { setPairing(await api.pairPhone()); setNote(""); } catch (e) { setNote((e as Error).message); }
  };
  return (
    <>
      {header}
      <p className="lead">Use TeamLoop on your phone while this laptop is on. Press Pair, scan the code with the phone camera (or open the link and type the code), then “Add to Home screen”.{hub?.connected ? " The code uses the fixed link." : ""}</p>
      <div className="hv-pair">
        {pairing ? (
          <>
            {/* the QR is an SVG made by our own server */}
            <div className="qr" dangerouslySetInnerHTML={{ __html: pairing.qr }} />
            <div className="hv-pair-text">
              <span className="hv-k">Or type this code</span>
              <b className="hv-code">{pairing.code}</b>
              <span className="hv-meta">Works once, until {new Date(pairing.expires * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}.</span>
              <a className="hv-link" href={pairing.link} target="_blank" rel="noreferrer">{pairing.link.split("/pair")[0]}</a>
              <button className="hv-outline" onClick={pair}>New code</button>
            </div>
          </>
        ) : (
          <div className="hv-pair-text">
            <button className="primary hv-solid" onClick={pair}>Pair a phone</button>
          </div>
        )}
        <img className="hv-wave" src="/mascot/wave.webp" alt="S waving" width={96} height={128} />
      </div>
      {note && <div className="note">{note}</div>}
      <div className="hv-phones">
        <span className="hv-k">Paired phones</span>
        {(phones ?? []).length === 0 && <p className="hv-meta">No phones paired yet.</p>}
        {(phones ?? []).map((p) => (
          <div key={p.id} className="hv-phone">
            <Icon name="phone" size={22} />
            <span><b>{p.name}</b><span className="hv-meta">paired {new Date(p.paired * 1000).toLocaleDateString()} · last seen {new Date(p.last_seen * 1000).toLocaleString()}</span></span>
            <button className="deny hv-remove" onClick={() => window.confirm(`Remove ${p.name}? It will have to pair again.`) && api.removePhone(p.id).then(refresh)}>Remove</button>
          </div>
        ))}
      </div>
      <HubBox hub={hub} setHub={setHub} />
    </>
  );
}
