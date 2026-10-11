import type { ModelInfo } from "./api";

// What the crew / a bot can be set to: "gemini" (any Gemini model, the free one that answers) or
// "ollama:qwen2.5:7b" (one model on this laptop). Cloud services are picked as a whole; local models one by one,
// since each installed model is different.
export type Choice = { value: string; label: string; note: string; ok: boolean; disabled: boolean };
type LocalModel = ModelInfo["models"][number];

export function labelOf(models: ModelInfo[], value: string | null | undefined): string {
  if (!value || value === "auto") return "Auto";
  const [provider, ...rest] = value.split(":");
  const model = rest.join(":");
  const p = models.find((m) => m.provider === provider);
  if (p?.local) return model ? `Local · ${model}` : "Local (any model)";
  return (p?.name ?? provider) + (model ? ` · ${model}` : "");
}

export function canDo(m: LocalModel): string {
  return [
    m.tools === false ? "tools written into its prompt" : "uses tools",
    m.thinking ? "thinks first" : "",
    m.ctx ? `${Math.round(m.ctx / 1024)}k context` : "",
  ].filter(Boolean).join(" · ");
}

export function localState(p: ModelInfo): string {
  if (p.running === false) return "Ollama isn't running: start it (free from ollama.com), then check again";
  if (!p.models.length) return "Ollama is running but has no models yet: run “ollama pull qwen2.5:7b”";
  return `${p.models.length} model${p.models.length > 1 ? "s" : ""} on this laptop`;
}

export function choices(models: ModelInfo[]): Choice[] {
  const out: Choice[] = [];
  for (const p of models) {
    if (p.local) {
      if (p.running === false || !p.models.length) {
        out.push({ value: p.provider, label: p.name, note: localState(p), ok: false, disabled: true });
        continue;
      }
      for (const m of p.models) {
        out.push({ value: `${p.provider}:${m.id}`, label: `Local · ${m.id}`, ok: !m.dead,
                   note: m.dead ? "not answering" : `on this laptop · ${canDo(m)}`, disabled: !!m.dead });
      }
      continue;
    }
    const live = p.models.filter((x) => !x.dead);
    out.push({ value: p.provider, label: p.name, ok: p.has_key && live.length > 0, disabled: !p.has_key,
               note: !p.has_key ? "no key: add one in Settings → API keys" : live.length ? "ready" : "not answering" });
  }
  return out;
}
