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
