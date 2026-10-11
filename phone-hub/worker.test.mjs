// node --test phone-hub   (Node 18+; the Durable Object itself needs Cloudflare, these test the parts around it)
import assert from "node:assert/strict";
import { test } from "node:test";
import { register } from "node:module";

// worker.js imports "cloudflare:workers"; give Node a stand-in for its DurableObject base class
register("data:text/javascript," + encodeURIComponent(`
export async function resolve(spec, ctx, next) {
  if (spec === "cloudflare:workers") return { url: "data:text/javascript,export class DurableObject { constructor(ctx, env) { this.ctx = ctx; this.env = env; } }", shortCircuit: true };
  return next(spec, ctx);
}`));
const w = await import("./src/worker.js");

test("secrets compare in full and only when equal", () => {
  assert.equal(w.sameSecret("abc123", "abc123"), true);
  assert.equal(w.sameSecret("abc123", "abc124"), false);
  assert.equal(w.sameSecret("abc", "abc123"), false);
  assert.equal(w.sameSecret("", ""), false);
});

test("a request travels as JSON and the answer comes back as a Response", async () => {
  const req = new Request("https://hub.example.workers.dev/api/chats/team/messages?x=1", {
    method: "POST", headers: { "content-type": "application/json", cookie: "teamloop_phone=t", "x-link-secret": "nope" },
    body: JSON.stringify({ text: "hi ✨" }),
  });
  const msg = await w.packRequest(req, "r1");
  assert.equal(msg.path, "/api/chats/team/messages?x=1");
  assert.equal(msg.headers.cookie, "teamloop_phone=t");
  assert.equal(msg.headers["x-link-secret"], undefined); // never passed on
  assert.equal(new TextDecoder().decode(w.fromBase64(msg.body)), JSON.stringify({ text: "hi ✨" }));

  const res = w.unpackResponse({ id: "r1", status: 202, headers: [["content-type", "application/json"], ["set-cookie", "a=b"]],
    body: w.toBase64(new TextEncoder().encode('{"ok":true}')) });
  assert.equal(res.status, 202);
  assert.deepEqual(await res.json(), { ok: true });
});

test("with the laptop off, the API says so and pages explain it", async () => {
  const api = w.offline("/api/chats");
  assert.equal(api.status, 503);
  assert.match((await api.json()).detail, /laptop is off/);
  const page = w.offline("/");
  assert.match(await page.text(), /The laptop is off or asleep/);
});

test("laptop-only pages and a wrong secret get 404 before reaching the hub", async () => {
  const env = { LINK_SECRET: "s3cret", HUB: { idFromName: () => "id", get: () => ({ fetch: async () => new Response("hub") }) } };
  for (const path of ["/console", "/docs", "/openapi.json", "/api/events"]) {
    assert.equal((await w.default.fetch(new Request("https://h.dev" + path), env)).status, 404, path);
  }
  const wrong = new Request("https://h.dev/__laptop", { headers: { "x-link-secret": "guess" } });
  assert.equal((await w.default.fetch(wrong, env)).status, 404);
  assert.equal(await (await w.default.fetch(new Request("https://h.dev/api/chats"), env)).text(), "hub");
});
