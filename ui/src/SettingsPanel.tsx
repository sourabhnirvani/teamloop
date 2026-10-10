import { useEffect, useState } from "react";
import { api, type Bot, type KeyInfo, type ModelInfo, type Pairing, type Phone, type Routine, type Settings, type Usage } from "./api";

type Section = "keys" | "models" | "usage" | "routines" | "phone";

export function SettingsPanel({ bots, onClose }: { bots: Record<string, Bot>; onClose: () => void }) {
  const [section, setSection] = useState<Section>("keys");
  const [keys, setKeys] = useState<KeyInfo[]>([]);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [usage, setUsage] = useState<Usage[]>([]);
  const [routines, setRoutines] = useState<Routine[]>([]);
  const [phones, setPhones] = useState<Phone[]>([]);
  const [pairing, setPairing] = useState<Pairing | null>(null);
  const [paste, setPaste] = useState("");
  const [note, setNote] = useState("");
  const [checking, setChecking] = useState(false);

  const refresh = () => {
    api.keys().then(setKeys).catch(() => {});
    api.models().then(setModels).catch(() => {});
    api.settings().then(setSettings).catch(() => {});
    api.usage().then(setUsage).catch(() => {});
    api.routines().then(setRoutines).catch(() => {});
    api.phones().then(setPhones).catch(() => {});
  };
  useEffect(refresh, []);
  useEffect(() => {
    if (!pairing) return;
    const t = window.setInterval(() => api.phones().then(setPhones).catch(() => {}), 3000); // show the phone as soon as it pairs
    return () => window.clearInterval(t);
  }, [pairing]);

  async function saveKeys() {
    try {
      const out = await api.addKeys(paste);
      setNote(out.map((o) => o.text).join(" "));
      setPaste("");
      refresh();
    } catch (e) {
      setNote(String((e as Error).message));
    }
  }

  async function check() {
    setChecking(true);
    setNote("Asking every model a tiny question…");
    try {
      setNote((await api.checkModels()).summary);
      refresh();
    } finally {
      setChecking(false);
    }
  }

  async function pair() {
    setNote("Opening a secure link to this laptop…");
    try {
      setPairing(await api.pairPhone());
      setNote("");
    } catch (e) {
      setNote(String((e as Error).message));
    }
  }

  async function update(patch: Partial<Settings>) {
    setSettings(await api.setSettings(patch));
  }

  const totals = usage.reduce((a, u) => ({ req: a.req + u.requests, tok: a.tok + u.tokens_in + u.tokens_out }), { req: 0, tok: 0 });

  return (
    <div className="overlay" onClick={onClose}>
      <aside className="settings" onClick={(e) => e.stopPropagation()}>
        <header>
          <b>Settings</b>
          <button className="icon" onClick={onClose} aria-label="Close">✕</button>
        </header>
        <nav>
          {(["keys", "models", "usage", "routines", "phone"] as Section[]).map((s) => (
            <button key={s} className={section === s ? "on" : ""} onClick={() => setSection(s)}>
              {{ keys: "API keys", models: "Models", usage: "Usage today", routines: "Routines", phone: "Phone" }[s]}
            </button>
          ))}
        </nav>
        {note && <div className="note">{note}</div>}

        {section === "keys" && (
          <div className="pane">
            <p>Paste free keys (Gemini, Groq, OpenRouter, NVIDIA…) or "neatlogs key: …". They're checked, then locked in the key vault.</p>
            <textarea value={paste} onChange={(e) => setPaste(e.target.value)} rows={3} placeholder="Paste keys here" />
            <button className="primary" disabled={!paste.trim()} onClick={saveKeys}>Save keys</button>
            <ul className="list">
              {keys.map((k) => (
                <li key={k.id}>
                  <b>{k.name}</b>
                  <span>{k.needs_key ? (k.keys.length ? k.keys.join(", ") : "no key") : "runs locally"}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {section === "models" && settings && (
          <div className="pane">
            <label className="toggle">
              <input type="checkbox" checked={settings.save_tokens} onChange={(e) => update({ save_tokens: e.target.checked })} />
              Save tokens mode (shorter history, fewer steps)
            </label>
            <label>
              Crew model
              <select value={settings.crew_model ?? ""} onChange={(e) => update({ crew_model: e.target.value || null })}>
                <option value="">Automatic (best free model that answers)</option>
                {models.filter((m) => m.has_key).map((m) => <option key={m.provider} value={m.provider}>{m.name}</option>)}
              </select>
            </label>
            {Object.values(bots).map((b) => (
              <label key={b.id} className="inline">
                {b.emoji} {b.name}
                <select
                  value={settings.bot_models[b.id] ?? ""}
                  onChange={(e) => {
                    const next = { ...settings.bot_models };
                    if (e.target.value) next[b.id] = e.target.value;
                    else delete next[b.id];
                    update({ bot_models: next });
                  }}
                >
                  <option value="">same as crew</option>
                  {models.filter((m) => m.has_key).map((m) => <option key={m.provider} value={m.provider}>{m.name}</option>)}
                </select>
              </label>
            ))}
            <button className="primary" disabled={checking} onClick={check}>{checking ? "Checking…" : "Check which models work"}</button>
            <ul className="list">
              {models.map((m) => (
                <li key={m.provider}>
                  <b>{m.name}</b>
                  <span>
                    {m.has_key
                      ? m.models.map((x, i) => <span key={x.id}>{i ? ", " : ""}{x.dead ? <s>{x.id}</s> : x.id}</span>)
                      : "add a key"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {section === "usage" && (
          <div className="pane">
            <p><b>{totals.req}</b> requests · <b>{totals.tok.toLocaleString()}</b> tokens today</p>
            <ul className="list">
              {usage.map((u) => (
                <li key={u.provider + u.model}>
                  <b>{u.provider}</b>
                  <span>{u.model}: {u.requests} req, {(u.tokens_in + u.tokens_out).toLocaleString()} tok</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {section === "routines" && (
          <div className="pane">
            <p>Ask S things like "every monday at 9am, give me a weekly summary".</p>
            <ul className="list">
              {routines.length === 0 && <li><span>No routines yet.</span></li>}
              {routines.map((r) => (
                <li key={r.id}>
                  <b>{r.schedule}</b>
                  <span>{r.text} · next {new Date(r.next_run * 1000).toLocaleString()}</span>
                  <button onClick={() => api.cancelRoutine(r.id).then(refresh)}>Cancel</button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {section === "phone" && (
          <div className="pane">
            <p>Use TeamLoop from your phone while this laptop is on. Scan the code with the phone camera, or open the link and type the code. Then "Add to Home screen".</p>
            <button className="primary" onClick={pair}>{pairing ? "New code" : "Pair a phone"}</button>
            {pairing && (
              <div className="pairing">
                {/* the QR is an SVG made by our own server */}
                <div className="qr" dangerouslySetInnerHTML={{ __html: pairing.qr }} />
                <p><b className="code">{pairing.code}</b><br />Works once, for 10 minutes.<br /><a href={pairing.link}>{pairing.link.split("/pair")[0]}</a></p>
              </div>
            )}
            <ul className="list">
              {phones.length === 0 && <li><span>No phones paired.</span></li>}
              {phones.map((p) => (
                <li key={p.id}>
                  <b>{p.name}</b>
                  <span>paired {new Date(p.paired * 1000).toLocaleDateString()} · last seen {new Date(p.last_seen * 1000).toLocaleString()}</span>
                  <button onClick={() => api.removePhone(p.id).then(refresh)}>Remove</button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </aside>
    </div>
  );
}
