// Small fetch helper for the pages in ui/src/settings/ (same behaviour as api.ts: 401 goes to /pair,
// errors throw the server's `detail`).

export async function req<T>(path: string, method: "GET" | "POST" | "DELETE" = "GET"): Promise<T> {
  const res = await fetch(path, method === "GET" ? undefined : { method });
  if (res.status === 401) window.location.assign("/pair");
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
