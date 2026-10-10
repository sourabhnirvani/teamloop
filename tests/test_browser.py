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


FORM = """<html><head><title>Sign up</title></head><body><main>
<form role="search" onsubmit="return false"><input type="search" placeholder="Search docs"></form>
<form onsubmit="document.title = 'SUBMITTED'; return false">
  <input placeholder="Email"> <input placeholder="Verification code"> <input type="file">
  <button>Continue</button>
</form>
</main></body></html>"""


async def test_forms_files_codes_and_cards_follow_the_rules(browser):
    ctx = Ctx(chat_id="t2", answer=False)
    page = await browser.page_for("t2")
    await page.set_content(FORM)
    assert browser.downloads_blocked
    items = {i["label"]: i for i in (await kit.browser_snapshot({}, ctx)).data["items"]}
    ids = {k: v["i"] for k, v in items.items()}
    assert items["Search docs"]["search"] and items["Continue"]["submits"] and not items["Email"]["search"]

    upload = await kit.browser_act({"index": next(i["i"] for i in items.values() if i["kind"] == "input:file"),
                                    "action": "click"}, ctx)
    assert upload.text.startswith("Refused: bots don't upload")
    code = await kit.browser_act({"index": ids["Verification code"], "action": "type", "text": "482913"}, ctx)
    assert code.text.startswith("Refused:") and "one-time code" in code.text
    card = await kit.browser_act({"index": ids["Email"], "action": "type", "text": "4111 1111 1111 1111"}, ctx)
    assert "card number" in card.text

    assert (await kit.browser_act({"index": ids["Search docs"], "action": "press", "text": "Enter"}, ctx)).ok
    enter = await kit.browser_act({"index": ids["Email"], "action": "press", "text": "Enter"}, ctx)
    assert not enter.ok and ctx.asked == 'Press "Email"'
    submit = await kit.browser_act({"index": ids["Continue"], "action": "click"}, ctx)
    assert not submit.ok and ctx.asked == 'Click "Continue"' and await page.title() == "Sign up"


async def test_after_an_ok_the_page_is_checked_again(browser):
    page = await browser.page_for("t3")
    await page.set_content(FORM)

    class Moving(Ctx):
        async def approve(self, title, details, screenshot=None):
            await page.set_content("<html><head><title>Other</title></head><body><button>Continue</button></body></html>")
            return True

    ctx = Moving(chat_id="t3")
    ids = {i["label"]: i["i"] for i in (await kit.browser_snapshot({}, ctx)).data["items"]}
    out = await kit.browser_act({"index": ids["Continue"], "action": "click"}, ctx)
    assert not out.ok and "page changed" in out.text


async def test_local_and_payment_pages_ask_first(browser):
    ctx = Ctx(chat_id="t4", answer=False)
    local = await kit.browser_open({"url": "http://192.168.1.1/admin"}, ctx)
    assert not local.ok and ctx.asked == "Open a local address"
    pay = await kit.browser_open({"url": "https://shop.example/checkout"}, ctx)
    assert not pay.ok and ctx.asked == "Open a checkout page"
