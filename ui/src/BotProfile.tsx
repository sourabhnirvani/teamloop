import { useEffect, useState } from "react";
import { api, type Bot, type BotLook, type Chat, type Routine } from "./api";
import { Avatar, colorOf, type Move } from "./Avatar";
import { LookPicker } from "./BotBuilder";
import { Sheet } from "./Sheet";

export const RULES: Record<string, { alone: string[]; asks: string[]; never: string[] }> = {
  s: { alone: ["plan jobs and hand steps to teammates", "remember things you tell it", "set routines"],
    asks: ["anything risky goes through the teammate's card"], never: ["approve its own cards"] },
  desk: { alone: ["open apps and files you name", "volume, brightness, Wi-Fi on", "read the screen", "run safe commands"],
    asks: ["close apps", "delete, kill processes, registry, services", "lock, sleep, restart, Wi-Fi off", "open a file"],
    never: ["Windows-key shortcuts or Enter in a terminal", "type passwords, card numbers or codes", "touch TeamLoop's own window"] },
  web: { alone: ["open and read pages", "click links, type in search boxes"],
    asks: ["send, post, buy, submit a form", "checkout pages, local-network pages"],
    never: ["type passwords or card numbers", "upload files, download files"] },
  scout: { alone: ["search the web", "read pages and summarise with links"], asks: [], never: ["act as you anywhere"] },
  inbox: { alone: ["read, sort and summarise email", "draft replies"], asks: ["send anything"], never: ["type passwords"] },
  writer: { alone: ["write new files on Desktop, Documents, Downloads", "notes, reports, messages"],
    asks: ["replace an existing file"], never: ["write outside those folders"] },
};

export function BotProfile({ bot, bots, chats, typing, look, onChat, onBot, onClose, onRemoved }: {
  bot: Bot; bots: Record<string, Bot>; chats: Chat[]; typing: Record<string, string[]>;
  look: (id: string) => { move: Move; sign: string | null };
  onChat: (chatId: string) => void; onBot: (botId: string) => void; onClose: () => void; onRemoved: () => void;
}) {
  const [routines, setRoutines] = useState<Routine[]>([]);
  const [persona, setPersona] = useState(bot.persona ?? "");
  const [editLook, setEditLook] = useState<BotLook | null>(null);
  const [task, setTask] = useState("");
  const [when, setWhen] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const loadRoutines = () => api.routines().then(setRoutines).catch(() => {});
  useEffect(() => { loadRoutines(); }, []);
  useEffect(() => { setPersona(bot.persona ?? ""); setEditLook(null); setNote(""); }, [bot.id, bot.persona]);

  const rules = RULES[bot.id];
  const busyIn = Object.entries(typing).filter(([, ids]) => ids.includes(bot.id)).map(([c]) => c);
  const dm = chats.find((c) => c.members.length === 1 && c.members[0] === bot.id);
  const mine = routines.filter((r) => r.chat_id === dm?.id);
  const edited = persona.trim() !== (bot.persona ?? "").trim();
  const act = async (work: () => Promise<unknown>, done: string) => {
    setBusy(true);
    setNote("");
    try { await work(); setNote(done); } catch (e) { setNote((e as Error).message); } finally { setBusy(false); }
  };
  const shown = editLook ? { ...bot, look: editLook } : bot;

  return (
    <Sheet title={bot.name} onClose={onClose} className="profile" wide={!!editLook}>
      <div style={{ "--bot": colorOf(bot) } as React.CSSProperties}>
        <div className="profile-hero">
          <Avatar bot={shown} {...(look(bot.id).sign ? look(bot.id) : { move: "cheer" as Move, sign: null })} size={120} />
          <div>
            <h2>{bot.name}</h2>
            <div className="role">{bot.role}{bot.custom ? " · built by you" : ""}</div>
            <div className="model">model: {bot.model === "auto" ? "best free model available" : bot.model}{bot.only ? " (only)" : ""}</div>
            <div className="hero-tags">
              <span className={`state ${busyIn.length ? "busy" : ""}`}>{busyIn.length ? `working in ${busyIn.length} chat${busyIn.length > 1 ? "s" : ""}` : "free"}</span>
              {bot.muted && <span className="state muted">🔕 muted</span>}
            </div>
          </div>
        </div>

        <div className="profile-actions">
          <button onClick={() => setEditLook(editLook ? null : { body: "blob", accessory: "none", eyes: "shiny", colour: colorOf(bot), ...(bot.look ?? {}) })}>
            {editLook ? "Close look" : "🎨 Change look"}
          </button>
          <button disabled={busy} onClick={() => act(() => api.patchBot(bot.id, { muted: !bot.muted }), bot.muted ? "Unmuted." : "Muted: it stays quiet in group rounds, and still works when S hands it a job or you @name it.")}>
            {bot.muted ? "🔔 Unmute" : "🔕 Mute"}
          </button>
          {dm && <button className="primary" onClick={() => onChat(dm.id)}>Chat with {bot.name}</button>}
        </div>
        {editLook && (
          <div className="profile-look">
            <LookPicker look={editLook} onChange={setEditLook} />
            <div className="dialog-btns">
              <button onClick={() => setEditLook(null)}>Cancel</button>
              <button className="primary" disabled={busy} onClick={() => act(() => api.patchBot(bot.id, { look: editLook }).then(() => setEditLook(null)), "New look saved.")}>Save look</button>
            </div>
          </div>
        )}
        {note && <div className="note">{note}</div>}

        <section className="profile-sec">
          <h4>Job & rules</h4>
          <textarea rows={4} value={persona} maxLength={2000} onChange={(e) => setPersona(e.target.value)} aria-label={`${bot.name}'s job and rules`} />
          <div className="row-btns">
            {!bot.custom && bot.default_persona && bot.persona !== bot.default_persona && (
              <button disabled={busy} onClick={() => act(() => api.patchBot(bot.id, { persona: "" }), "Back to its own job & rules.")}>Reset</button>
            )}
            <button className="primary" disabled={!edited || busy || !persona.trim()} onClick={() => act(() => api.patchBot(bot.id, { persona }), "Saved: it works this way from its next message.")}>Save</button>
          </div>
        </section>

        {rules && (
          <div className="rules">
            <div><h4>On its own</h4><ul>{rules.alone.map((r) => <li key={r}>{r}</li>)}</ul></div>
            <div><h4>Asks you first</h4><ul>{rules.asks.length ? rules.asks.map((r) => <li key={r}>{r}</li>) : <li className="quiet">nothing it does needs your OK</li>}</ul></div>
            <div><h4>Never</h4><ul>{rules.never.map((r) => <li key={r}>{r}</li>)}</ul></div>
          </div>
        )}

        <section className="profile-sec">
          <h4>Tools</h4>
          <div className="chips">{(bot.tools ?? []).map((t) => <code key={t} className="chip">{t}</code>)}</div>
        </section>

        <section className="profile-sec">
          <h4>Routines</h4>
          {mine.length === 0 && <p className="quiet">None yet.</p>}
          {mine.map((r) => (
            <div key={r.id} className="routine-row">
              <span>⏰ {r.text} <small>({r.schedule})</small></span>
              <button onClick={() => api.cancelRoutine(r.id).then(loadRoutines)}>Cancel</button>
            </div>
          ))}
          {dm && (
            <form className="routine-add" onSubmit={(e) => {
              e.preventDefault();
              act(() => api.addRoutine(dm.id, task.trim(), when.trim()).then(() => { setTask(""); setWhen(""); return loadRoutines(); }), "Routine added.");
            }}>
              <input value={task} onChange={(e) => setTask(e.target.value)} placeholder="What to do, e.g. check AI news" aria-label="Routine task" />
              <input value={when} onChange={(e) => setWhen(e.target.value)} placeholder="every day at 9am" aria-label="When" />
              <button className="primary" disabled={!task.trim() || !when.trim() || busy}>Add routine</button>
            </form>
          )}
        </section>

        <div className="profile-crew" role="group" aria-label="Other bots">
          {Object.values(bots).map((b) => (
            <button key={b.id} className={b.id === bot.id ? "on" : ""} title={b.name} aria-label={`${b.name} profile`} onClick={() => onBot(b.id)}>
              <Avatar bot={b} size={34} />
            </button>
          ))}
        </div>
        {bot.custom && (
          <button className="deny wide" disabled={busy} onClick={() => window.confirm(`Remove ${bot.name}? Its chat goes too.`) &&
            act(() => api.deleteBot(bot.id).then(onRemoved), "Removed.")}>Remove {bot.name}</button>
        )}
      </div>
    </Sheet>
  );
}
