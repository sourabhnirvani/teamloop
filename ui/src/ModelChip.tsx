import { useEffect, useRef, useState } from "react";
import { api, type Bot, type ModelInfo, type Settings } from "./api";
import { choices, labelOf } from "./models";

// ⚡ in a chat's header: which free model answers there. In a 1:1 chat it's that bot's model; in a group,
// the crew's. "Only this model" turns off falling back to the next free model when it's busy.
export function ModelChip({ bot }: { bot?: Bot }) {
  const [open, setOpen] = useState(false);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [error, setError] = useState("");
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => { // the closed chip names the model too: in a group chat that's the crew's setting
    api.models().then(setModels).catch(() => {});
    api.settings().then(setSettings).catch(() => {});
  }, []);

  useEffect(() => {
    if (!open) return;
    api.models().then(setModels).catch(() => {});
    api.settings().then(setSettings).catch(() => {});
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !box.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", close);
    window.addEventListener("keydown", close);
    return () => { window.removeEventListener("mousedown", close); window.removeEventListener("keydown", close); };
  }, [open]);

  const current = bot ? settings?.bot_models[bot.id] ?? null : settings?.crew_model ?? null;
  const only = bot ? !!settings?.bot_only?.[bot.id] : false;
  const nameOf = (id: string | null | undefined) => labelOf(models, id);
  const shown = bot ? nameOf(bot.model) : nameOf(settings?.crew_model);

  async function pick(provider: string | null) {
    if (!settings) return;
    setError("");
    try {
      if (bot) {
        const next = { ...settings.bot_models };
        if (provider) next[bot.id] = provider;
        else delete next[bot.id];
        setSettings(await api.setSettings({ bot_models: next }));
      } else {
        setSettings(await api.setSettings({ crew_model: provider }));
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function setOnly(on: boolean) {
    if (!settings || !bot) return;
    try {
      setSettings(await api.setSettings({ bot_only: { ...(settings.bot_only ?? {}), [bot.id]: on } }));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="chip-wrap" ref={box}>
      <button className="model-chip" aria-haspopup="menu" aria-expanded={open} title="Which free model answers here"
              onClick={() => setOpen(!open)}>
        ⚡ {open && settings ? nameOf(current) : shown}{bot?.only ? " · only" : ""}
      </button>
      {open && (
        <div className="menu" role="menu" aria-label={bot ? `Model for ${bot.name}` : "Model for the crew"}>
          <div className="menu-title">{bot ? `Model for ${bot.name}` : "Model for the whole crew"}</div>
          <button role="menuitemradio" aria-checked={!current} className={!current ? "on" : ""} onClick={() => pick(null)}>
            <b>Auto</b><small>the best free model that answers</small>
          </button>
          {choices(models).map((c) => (
            <button key={c.value} role="menuitemradio" aria-checked={current === c.value} disabled={c.disabled}
                    className={current === c.value ? "on" : ""} onClick={() => pick(c.value)}>
              <b>{c.label}</b><small className={c.ok ? "ok" : ""}>{c.note}</small>
            </button>
          ))}
          {bot && (
            <label className="menu-check">
              <input type="checkbox" checked={only} disabled={!current} onChange={(e) => setOnly(e.target.checked)} />
              Only this model (no fallback)
            </label>
          )}
          {error && <div className="error">{error}</div>}
        </div>
      )}
    </div>
  );
}
