// A tiny hash router: #/chats/team, #/crew, #/settings/keys, plus overlays like ?bot=desk or ?new=group.
// Every screen has an address, so the phone's Back button closes the top layer.

import { useEffect, useState } from "react";

export type Tab = "chats" | "crew" | "settings";
export type Route = { tab: Tab; id: string | null; bot: string | null; overlay: string | null };

const TABS: Tab[] = ["chats", "crew", "settings"];

export function parse(hash: string): Route {
  const [path, query = ""] = hash.replace(/^#\/?/, "").split("?");
  const [first, second] = path.split("/");
  const tab = (TABS as string[]).includes(first) ? (first as Tab) : "chats";
  const params = new URLSearchParams(query);
  return { tab, id: second || null, bot: params.get("bot"), overlay: params.get("new") };
}

export function href(tab: Tab, id?: string | null, extra?: Record<string, string>): string {
  const q = extra ? `?${new URLSearchParams(extra)}` : "";
  return `#/${tab}${id ? `/${id}` : ""}${q}`;
}

export function go(to: string, replace = false) {
  if (replace) window.history.replaceState(null, "", to);
  else window.history.pushState(null, "", to);
  window.dispatchEvent(new HashChangeEvent("hashchange"));
}

// open an overlay on top of the current screen (Back closes it)
export function withOverlay(route: Route, key: "bot" | "new", value: string): string {
  return href(route.tab, route.id, { [key]: value });
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parse(window.location.hash));
  useEffect(() => {
    const on = () => setRoute(parse(window.location.hash));
    window.addEventListener("hashchange", on);
    window.addEventListener("popstate", on);
    return () => {
      window.removeEventListener("hashchange", on);
      window.removeEventListener("popstate", on);
    };
  }, []);
  return route;
}
