// TeamLoop phone hub: one fixed https address for the phone app, on the person's own free Cloudflare account.
//
// The laptop dials OUT to this hub over a websocket (nothing at home is opened). A phone's request comes in
// here, goes down that websocket to the laptop's TeamLoop, and the answer comes back up. The laptop still makes
// every check (pairing cookie, approvals): the hub only carries bytes. If the laptop is off, the phone gets a
// clear "laptop is off" answer instead of a broken page.

import { DurableObject } from "cloudflare:workers";

const TIMEOUT_MS = 45_000; // long-polls wait up to 25 s on the laptop
const HOP = new Set(["connection", "keep-alive", "upgrade", "transfer-encoding", "te", "trailer", "proxy-authorization",
  "proxy-authenticate", "host", "content-length", "x-link-secret"]);
const LAPTOP_ONLY = ["/console", "/docs", "/redoc", "/openapi.json"]; // and everything under them
const SSE = "/api/events"; // the laptop's stream, which a hub can't carry; phones long-poll /api/events/poll instead

export function sameSecret(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || !a || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export function toBase64(bytes) {
  let s = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) s += String.fromCharCode(...bytes.subarray(i, i + chunk));
  return btoa(s);
}

export function fromBase64(text) {
  const s = atob(text || "");
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
  return out;
}

// what goes down the websocket for one phone request
export async function packRequest(request, id) {
  const url = new URL(request.url);
  const headers = {};
  for (const [k, v] of request.headers) if (!HOP.has(k.toLowerCase())) headers[k] = v;
  const body = ["GET", "HEAD"].includes(request.method) ? "" : toBase64(new Uint8Array(await request.arrayBuffer()));
  return { id, method: request.method, path: url.pathname + url.search, headers, body };
}

export function unpackResponse(msg) {
  const headers = new Headers();
  for (const [k, v] of msg.headers || []) if (!HOP.has(k.toLowerCase())) headers.append(k, v);
  return new Response(msg.status === 204 || msg.status === 304 ? null : fromBase64(msg.body), { status: msg.status, headers });
}

export function offline(path) {
  if (path.startsWith("/api/")) {
    return Response.json({ detail: "The laptop is off or asleep. TeamLoop answers again when it's back." }, { status: 503 });
  }
  return new Response(`<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TeamLoop</title><body style="margin:0;min-height:100vh;display:grid;place-items:center;background:#090c18;color:#eceffa;font:16px system-ui;text-align:center;padding:24px">
<div><div style="font-size:48px">💤</div><h2>The laptop is off or asleep</h2><p style="color:#8e97bb">Turn it on and TeamLoop opens here again.<br>This page checks every 10 seconds.</p></div>
<script>setTimeout(()=>location.reload(),10000)</script>`, { status: 503, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } });
}

export class Hub extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.pending = new Map(); // request id -> { resolve, timer }
    this.seq = 0;
  }

  laptop() {
    return this.ctx.getWebSockets("laptop")[0];
  }

  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === "/__laptop") {
      if (request.headers.get("upgrade") !== "websocket") return new Response("websocket only", { status: 426 });
      for (const old of this.ctx.getWebSockets("laptop")) old.close(1012, "a newer laptop connection replaced this one");
      const pair = new WebSocketPair();
      this.ctx.acceptWebSocket(pair[1], ["laptop"]); // hibernates between messages: idle time costs nothing
      return new Response(null, { status: 101, webSocket: pair[0] });
    }
    const ws = this.laptop();
    if (!ws) return offline(url.pathname);
    const id = `${Date.now().toString(36)}-${++this.seq}`;
    const msg = await packRequest(request, id);
    return await new Promise((resolve) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        resolve(url.pathname.startsWith("/api/") ? Response.json({ detail: "The laptop didn't answer in time." }, { status: 504 }) : offline(url.pathname));
      }, TIMEOUT_MS);
      this.pending.set(id, { resolve, timer });
      try {
        ws.send(JSON.stringify(msg));
      } catch {
        clearTimeout(timer);
        this.pending.delete(id);
        resolve(offline(url.pathname));
      }
    });
  }

  async webSocketMessage(ws, data) {
    let msg;
    try {
      msg = JSON.parse(typeof data === "string" ? data : new TextDecoder().decode(data));
    } catch {
      return;
    }
    if (msg.type === "ping") return ws.send(JSON.stringify({ type: "pong" }));
    const waiting = this.pending.get(msg.id);
    if (!waiting) return;
    clearTimeout(waiting.timer);
    this.pending.delete(msg.id);
    waiting.resolve(unpackResponse(msg));
  }

  async webSocketClose(ws, code, reason) {
    try { ws.close(code, reason); } catch { /* already closed */ }
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/__laptop") {
      if (!sameSecret(request.headers.get("x-link-secret") || "", env.LINK_SECRET || "")) {
        return new Response("not found", { status: 404 });
      }
    } else if (url.pathname === SSE || LAPTOP_ONLY.some((p) => url.pathname === p || url.pathname.startsWith(p + "/"))) {
      return new Response("not found", { status: 404 });
    }
    const hub = env.HUB.get(env.HUB.idFromName("teamloop"));
    return hub.fetch(request);
  },
};
