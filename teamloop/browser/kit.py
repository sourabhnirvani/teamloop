"""Web's tools: open, read, look at (numbered elements) and act in the crew's own Chrome.

Clicking send/post/buy/delete, pressing Enter in a chat site, or typing a line that ends with a newline in
one asks the person first. Password fields are never typed into.
"""

from __future__ import annotations

import re
import uuid

from teamloop import config
from teamloop.browser.host import BrowserHost
from teamloop.computer import risk
from teamloop.tools.registry import ToolResult, tool

READ_CHARS = 6000
MAX_ITEMS = 60
# Pages on this computer or the home network, and payment pages, open only after the person's OK.
LOCAL = re.compile(r"^https?://(localhost|127\.|0\.0\.0\.0|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|169\.254\.|"
                   r"\[::1\]|[^/:]+\.local\b)", re.IGNORECASE)
PAYMENT = re.compile(r"checkout|payment|/pay(/|\b)|billing|/cart\b|purchase", re.IGNORECASE)
LABEL_JS = """el => (el.getAttribute('aria-label') || el.innerText || el.value || el.placeholder || el.title || '')
  .trim().replace(/\\s+/g, ' ').slice(0, 80)"""

SNAPSHOT_JS = """(max) => {
  const sel = 'a[href],button,input:not([type=hidden]),textarea,select,[role=button],[role=link],[role=tab],' +
              '[role=menuitem],[role=checkbox],[role=option],[contenteditable=true],summary';
  document.querySelectorAll('[data-tl]').forEach(e => e.removeAttribute('data-tl'));
  const out = [];
  for (const el of document.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect(), st = getComputedStyle(el);
    if (r.width < 2 || r.height < 2 || st.visibility === 'hidden' || st.display === 'none') continue;
    if (r.bottom < 0 || r.top > innerHeight * 3) continue;
    const label = (el.getAttribute('aria-label') || el.innerText || el.value || el.placeholder || el.title || '')
      .trim().replace(/\\s+/g, ' ').slice(0, 80);
    const i = out.length;
    el.setAttribute('data-tl', String(i));
    const form = el.form || null;
    const searchForm = !!form && (form.matches('[role=search]') || !!form.querySelector('input[type=search]'));
    const hint = [el.name, el.placeholder, el.getAttribute('aria-label'), el.id].join(' ');
    out.push({i, kind: el.tagName.toLowerCase() + (el.type ? ':' + el.type : ''), label,
              href: el.href ? String(el.href).slice(0, 120) : undefined, password: el.type === 'password',
              search: el.type === 'search' || searchForm || /search|query|\\bq\\b|find/i.test(hint),
              submits: !!form && !searchForm && (el.type === 'submit' || el.type === 'image')});
    if (out.length >= max) break;
  }
  return {title: document.title, url: location.href, items: out};
}"""

READ_JS = """() => {
  const main = document.querySelector('main, article, [role=main]') || document.body;
  return (main ? main.innerText : '').replace(/\\n{3,}/g, '\\n\\n').trim();
}"""

_host: BrowserHost | None = None
_last: dict[int, dict[int, dict]] = {}  # id(page) -> index -> item from the last snapshot


def host() -> BrowserHost:
    global _host
    if _host is None:
        _host = BrowserHost()
    return _host


def set_host(new: BrowserHost | None) -> None:
    global _host
    _host = new
    _last.clear()


async def _page(ctx):
    return await host().page_for(ctx.chat_id)


async def _shot(page) -> str | None:
    try:
        folder = config.workspace() / "shots"
        folder.mkdir(parents=True, exist_ok=True)
        name = f"{uuid.uuid4().hex[:12]}.png"
        await page.screenshot(path=str(folder / name))
        return f"/api/shots/{name}"
    except Exception:
        return None


def _where(page_title: str, url: str) -> str:
    return f"{page_title} {url}"


def _act_risk(action: str, text: str, item: dict, where: str, label: str) -> str:
    if action == "type":
        return risk.type_risk(text, where, item["password"], field=label)
    if action == "click":
        level = risk.click_risk(label, where)
        return risk.ASK if level == risk.SAFE and item.get("submits") else level
    if action == "press":
        level = risk.keys_risk(text or "Enter", where)
        enter_in_field = risk.normalize_keys(text or "Enter") == "enter" and item["kind"].startswith("input")
        return risk.ASK if level == risk.SAFE and enter_in_field and not item.get("search") else level
    return risk.SAFE


@tool("browser_open", "Open a web page in the crew's Chrome (the person's sign-ins live there).",
      {"url": {"type": "string"}, "required": ["url"]}, kit="browser")
async def browser_open(args: dict, ctx) -> ToolResult:
    url = str(args.get("url", "")).strip()
    if not url:
        return ToolResult(False, "Which page?")
    if re.match(r"^(localhost|127\.0\.0\.1)(:\d+)?(/|$)", url):
        url = "http://" + url
    elif not re.match(r"^[a-z][a-z0-9+.\-]*:(?!\d)", url, re.IGNORECASE):
        url = "https://" + url
    if not url.startswith(("http://", "https://")):
        return ToolResult(False, "Refused: only http(s) pages can be opened.")
    if LOCAL.match(url) and not await ctx.approve(
            "Open a local address", f"Open {url}? It's on this computer or your home network."):
        return ToolResult(False, f"The person said no, so I didn't open {url}.")
    if PAYMENT.search(url) and not await ctx.approve("Open a checkout page", f"Open {url}? It looks like a payment page."):
        return ToolResult(False, f"The person said no, so I didn't open {url}.")
    page = await _page(ctx)
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        return ToolResult(False, f"Couldn't open {url}: {str(e).splitlines()[0][:120]}")
    await page.bring_to_front()
    return ToolResult(True, f"Opened \"{await page.title()}\" ({page.url}).", {"url": page.url, "title": await page.title()})


@tool("browser_snapshot", "List the links, buttons and fields on the current page, numbered, to act on them.",
      {}, kit="browser")
async def browser_snapshot(args: dict, ctx) -> ToolResult:
    page = await _page(ctx)
    snap = await page.evaluate(SNAPSHOT_JS, MAX_ITEMS)
    _last[id(page)] = {item["i"]: item for item in snap["items"]}
    return ToolResult(True, f"\"{snap['title']}\" has {len(snap['items'])} things to act on.",
                      {"url": snap["url"], "items": snap["items"]})


@tool("browser_act", "Click, type into, select or press a key on an element from the last browser_snapshot.",
      {"index": {"type": "integer"}, "action": {"type": "string", "enum": ["click", "type", "select", "press"]},
       "text": {"type": "string", "description": "text to type, option to select, or key to press (Enter, Tab...)"},
       "required": ["index", "action"]}, kit="browser")
async def browser_act(args: dict, ctx) -> ToolResult:
    page = await _page(ctx)
    index, action, text = int(args.get("index", -1)), str(args.get("action", "")), str(args.get("text", ""))
    item = _last.get(id(page), {}).get(index)
    locator = page.locator(f'[data-tl="{index}"]')
    if item is None or await locator.count() == 0:
        return ToolResult(False, "That number isn't on the page any more; take a new browser_snapshot.")
    where = _where(await page.title(), page.url)
    label = item["label"] or item["kind"]
    if item["kind"] == "input:file":
        return ToolResult(False, "Refused: bots don't upload files; the person attaches files themselves.")
    level = _act_risk(action, text, item, where, label)
    if level == risk.NEVER:
        return ToolResult(False, risk.refusal("keys" if action == "press" else action, text or "Enter", where,
                                              item["password"], label))
    if level == risk.ASK:
        url_before = page.url
        note = " (this submits a form)" if item.get("submits") else ""
        if not await ctx.approve(f"{action.capitalize()} \"{label}\"",
                                 f"On {page.url}: {action} \"{label}\"{note}" + (f" with: {text[:300]}" if text else ""),
                                 await _shot(page)):
            return ToolResult(False, f"The person said no, so I didn't {action} \"{label}\".")
        # The page may have moved on while the person decided: act only on what they saw.
        if page.url != url_before or await locator.count() == 0 or \
                (await locator.evaluate(LABEL_JS) or item["kind"]) != label:
            return ToolResult(False, "The page changed while waiting for the OK, so I didn't act; "
                                     "take a new browser_snapshot.")
    try:
        if action == "click":
            await locator.click(timeout=8000)
        elif action == "type":
            if item["kind"].startswith(("input", "textarea")):
                await locator.fill(text, timeout=8000)
            else:
                await locator.click(timeout=8000)
                await page.keyboard.type(text)
        elif action == "select":
            await locator.select_option(label=text, timeout=8000)
        elif action == "press":
            await locator.press(text or "Enter", timeout=8000)
        else:
            return ToolResult(False, f"Unknown action {action}.")
    except Exception as e:
        return ToolResult(False, f"Couldn't {action} \"{label}\": {str(e).splitlines()[0][:120]}")
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass
    done = {"click": "Clicked", "type": "Typed into", "select": "Selected in", "press": f"Pressed {text or 'Enter'} in"}
    return ToolResult(True, f"{done[action]} \"{label}\"; the page is now \"{await page.title()}\" ({page.url}).",
                      {"url": page.url})


@tool("browser_read", "Read the main text of the current page.", {}, kit="browser")
async def browser_read(args: dict, ctx) -> ToolResult:
    page = await _page(ctx)
    text = await page.evaluate(READ_JS)
    if not text:
        return ToolResult(False, f"\"{await page.title()}\" has no readable text.")
    return ToolResult(True, f"Read \"{await page.title()}\" ({len(text)} characters).",
                      {"url": page.url, "text": text[:READ_CHARS]})


@tool("browser_back", "Go back one page.", {}, kit="browser")
async def browser_back(args: dict, ctx) -> ToolResult:
    page = await _page(ctx)
    await page.go_back(wait_until="domcontentloaded")
    return ToolResult(True, f"Went back to \"{await page.title()}\" ({page.url}).")
