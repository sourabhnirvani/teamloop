"""Web kit: search and read pages without a browser (fast, no sign-in needed)."""

from __future__ import annotations

import html
import re
from urllib.parse import parse_qs, quote, unquote, urlparse

import httpx

from teamloop.tools.registry import ToolResult, tool

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
# Wikimedia refuses browser-looking agents from scripts; it wants an honest one with a contact link.
BOT_UA = "TeamLoop/0.1 (https://github.com/sourabhnirvani/teamloop)"
_WIKIMEDIA = re.compile(r"(^|\.)(wikipedia|wikimedia|wiktionary|wikidata)\.org$", re.I)
PAGE_CHARS = 6000
MAX_BYTES = 2_000_000

_DDG_LINK = re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_DDG_SNIPPET = re.compile(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', re.S)
_TAG = re.compile(r"<[^>]+>")
_DROP = re.compile(r"<(script|style|noscript|svg|head|nav|footer)[^>]*>.*?</\1>", re.S | re.I)
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)


def _clean(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", fragment))).strip()


def _ddg_url(href: str) -> str:
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        return unquote(parse_qs(parsed.query).get("uddg", [href])[0])
    return href


def _ua_for(url: str) -> str:
    return BOT_UA if _WIKIMEDIA.search(urlparse(url).hostname or "") else UA


def _client(**kw) -> httpx.AsyncClient:
    return httpx.AsyncClient(headers={"User-Agent": UA}, timeout=20, follow_redirects=True, **kw)


async def _duckduckgo(client: httpx.AsyncClient, query: str, n: int) -> list[dict]:
    resp = await client.post("https://html.duckduckgo.com/html/", data={"q": query})
    if resp.status_code != 200:  # 202 is its "are you a bot?" page
        return []
    return _ddg_results(resp.text, n)


def _ddg_results(page: str, n: int) -> list[dict]:
    links = _DDG_LINK.findall(page)
    snippets = _DDG_SNIPPET.findall(page)
    results = []
    for i, (href, title) in enumerate(links):
        url = _ddg_url(html.unescape(href))
        if "duckduckgo.com/y.js" in url:  # ads
            continue
        results.append({"title": _clean(title), "url": url, "snippet": _clean(snippets[i]) if i < len(snippets) else ""})
        if len(results) >= n:
            break
    return results


async def _wikipedia(client: httpx.AsyncClient, query: str, n: int) -> list[dict]:
    resp = await client.get("https://en.wikipedia.org/w/api.php", headers={"User-Agent": BOT_UA}, params={
        "action": "query", "list": "search", "srsearch": query, "format": "json", "srlimit": n})
    if resp.status_code != 200:
        return []
    hits = resp.json().get("query", {}).get("search", [])
    return [{"title": h["title"], "url": "https://en.wikipedia.org/wiki/" + quote(h["title"].replace(" ", "_")),
             "snippet": _clean(h.get("snippet", ""))} for h in hits]


async def _browser_search(query: str, n: int) -> list[dict]:
    """Search DuckDuckGo in the crew's own Chrome (free, no key). Empty if Chrome can't be used."""
    try:
        from teamloop.browser import kit as browser_kit

        browser = browser_kit.host()
        await browser.start()
        page = await browser.context.new_page()
    except Exception:
        return []
    try:
        await page.goto("https://html.duckduckgo.com/html/?q=" + quote(query), wait_until="domcontentloaded",
                        timeout=20000)
        return _ddg_results(await page.content(), n)
    except Exception:
        return []
    finally:
        try:
            await page.close()
        except Exception:
            pass


@tool("web_search", "Search the web. Returns titles, links and short snippets.",
      {"query": {"type": "string"}, "max_results": {"type": "integer", "description": "1-10, default 5"},
       "required": ["query"]}, kit="web")
async def web_search(args: dict, ctx) -> ToolResult:
    query = str(args.get("query", "")).strip()
    if not query:
        return ToolResult(False, "Tell me what to search for.")
    n = max(1, min(10, int(args.get("max_results") or 5)))
    async with _client() as client:
        results, source = [], "the web"
        try:
            results = await _duckduckgo(client, query, n)
        except httpx.HTTPError:
            results = []
        if not results:  # DuckDuckGo challenges scripts after a few searches; a real browser isn't challenged
            results = await _browser_search(query, n)
        if not results:
            source = "Wikipedia"
            try:
                results = await _wikipedia(client, query, n)
            except httpx.HTTPError:
                results = []
    if not results:
        return ToolResult(False, f"Search for {query!r} found nothing (or search is unreachable).")
    return ToolResult(True, f"Found {len(results)} results on {source} for {query!r}.", {"results": results})


@tool("fetch_page", "Read a web page and return its main text.",
      {"url": {"type": "string"}, "required": ["url"]}, kit="web")
async def fetch_page(args: dict, ctx) -> ToolResult:
    url = str(args.get("url", "")).strip()
    if not re.match(r"^https?://", url):
        return ToolResult(False, "Give a full http(s) link.")
    try:
        async with _client() as client:
            resp = await client.get(url, headers={"User-Agent": _ua_for(url)})
    except httpx.HTTPError as e:
        return ToolResult(False, f"Could not open {url}: {e.__class__.__name__}.")
    if resp.status_code >= 400:
        return ToolResult(False, f"{url} answered {resp.status_code}.")
    kind = resp.headers.get("content-type", "")
    body = resp.content[:MAX_BYTES].decode(resp.encoding or "utf-8", errors="replace")
    if "html" in kind:
        match = _TITLE.search(body)
        title = _clean(match.group(1)) if match else url
        text = _clean(_DROP.sub(" ", body))
    elif kind.startswith("text/") or "json" in kind:
        title, text = url, body.strip()
    else:
        return ToolResult(False, f"{url} is not a text page ({kind or 'unknown type'}).")
    if not text:
        return ToolResult(False, f"{url} had no readable text.")
    return ToolResult(True, f"Read {title!r} ({len(text)} characters).",
                      {"url": str(resp.url), "title": title, "text": text[:PAGE_CHARS]})
