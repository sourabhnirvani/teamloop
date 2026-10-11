import { useEffect, useState } from "react";
import { api, type Bot, type BotLook, type Personality } from "./api";
import { Mascot } from "./Avatar";
import { ACCESSORIES, BODIES, EYES, PALETTE, randomLook } from "./Look";
import { Sheet } from "./Sheet";

// Pick a body, an accessory, eyes and a colour; the preview updates as you go.
export function LookPicker({ look, onChange }: { look: BotLook; onChange: (l: BotLook) => void }) {
  const row = (title: string, items: { id: string; label: string }[], key: keyof BotLook) => (
    <div className="pick-row">
      <h4>{title}</h4>
      <div className="pick-grid" role="radiogroup" aria-label={title}>
        {items.map((it) => (
          <button key={it.id} role="radio" aria-checked={look[key] === it.id} title={it.label} aria-label={it.label}
                  className={look[key] === it.id ? "on" : ""} onClick={() => onChange({ ...look, [key]: it.id })}>
            <Mascot id="pick" size={40} look={{ ...look, [key]: it.id }} />
          </button>
        ))}
      </div>
    </div>
  );
  return (
    <div className="look-picker">
      {row("Body", BODIES, "body")}
      {row("Accessory", ACCESSORIES, "accessory")}
      {row("Eyes", EYES, "eyes")}
      <div className="pick-row">
        <h4>Colour</h4>
        <div className="swatches" role="radiogroup" aria-label="Colour">
          {PALETTE.map((c) => (
            <button key={c} role="radio" aria-checked={look.colour === c} aria-label={c === "rainbow" ? "Rainbow" : c}
                    className={`swatch ${look.colour === c ? "on" : ""}`}
                    style={{ background: c === "rainbow" ? "linear-gradient(135deg,#ff8fb3,#ffd45c,#8af5d6,#7bb8ff,#c9a8ff)" : c }}
                    onClick={() => onChange({ ...look, colour: c })} />
          ))}
        </div>
      </div>
    </div>
  );
}

let personalities: Personality[] | null = null; // the same twelve for the whole session: fetched once

export function usePersonalities(): Personality[] {
  const [list, setList] = useState<Personality[]>(personalities ?? []);
  useEffect(() => {
    if (personalities) return;
    api.personalities().then((l) => { personalities = l; setList(l); }).catch(() => {});
  }, []);
  return list;
}

// How the bot talks and moves: one tap picks it, and the line under the chips says what it means.
export function PersonalityPicker({ value, onChange, busy }: { value: string; onChange: (id: string) => void; busy?: boolean }) {
  const list = usePersonalities();
  const now = list.find((p) => p.id === value);
  return (
    <div className="pick-row">
      <h4>Personality</h4>
      <div className="pers-grid" role="radiogroup" aria-label="Personality">
        {list.map((p) => (
          <button key={p.id} role="radio" aria-checked={p.id === value} className={p.id === value ? "on" : ""} disabled={busy}
                  title={p.blurb} onClick={() => onChange(p.id)}>
            <span aria-hidden="true">{p.emoji}</span> {p.label}
          </button>
        ))}
      </div>
      {now && <small className="pers-blurb">{now.emoji} {now.label}: {now.blurb.toLowerCase()}. It talks this way, and moves this way here.</small>}
    </div>
  );
}

export function NewBotSheet({ onClose, onMade }: { onClose: () => void; onMade: (bot: Bot) => void }) {
  const [look, setLook] = useState<BotLook>(() => randomLook());
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [persona, setPersona] = useState("");
  const [personality, setPersonality] = useState("cheerful");
  const kinds = usePersonalities();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [bounce, setBounce] = useState(0);

  const change = (l: BotLook) => { setLook(l); setBounce((b) => b + 1); };

  return (
    <Sheet title="Build a bot" onClose={onClose} wide>
      <div className="builder">
        <div className="builder-preview">
          <Mascot key={bounce} id="preview" size={150} move={bounce ? "cheer" : "idle"} look={look} personality={personality} />
          <b>{name || "Your bot"}</b>
          <small>{role || "its job"}</small>
          <button onClick={() => {
            change(randomLook());
            if (kinds.length) setPersonality(kinds[Math.floor(Math.random() * kinds.length)].id);
          }}>🎲 Surprise me</button>
        </div>
        <div className="builder-form">
          <LookPicker look={look} onChange={change} />
          <PersonalityPicker value={personality} onChange={(p) => { setPersonality(p); setBounce(0); }} />
          <div className="two">
            <label className="field">Name<input value={name} maxLength={24} onChange={(e) => setName(e.target.value)} placeholder="e.g. Blog Pulse" /></label>
            <label className="field">Role<input value={role} maxLength={40} onChange={(e) => setRole(e.target.value)} placeholder="e.g. Content" /></label>
          </div>
          <label className="field">Job & rules
            <textarea rows={4} value={persona} maxLength={2000} onChange={(e) => setPersona(e.target.value)}
                      placeholder="What it owns, how it works, and its limits (e.g. “drafts only, never posts”)." />
          </label>
          <p className="quiet">It starts with web search, reading your files (not changing them) and memory. It gets its own chat, joins the Team, and S can hand it work. Change anything later in its profile.</p>
          {error && <div className="error">{error}</div>}
          <div className="dialog-btns">
            <button onClick={onClose}>Cancel</button>
            <button className="primary" disabled={!name.trim() || busy} onClick={async () => {
              setBusy(true);
              setError("");
              try {
                onMade(await api.createBot({ name: name.trim(), role: role.trim(), persona: persona.trim(), look, personality }));
              } catch (e) {
                setError((e as Error).message);
                setBusy(false);
              }
            }}>{busy ? "Creating…" : "Create bot"}</button>
          </div>
        </div>
      </div>
    </Sheet>
  );
}
