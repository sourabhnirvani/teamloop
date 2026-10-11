// Updates: the laptop says which app bundle it serves; if this open app (a phone above all) runs an
// older one, it offers Update, which drops the saved copy and loads the new one.

export function runningVersion(): string | null {
  const src = document.querySelector<HTMLScriptElement>('script[src*="/assets/index-"]')?.getAttribute("src");
  return src ? src.split("/").pop() ?? null : null; // null in `npm run dev`: nothing to compare
}

export async function latestVersion(): Promise<string | null> {
  try {
    const res = await fetch("/api/version", { cache: "no-store" });
    return res.ok ? ((await res.json()) as { version: string }).version : null;
  } catch {
    return null;
  }
}

export async function updateAvailable(): Promise<boolean> {
  const mine = runningVersion();
  const latest = await latestVersion();
  return !!mine && !!latest && latest !== "dev" && latest !== mine;
}

// A note on the phone's screen while the app is in the background (updates, approval cards). Phones only
// show these through the service worker; it needs the person's OK once (Settings → Appearance & updates).
export async function notify(title: string, body: string, tag: string): Promise<void> {
  try {
    if (document.visibilityState === "visible" || !("Notification" in window) || Notification.permission !== "granted") return;
    const reg = await navigator.serviceWorker?.getRegistration();
    if (reg) await reg.showNotification(title, { body, tag, icon: "/app-icon.png", badge: "/app-icon.png" });
    else new Notification(title, { body, tag, icon: "/app-icon.png" });
  } catch {
    /* notifications blocked: the in-app prompt still shows */
  }
}

export async function askToNotify(): Promise<NotificationPermission | "unsupported"> {
  if (!("Notification" in window)) return "unsupported";
  return Notification.permission === "default" ? Notification.requestPermission() : Notification.permission;
}

export async function applyUpdate(): Promise<void> {
  try {
    const reg = await navigator.serviceWorker?.getRegistration();
    await reg?.update();
  } catch {
    /* no service worker: a reload is enough */
  }
  try {
    await Promise.all((await caches.keys()).map((k) => caches.delete(k)));
  } catch {
    /* caches not available */
  }
  window.location.reload();
}
