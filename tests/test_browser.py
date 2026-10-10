"""Drives a hidden Chrome on a temp profile. Skips without Chrome; TEAMLOOP_BROWSER_TESTS=0 skips too."""

import os
from types import SimpleNamespace
from urllib.parse import quote

import pytest

from teamloop.browser import host as host_mod
from teamloop.browser import kit

pytestmark = pytest.mark.skipif(os.getenv("TEAMLOOP_BROWSER_TESTS") == "0" or host_mod.find_chrome() is None,
                                reason="needs Chrome")

PAGE = """<html><head><title>Test shop</title></head><body><main>
<h1>Hello crew</h1>
<input id="q" placeholder="Your name">
<button onclick="document.querySelector('h1').innerText = 'Hi ' + document.getElementById('q').value">Greet</button>
<button onclick="document.querySelector('h1').innerText = 'SENT'">Send</button>
<input type="password" placeholder="Password">
</main></body></html>"""


class Ctx(SimpleNamespace):
    async def approve(self, title, details, screenshot=None):
        self.asked = title
        return self.answer


@pytest.fixture
async def browser(tmp_path):
    h = host_mod.BrowserHost(profile=tmp_path / "chrome", port=host_mod.free_port(), headless=True)
    kit.set_host(h)
    yield h
    await h.close(kill=True)
    kit.set_host(None)


async def test_open_snapshot_type_click_read(browser):
    ctx = Ctx(chat_id="t1", answer=False)
    opened = await kit.browser_open({"url": "data:text/html," + quote(PAGE)}, ctx)
    assert not opened.ok and "Refused" in opened.text  # only http(s)

    page = await browser.page_for("t1")
    await page.set_content(PAGE)
    snap = await kit.browser_snapshot({}, ctx)
    labels = {i["label"]: i["i"] for i in snap.data["items"]}
    assert {"Your name", "Greet", "Send", "Password"} <= set(labels)

    assert (await kit.browser_act({"index": labels["Your name"], "action": "type", "text": "Riya"}, ctx)).ok
    assert (await kit.browser_act({"index": labels["Greet"], "action": "click"}, ctx)).ok
    read = await kit.browser_read({}, ctx)
    assert "Hi Riya" in read.data["text"]

    denied = await kit.browser_act({"index": labels["Send"], "action": "click"}, ctx)
    assert not denied.ok and ctx.asked == 'Click "Send"'
    assert "SENT" not in (await kit.browser_read({}, ctx)).data["text"]

    refused = await kit.browser_act({"index": labels["Password"], "action": "type", "text": "x"}, ctx)
    assert refused.text.startswith("Refused:")


async def test_each_chat_gets_its_own_tab(browser):
    a = await browser.page_for("a")
    b = await browser.page_for("b")
    assert a is not b and await browser.page_for("a") is a
