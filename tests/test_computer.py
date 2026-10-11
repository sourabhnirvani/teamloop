import os
import sys

import pytest

from teamloop.computer import risk

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="computer kit is Windows-only")


@pytest.mark.parametrize("name,title,expected", [
    ("Send", "WhatsApp", risk.ASK),
    ("  Post  ", "LinkedIn", risk.ASK),
    ("Delete", "File Explorer", risk.ASK),
    ("Place order", "Amazon", risk.ASK),
    ("Sender settings", "Outlook", risk.SAFE),
    ("Bold", "Word", risk.SAFE),
    ("Save", "Notepad", risk.SAFE),
])
def test_click_risk(name, title, expected):
    assert risk.click_risk(name, title) == expected


@pytest.mark.parametrize("keys,title,expected", [
    ("Enter", "WhatsApp", risk.ASK),
    ("ctrl + Enter", "Inbox - Gmail - Chrome", risk.ASK),
    ("enter", "Untitled - Notepad", risk.SAFE),
    ("shift+delete", "File Explorer", risk.ASK),
    ("Alt+F4", "Anything", risk.ASK),
    ("ctrl+s", "Word", risk.SAFE),
])
def test_keys_risk(keys, title, expected):
    assert risk.keys_risk(keys, title) == expected


def test_type_and_power_risk():
    assert risk.type_risk("hunter2", "Login", is_password=True) == risk.NEVER
    assert risk.type_risk("4111 1111 1111 1111", "Checkout - Chrome") == risk.NEVER  # card (Luhn)
    assert risk.type_risk("1234 5678 9012 3456", "Notepad") == risk.SAFE  # not a card number
    assert risk.type_risk("gsk_" + "a" * 52, "Notepad") == risk.NEVER  # API key
    assert risk.type_risk("482913", "Sign in", field="Verification code") == risk.NEVER
    assert risk.type_risk("482913", "Calculator") == risk.SAFE
    assert risk.type_risk("dir\n", "Windows PowerShell [powershell.exe]") == risk.NEVER
    assert risk.type_risk("hello", "TeamLoop - Chrome [chrome.exe]") == risk.NEVER
    assert risk.click_risk("Approve", "TeamLoop [electron.exe]") == risk.NEVER
    assert risk.keys_risk("win+r", "Notepad [notepad.exe]") == risk.NEVER
    assert risk.keys_risk("enter", "Command Prompt [cmd.exe]") == risk.NEVER
    assert risk.keys_risk("enter", "Run [explorer.exe]") == risk.NEVER
    assert risk.keys_risk("enter", "Downloads [explorer.exe]") == risk.ASK
    assert risk.refusal("keys", "win+r").startswith("Refused: Windows-key")
    assert risk.type_risk("hi there\n", "Telegram") == risk.ASK
    assert risk.type_risk("hi there", "Telegram") == risk.SAFE
    assert risk.type_risk("line one\nline two", "Notepad") == risk.SAFE
    assert risk.power_risk("shutdown") == risk.ASK
    assert risk.power_risk("format c:") == risk.NEVER


def test_key_translation():
    from teamloop.computer import uia

    assert uia.keys_to_sendkeys("ctrl+s") == "^s"
    assert uia.keys_to_sendkeys("Alt + Tab") == "%{TAB}"
    assert uia.keys_to_sendkeys("ctrl+shift+esc") == "^+{ESC}"
    assert uia.keys_to_sendkeys("win+d") == "{VK_LWIN down}d{VK_LWIN up}"
    assert uia.escape_text("a+b{c}\n(x)") == "a{+}b{{}c{}}{ENTER}{(}x{)}"


def test_app_matching():
    from teamloop.computer import apps

    listing = [{"name": "Calculator", "appid": "calc!App"}, {"name": "Google Chrome", "appid": "Chrome"},
               {"name": "Visual Studio Code", "appid": "vsc"}, {"name": "Paint", "appid": "paint"},
               {"name": "Paint 3D", "appid": "paint3d"}]
    assert apps.match("calculator", listing)["appid"] == "calc!App"
    assert apps.match("chrome", listing)["appid"] == "Chrome"
    assert apps.match("vscode", listing)["appid"] == "vsc"
    assert apps.match("paint", listing)["appid"] == "paint"
    assert apps.match("calculater", listing)["appid"] == "calc!App"
    assert apps.match("photoshop", listing) is None


def test_window_listing_works():
    from teamloop.computer import winapi

    wins = winapi.windows()
    assert isinstance(wins, list)
    assert all(w.title and w.hwnd for w in wins)


@pytest.mark.skipif(os.getenv("TEAMLOOP_DESKTOP_TESTS") != "1", reason="real desktop test; set TEAMLOOP_DESKTOP_TESTS=1")
async def test_open_and_close_calculator():
    from types import SimpleNamespace

    from teamloop.computer import tools

    class Ctx(SimpleNamespace):
        async def approve(self, *a, **k):
            return True

        async def emit(self, *a, **k):
            pass

    ctx = Ctx(bot_id="desk", chat_id="t")
    opened = await tools.open_app({"name": "calculator"}, ctx)
    assert opened.ok, opened.text
    closed = await tools.close_app({"name": "calculator"}, ctx)
    assert closed.ok, closed.text
    status = await tools.system_status({}, ctx)
    assert status.ok and "volume" in status.text
