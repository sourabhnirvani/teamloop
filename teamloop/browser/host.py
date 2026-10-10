"""The crew's own Chrome: a separate profile the person signs in to once, driven over CDP with Playwright.

Chrome is started as a normal detached process, so it survives the server restarting; the next start
reconnects to it. One tab per chat.
"""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
from pathlib import Path

import httpx

from teamloop import config

DEFAULT_PORT = 9333


def find_chrome() -> str | None:
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        os.environ.get("TEAMLOOP_CHROME", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.join(local, r"Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome", "/usr/bin/chromium",
    ]
    return next((c for c in candidates if c and Path(c).is_file()), None)


def _cancel(download) -> None:
    asyncio.ensure_future(download.cancel())


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class BrowserHost:
    def __init__(self, profile: Path | None = None, port: int | None = None, headless: bool | None = None):
        self.profile = profile or config.workspace() / "agent-chrome"
        self.port = port or int(os.getenv("TEAMLOOP_CHROME_PORT", DEFAULT_PORT))
        self.headless = os.getenv("TEAMLOOP_BROWSER_HEADLESS") == "1" if headless is None else headless
        self._pw = None
        self.browser = None
        self.context = None
        self._proc: subprocess.Popen | None = None
        self._pages: dict[str, object] = {}
        self._lock = asyncio.Lock()
        self.downloads_blocked = False

    @property
    def cdp_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    async def _alive(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                return (await client.get(f"{self.cdp_url}/json/version")).status_code == 200
        except httpx.HTTPError:
            return False

    def _launch(self, chrome: str) -> None:
        self.profile.mkdir(parents=True, exist_ok=True)
        args = [chrome, f"--user-data-dir={self.profile}", f"--remote-debugging-port={self.port}",
                "--no-first-run", "--no-default-browser-check", "--disable-features=Translate"]
        if self.headless:
            args.append("--headless=new")
        args.append("about:blank")
        flags = 0x00000008 | 0x00000200 if sys.platform == "win32" else 0  # DETACHED_PROCESS | NEW_PROCESS_GROUP
        self._proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)

    async def start(self) -> None:
        async with self._lock:
            if self.browser is not None and self.browser.is_connected():
                return
            if not await self._alive():
                chrome = find_chrome()
                if chrome is None:
                    raise RuntimeError("Chrome isn't installed (set TEAMLOOP_CHROME to its path).")
                self._launch(chrome)
                for _ in range(60):
                    if await self._alive():
                        break
                    await asyncio.sleep(0.25)
                else:
                    raise RuntimeError("Chrome started but its control port never opened.")
            from playwright.async_api import async_playwright

            self._pw = self._pw or await async_playwright().start()
            self.browser = await self._pw.chromium.connect_over_cdp(self.cdp_url)
            self.context = self.browser.contexts[0] if self.browser.contexts else await self.browser.new_context()
            await self._block_downloads()

    async def _block_downloads(self) -> None:
        """Bots never download files: Chrome is told to deny downloads, and any that start anyway are cancelled."""
        try:
            cdp = await self.browser.new_browser_cdp_session()
            await cdp.send("Browser.setDownloadBehavior", {"behavior": "deny"})
            self.downloads_blocked = True
        except Exception:
            self.downloads_blocked = False
        self.context.on("page", lambda page: page.on("download", _cancel))
        for page in self.context.pages:
            page.on("download", _cancel)

    async def page_for(self, chat_id: str):
        await self.start()
        page = self._pages.get(chat_id)
        if page is None or page.is_closed():
            blank = [p for p in self.context.pages if p.url == "about:blank" and p not in self._pages.values()]
            page = blank[0] if blank else await self.context.new_page()
            page.on("download", _cancel)
            self._pages[chat_id] = page
        return page

    async def close(self, kill: bool = False) -> None:
        if self.browser is not None:
            try:
                await self.browser.close()
            except Exception:
                pass
        if self._pw is not None:
            await self._pw.stop()
        self.browser = self.context = self._pw = None
        self._pages.clear()
        if kill and self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
