// Build L probe for the phone hub Worker's own filter (phone-hub/src/worker.js), run with plain Node:
//     node evidence/runs/worker-probe-yang.mjs
// The Durable Object is replaced by a recorder, so this shows which phone requests the Worker passes on to the
// laptop and which it stops itself. (The laptop checks again; see security-probe-yang.py.)
import { register } from "node:module";

register("data:text/javascript," + encodeURIComponent(`
export async function resolve(spec, ctx, next) {
  if (spec === "cloudflare:workers") return { url: "data:text/javascript,export class DurableObject {}", shortCircuit: true };
  return next(spec, ctx);
}`));
const w = await import("../../phone-hub/src/worker.js");

const forwarded = [];
const env = {
  LINK_SECRET: "s".repeat(43),
  HUB: { idFromName: () => "id", get: () => ({ fetch: async (req) => { forwarded.push(new URL(req.url).pathname); return new Response("ok"); } }) },
};

const tries = [
  ["/api/events", "the SSE stream (blocked on purpose)"],
  ["/api/%65vents", "same stream, one letter percent-encoded"],
  ["//x/api/events", "same stream behind a double slash"],
  ["/api/events/", "trailing slash"],
  ["/console", "laptop console"],
  ["/c%6Fnsole", "console, percent-encoded"],
  ["//x/console", "console behind a double slash"],
  ["/docs/../console", "dot segments"],
  ["/__laptop", "the laptop socket without the secret"],
];
for (const [path, label] of tries) {
  forwarded.length = 0;
  const res = await w.default.fetch(new Request("https://hub.example" + path), env);
  const verdict = forwarded.length ? `PASSED ON to the laptop as ${forwarded[0]}` : `stopped by the Worker (${res.status})`;
  console.log(`${path.padEnd(18)} | ${label.padEnd(40)} | ${verdict}`);
}
