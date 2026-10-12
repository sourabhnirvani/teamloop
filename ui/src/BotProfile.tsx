import { useEffect, useState } from "react";
import { api, type Bot, type BotLook, type Chat, type Routine } from "./api";
import { Avatar, colorOf, type Move } from "./Avatar";
import { LookPicker, PersonalityPicker, usePersonalities } from "./BotBuilder";
import { Icon } from "./Icon";
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
  const [noteAt, setNoteAt] = useState<"top" | "personality">("top"); // shown next to what was just changed
  const [busy, setBusy] = useState(false);
  const personalities = usePersonalities();
  const loadRoutines = () => api.routines().then(setRoutines).catch(() => {});
  useEffect(() => { loadRoutines(); }, []);
  useEffect(() => { setPersona(bot.persona ?? ""); setEditLook(null); setNote(""); }, [bot.id, bot.persona]);

  const rules = RULES[bot.id];
  const busyIn = Object.entries(typing).filter(([, ids]) => ids.includes(bot.id)).map(([c]) => c);
  const dm = chats.find((c) => c.members.length === 1 && c.members[0] === bot.id);
  const mine = routines.filter((r) => r.chat_id === dm?.id);
  const edited = persona.trim() !== (bot.persona ?? "").trim();
  const act = async (work: () => Promise<unknown>, done: string, at: "top" | "personality" = "top") => {
    setBusy(true);
    setNote("");
    setNoteAt(at);
    try { await work(); setNote(done); } catch (e) { setNote((e as Error).message); } finally { setBusy(false); }
  };
  const shown = editLook ? { ...bot, look: editLook } : bot;

  const colour = bot.id === "s" ? "#18171B" : colorOf(bot); // S's header is its charcoal hoodie, in both themes
  const kind = personalities.find((p) => p.id === bot.personality)?.label ?? (bot.personality ? bot.personality.charAt(0).toUpperCase() + bot.personality.slice(1) : "");
  const sentence = (xs: string[]) => { const t = xs.join(", "); return t.charAt(0).toUpperCase() + t.slice(1); };
  const nextRun = (ts: number) => new Date(ts * 1000).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
  const ownPersona = !bot.custom && !!bot.default_persona && bot.persona !== bot.default_persona;
  const pale = (() => { // a light colour someone picked: the header text goes dark so it stays readable
    const m = /^#([0-9a-f]{6})$/i.exec(colour);
    if (!m) return false;
    const [r, g, b] = [0, 2, 4].map((i) => { const c = parseInt(m[1].slice(i, i + 2), 16) / 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.4;
  })();

  return (
    <Sheet title={bot.name} onClose={onClose} className="profile hd-profile" wide>
      <div style={{ "--bot": colorOf(bot), "--hd-c": colour } as React.CSSProperties}>
        <header className={`hd-pro-head${pale ? " pale" : ""}`}>
          <button className="hd-pro-close" onClick={onClose} aria-label="Close"><Icon name="no" size={20} /></button>
          <span className="hd-pro-tile">
            <Avatar bot={shown} {...(look(bot.id).sign ? look(bot.id) : { move: "idle" as Move, sign: null })} size={124} />
          </span>
          <div className="hd-pro-who">
            <h2>{bot.name}</h2>
            <div className="hd-pro-role">{[bot.role, kind].filter(Boolean).join(" · ")}{bot.custom ? " · built by you" : ""}</div>
            <div className="hd-pro-tags">
              <span className="hd-pro-model">model: {bot.model === "auto" ? "best free model available" : bot.model}{bot.only ? " (only)" : ""}</span>
              <span className="hd-pro-state">{busyIn.length ? `working in ${busyIn.length} chat${busyIn.length > 1 ? "s" : ""}` : "free"}</span>
              {bot.muted && <span className="hd-pro-state"><Icon name="mute" size={13} /> muted</span>}
            </div>
          </div>
        </header>

        <div className="hd-pro-body">
          <div className="hd-pro-actions">
            <button className="hd-btn" onClick={() => setEditLook(editLook ? null : { body: "blob", accessory: "none", eyes: "shiny", colour: colorOf(bot), ...(bot.look ?? {}) })}>
              {editLook ? "Close look" : <><Icon name="look" /> Change look</>}
            </button>
            <button className="hd-btn" disabled={busy} onClick={() => act(() => api.patchBot(bot.id, { muted: !bot.muted }), bot.muted ? "Unmuted." : "Muted: it stays quiet in group rounds, and still works when S hands it a job or you @name it.")}>
              {bot.muted ? <><Icon name="bell" /> Unmute</> : <><Icon name="mute" /> Mute</>}
            </button>
            {dm && <button className="hd-btn dark" onClick={() => onChat(dm.id)}><Icon name="chat" /> Chat with {bot.name}</button>}
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
          {note && noteAt === "top" && <div className="note">{note}</div>}

          <section className="hd-pro-sec">
            <PersonalityPicker value={bot.personality ?? "cheerful"} busy={busy}
              onChange={(p) => p !== bot.personality && act(() => api.patchBot(bot.id, { personality: p }), "New personality: it talks this way from its next message.", "personality")} />
            {!bot.custom && bot.default_personality && bot.personality !== bot.default_personality && (
              <div className="row-btns">
                <button disabled={busy} onClick={() => act(() => api.patchBot(bot.id, { personality: "" }), `Back to ${bot.name}'s own personality.`, "personality")}>Reset personality</button>
              </div>
            )}
            {note && noteAt === "personality" && <div className="note">{note}</div>}
          </section>

          <section className="hd-pro-sec">
            <label className="hd-k" htmlFor={`job-${bot.id}`}>Job & rules</label>
            <textarea id={`job-${bot.id}`} rows={3} value={persona} maxLength={2000} onChange={(e) => setPersona(e.target.value)} aria-label={`${bot.name}'s job and rules`} />
            {(edited || ownPersona) && (
              <div className="row-btns">
                {ownPersona && <button disabled={busy} onClick={() => act(() => api.patchBot(bot.id, { persona: "" }), "Back to its own job & rules.")}>Reset</button>}
                <button className="primary" disabled={!edited || busy || !persona.trim()} onClick={() => act(() => api.patchBot(bot.id, { persona }), "Saved: it works this way from its next message.")}>Save</button>
              </div>
            )}
            {rules && (
              <div className="hd-rules">
                <div className="hd-rule alone"><b><Icon name="ok" size={16} /> On its own</b>{sentence(rules.alone)}</div>
                <div className="hd-rule asks"><b><Icon name="ask" size={16} /> Asks you first</b>{rules.asks.length ? sentence(rules.asks) : "Nothing it does needs your OK"}</div>
                <div className="hd-rule never"><b><Icon name="no" size={16} /> Never</b>{sentence(rules.never)}</div>
              </div>
            )}
          </section>

          <section className="hd-pro-sec">
            <div className="hd-k">Tools</div>
            <div className="hd-tools">{(bot.tools ?? []).map((t) => <code key={t}>{t}</code>)}</div>
          </section>

          <section className="hd-pro-sec">
            <div className="hd-k">Routines</div>
            {mine.length === 0 && <p className="quiet">None yet.</p>}
            {mine.map((r) => (
              <div key={r.id} className="hd-routine">
                <Icon name="routine" size={22} />
                <span><b>{r.schedule}</b><small>{r.text}{r.next_run ? ` · next ${nextRun(r.next_run)}` : ""}</small></span>
                <button onClick={() => api.cancelRoutine(r.id).then(loadRoutines)}>Cancel</button>
              </div>
            ))}
            {dm && (
              <form className="hd-routine-add" onSubmit={(e) => {
                e.preventDefault();
                act(() => api.addRoutine(dm.id, task.trim(), when.trim()).then(() => { setTask(""); setWhen(""); return loadRoutines(); }), "Routine added.");
              }}>
                <input value={task} onChange={(e) => setTask(e.target.value)} placeholder="What to do, e.g. check AI news" aria-label="Routine task" />
                <input value={when} onChange={(e) => setWhen(e.target.value)} placeholder="every day at 9am" aria-label="When" />
                <button className="hd-btn" disabled={!task.trim() || !when.trim() || busy}><Icon name="add" /> Add routine</button>
              </form>
            )}
          </section>

          <section className="hd-pro-foot">
            <div className="hd-pro-crew" role="group" aria-label="Other bots">
              <span className="hd-meta">Works with</span>
              {Object.values(bots).filter((b) => b.id !== bot.id).map((b) => (
                <button key={b.id} title={b.name} aria-label={`${b.name} profile`} onClick={() => onBot(b.id)}>
                  <Avatar bot={b} size={34} />
                </button>
              ))}
            </div>
            {bot.custom && (
              <button className="hd-remove" disabled={busy} onClick={() => window.confirm(`Remove ${bot.name}? Its chat goes too.`) &&
                act(() => api.deleteBot(bot.id).then(onRemoved), "Removed.")}>Remove {bot.name}</button>
            )}
          </section>
        </div>
      </div>
    </Sheet>
  );
}
