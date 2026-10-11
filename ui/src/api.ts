// The TeamLoop server API (PLAN.md section 4).

export type Bot = { id: string; name: string; role: string; emoji: string; model: string };
export type LastMessage = { sender: string; text: string; kind: string; ts: number };
export type Chat = { id: string; title: string; members: string[]; created: number; last?: LastMessage | null };
export type Message = { id: number; chat_id: string; sender: string; text: string; kind: string; ts: number };
export type KeyInfo = { id: string; name: string; needs_key: boolean; keys: string[] };
export type ModelInfo = { provider: string; name: string; has_key: boolean; models: { id: string; dead: boolean; ok?: boolean | null }[] };
export type Settings = { save_tokens: boolean; crew_model: string | null; bot_models: Record<string, string> };
export type Usage = { day: string; provider: string; model: string; requests: number; tokens_in: number; tokens_out: number };
export type Routine = { id: string; chat_id: string; text: string; schedule: string; next_run: number };
export type Phone = { id: string; name: string; paired: number; last_seen: number };
export type Pairing = { code: string; link: string; expires: number; qr: string };
export type ApprovalEvent = { type: "approval"; chat_id: string; id: string; bot: string; title: string; details: string; screenshot?: string | null };
export type CrewState = { typing: Record<string, string[]>; approvals: ApprovalEvent[]; asleep: boolean; save_tokens: boolean };

export type ServerEvent =
  | { type: "message"; chat_id: string; message: Message }
  | { type: "typing"; chat_id: string; bot: string; on: boolean }
  | { type: "step"; chat_id: string; bot: string; tool: string; status: "start" | "done" | "fail"; text?: string; args?: unknown }
  | ApprovalEvent
  | { type: "approval_done"; chat_id: string; id: string; status: string }
  | { type: "screenshot"; chat_id: string; bot: string; url: string }
  | { type: "settings"; chat_id: null } & Settings
  | { type: "usage"; chat_id: null; provider: string; model: string; tokens_in: number; tokens_out: number };

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (res.status === 401) window.location.assign("/pair"); // a phone that isn't paired (or was removed)
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
  state: () => call<CrewState>("/api/state"),
  keys: () => call<KeyInfo[]>("/api/keys"),
  addKeys: (text: string) => post<{ provider: string; status: string; text: string }[]>("/api/keys", { text }),
  models: () => call<ModelInfo[]>("/api/models"),
  checkModels: () => post<{ summary: string }>("/api/models/check"),
  settings: () => call<Settings>("/api/settings"),
  setSettings: (patch: Partial<Settings>) => post<Settings>("/api/settings", patch),
  usage: () => call<Usage[]>("/api/usage"),
  routines: () => call<Routine[]>("/api/routines"),
  cancelRoutine: (id: string) => call<{ ok: boolean }>(`/api/routines/${id}`, { method: "DELETE" }),
  phones: () => call<Phone[]>("/api/phones"),
  pairPhone: () => post<Pairing>("/api/phones/pair"),
  removePhone: (id: string) => call<{ ok: boolean }>(`/api/phones/${id}`, { method: "DELETE" }),
  signIn: (url: string) => post<{ ok: boolean; url: string; text: string }>("/api/browser/signin", { url }),
};

// On the laptop itself the app talks to the server directly; anywhere else it's a paired phone.
export const onLaptop = ["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname);

type Listeners = {
  onEvent: (e: ServerEvent) => void;
  onLive: (live: boolean) => void;
  onResync: () => void; // (re)connected or events were dropped: reload chats, the open chat and /api/state
};

// Phones come in over a Cloudflare tunnel, which doesn't carry SSE, so they long-poll instead.
function poll({ onEvent, onLive, onResync }: Listeners): () => void {
  let closed = false;
  const stop = new AbortController();
  (async () => {
    let after = -1;
    while (!closed) {
      try {
        const res = await fetch(`/api/events/poll?after=${after}`, { signal: stop.signal });
        if (res.status === 401) return window.location.assign("/pair");
        if (!res.ok) throw new Error(res.statusText);
        const data = (await res.json()) as { seq: number; oldest?: number; events: ServerEvent[] };
        onLive(true);
        const gap = after < 0 || data.seq < after || (data.oldest !== undefined && data.oldest > after + 1 && data.events.length > 0);
        after = data.seq;
        if (closed) return;
        if (gap) onResync();
        data.events.forEach(onEvent);
      } catch {
        if (closed) return;
        onLive(false);
        await new Promise((r) => setTimeout(r, 2000));
      }
    }
  })();
  return () => {
    closed = true;
    stop.abort();
  };
}

export function listen(listeners: Listeners): () => void {
  if (!onLaptop) return poll(listeners);
  let source: EventSource | null = null;
  let closed = false;
  let retry: number | undefined;
  const open = () => {
    source = new EventSource("/api/events");
    source.onopen = () => {
      listeners.onLive(true);
      listeners.onResync(); // anything said while the stream was down comes back
    };
    source.onmessage = (msg) => listeners.onEvent(JSON.parse(msg.data) as ServerEvent);
    source.onerror = () => {
      listeners.onLive(false);
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
