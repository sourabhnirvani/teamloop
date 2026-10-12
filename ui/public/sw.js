// TeamLoop service worker: lets the phone install the app and open it offline.
// The API is never cached; live chat always comes from the laptop.
const CACHE = "teamloop-v3"; // a new name clears the old cache (v2 could hold an old logo or an error page)

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) =>
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()),
  ),
);

// Save the fresh page, and drop built files from older versions (same name, different hash).
async function keep(page) {
  const html = await page.clone().text();
  const cache = await caches.open(CACHE);
  await cache.put("/", page);
  const used = new Set(html.match(/\/assets\/[\w.-]+/g) || []);
  const families = new Set([...used].map((p) => p.replace(/-[\w]+\.(js|css)$/, "")));
  for (const req of await cache.keys()) {
    const path = new URL(req.url).pathname;
    if (path.startsWith("/assets/") && !used.has(path) && families.has(path.replace(/-[\w]+\.(js|css)$/, ""))) {
      await cache.delete(req);
    }
  }
}

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api") || url.pathname === "/pair") return;
  if (e.request.mode === "navigate") {
    // Fresh page when the laptop is reachable, the saved one when it isn't.
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          if (res.ok) e.waitUntil(keep(res.clone())); // never save an error page as the app
          return res;
        })
        .catch(() => caches.match("/")),
    );
    return;
  }
  // Everything with a fixed name (logo.svg, the manifest, app-icon.png, mascot frames) can change in an update:
  // fresh when the laptop is reachable (asking the laptop each time, not the browser's own cache), the saved copy
  // when it isn't.
  if (!url.pathname.startsWith("/assets/") && !url.pathname.startsWith("/icons/")) {
    e.respondWith(
      fetch(e.request, { cache: "no-cache" })
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            e.waitUntil(caches.open(CACHE).then((c) => c.put(e.request, copy)));
          }
          return res;
        })
        .catch(() => caches.match(e.request)),
    );
    return;
  }
  // Built files and icons have hashed names, so a saved copy is always right.
  e.respondWith(
    caches.match(e.request).then(
      (hit) =>
        hit ||
        fetch(e.request).then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(e.request, copy));
          }
          return res;
        }),
    ),
  );
});

// tapping a TeamLoop notification (update ready, a bot needs your OK) brings the app up
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  e.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((wins) => {
      const open = wins.find((w) => new URL(w.url).origin === location.origin);
      return open ? open.focus() : self.clients.openWindow("/");
    }),
  );
});
