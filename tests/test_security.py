"""Build C, key security: key-carrying tool calls are refused, programs get no keys, secret files stay shut."""

import os
from types import SimpleNamespace

from fakes import FakeRouter
from fastapi.testclient import TestClient

from teamloop import kits
from teamloop.computer import terminal
from teamloop.keys import vault
from teamloop.server.app import build_crew, create_app
from teamloop.tools import files, registry

from test_terminal import needs_shell

FAKE = "gsk_" + "testonlynotarealkey0123456789abcdefABCDEF"


async def test_web_search_with_a_key_is_blocked_and_logged(tmp_path):
    kits.load_all()
    os.environ["GROQ_API_KEY"] = FAKE
    crew = build_crew(tmp_path / "sec.db", router=FakeRouter([]))
    ctx = SimpleNamespace(crew=crew, bot_id="scout", chat_id="c1")
    result = await registry.run("web_search", {"query": f"is {FAKE} valid"}, ctx)
    assert not result.ok and "Refused" in result.text and FAKE not in result.text
    blocked = crew.store.get_setting(registry.BLOCKED)
    assert [b["tool"] for b in blocked] == ["web_search"] and blocked[0]["bot"] == "scout"
    assert FAKE not in str(blocked)
    with TestClient(create_app(crew)) as client:
        body = client.get("/api/security").json()
    assert body["blocked"][0]["tool"] == "web_search" and FAKE not in str(body)


async def test_a_call_without_a_key_is_not_blocked(tmp_path):
    kits.load_all()
    os.environ["GROQ_API_KEY"] = FAKE
    ctx = SimpleNamespace(crew=build_crew(tmp_path / "ok.db", router=FakeRouter([])), bot_id="s", chat_id="c")
    assert registry._block_key_leak("read_file", {"path": "notes.md"}, ctx) is None


@needs_shell
async def test_programs_get_no_keys(tmp_path):
    os.environ["GROQ_API_KEY"] = FAKE
    os.environ["TEAMLOOP_HARMLESS"] = "visible"
    code, out, _, _ = await terminal.run('Write-Output "[$env:GROQ_API_KEY][$env:TEAMLOOP_HARMLESS]"', tmp_path)
    assert code == 0 and "[][visible]" in out


async def test_file_tools_refuse_secret_files():
    folder = files.roots()["workspace"]
    for name in (".env", ".env.local", "teamloop.db", "keys.vault"):
        (folder / name).write_text("GROQ_API_KEY=x", encoding="utf-8")
        result = await files.read_file({"path": name}, None)
        assert not result.ok and "Refused" in result.text, name
    (folder / ".env.example").write_text("GROQ_API_KEY=", encoding="utf-8")
    assert (await files.read_file({"path": ".env.example"}, None)).ok


def test_security_lists_vault_names_only(tmp_path):
    vault.put("GEMINI_API_KEY", "AIza" + "x" * 35)
    with TestClient(create_app(build_crew(tmp_path / "v.db", router=FakeRouter([])))) as client:
        body = client.get("/api/security").json()
    assert body["locked"] == 1 and body["names"] == ["GEMINI_API_KEY"] and "AIza" not in str(body)
