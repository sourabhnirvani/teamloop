// The TeamLoop server API (PLAN.md section 4).

export type Bot = { id: string; name: string; role: string; emoji: string; model: string };
export type Chat = { id: string; title: string; members: string[]; created: number };
export type Message = { id: number; chat_id: string; sender: string; text: string; kind: string; ts: number };
export type KeyInfo = { id: string; name: string; needs_key: boolean; keys: string[] };
export type ModelInfo = { provider: string; name: string; has_key: boolean; models: { id: string; dead: boolean }[] };
export type Settings = { save_tokens: boolean; crew_model: string | null; bot_models: Record<string, string> };
export type Usage = { day: string; provider: string; model: string; requests: number; tokens_in: number; tokens_out: number };
export type Routine = { id: string; chat_id: string; text: string; schedule: string; next_run: number };

export type ServerEvent =
  | { type: "message"; chat_id: string; message: Message }
  | { type: "typing"; chat_id: string; bot: string; on: boolean }
  | { type: "step"; chat_id: string; bot: string; tool: string; status: "start" | "done" | "fail"; text?: string; args?: unknown }
  | { type: "approval"; chat_id: string; id: string; bot: string; title: string; details: string; screenshot?: string | null }
  | { type: "approval_done"; chat_id: string; id: string; status: string }
  | { type: "screenshot"; chat_id: string; bot: string; url: string }
  | { type: "error"; chat_id: string; text: string };

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* not JSON */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

const post = <T,>(path: string, body?: unknown) =>
  call<T>(path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body ?? {}) });

export const api = {
  bots: () => call<Bot[]>("/api/bots"),
  chats: () => call<Chat[]>("/api/chats"),
  newChat: (title: string, members: string[]) => post<Chat>("/api/chats", { title, members }),
  messages: (chatId: string) => call<Message[]>(`/api/chats/${chatId}/messages`),
  send: (chatId: string, text: string) => post<Message>(`/api/chats/${chatId}/messages`, { text }),
  stop: (chatId: string) => post<{ stopped: boolean }>(`/api/chats/${chatId}/stop`),
  answer: (approvalId: string, ok: boolean) => post<{ ok: boolean }>(`/api/approvals/${approvalId}`, { ok }),
  keys: () => call<KeyInfo[]>("/api/keys"),
  addKeys: (text: string) => post<{ provider: string; status: string; text: string }[]>("/api/keys", { text }),
  models: () => call<ModelInfo[]>("/api/models"),
  checkModels: () => post<{ summary: string }>("/api/models/check"),
  settings: () => call<Settings>("/api/settings"),
  setSettings: (patch: Partial<Settings>) => post<Settings>("/api/settings", patch),
  usage: () => call<Usage[]>("/api/usage"),
  routines: () => call<Routine[]>("/api/routines"),
  cancelRoutine: (id: string) => call<{ ok: boolean }>(`/api/routines/${id}`, { method: "DELETE" }),
};

export function listen(onEvent: (e: ServerEvent) => void, onState: (live: boolean) => void): () => void {
  let source: EventSource | null = null;
  let closed = false;
  let retry: number | undefined;
  const open = () => {
    source = new EventSource("/api/events");
    source.onopen = () => onState(true);
    source.onmessage = (msg) => onEvent(JSON.parse(msg.data) as ServerEvent);
    source.onerror = () => {
      onState(false);
      source?.close();
      if (!closed) retry = window.setTimeout(open, 2000);
    };
  };
  open();
  return () => {
    closed = true;
    window.clearTimeout(retry);
    source?.close();
  };
}
