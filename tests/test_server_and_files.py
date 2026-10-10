import time
from types import SimpleNamespace

from fakes import FakeRouter
from fastapi.testclient import TestClient

from teamloop.server.app import build_crew, create_app
from teamloop.tools import files


def test_api_roundtrip(tmp_path):
    crew = build_crew(tmp_path / "api.db", router=FakeRouter(["Hello from S"]))
    with TestClient(create_app(crew)) as client:
        bots = client.get("/api/bots").json()
        assert [b["id"] for b in bots] == ["s", "desk", "web", "scout", "inbox", "writer"]
        assert {c["id"] for c in client.get("/api/chats").json()} >= {"team", "dm-s"}

        assert client.post("/api/chats/dm-s/messages", json={"text": "hi"}).status_code == 202
        deadline = time.time() + 3
        while time.time() < deadline and len(client.get("/api/chats/dm-s/messages").json()) < 2:
            time.sleep(0.02)
        assert client.get("/api/chats/dm-s/messages").json()[-1]["text"] == "Hello from S"

        duo = client.post("/api/chats", json={"title": "Duo", "members": ["web", "scout", "nobody"]}).json()
        assert duo["members"] == ["web", "scout"]
        assert client.post("/api/chats/nope/messages", json={"text": "x"}).status_code == 404
        assert client.post("/api/approvals/nope", json={"ok": True}).status_code == 404
        assert client.post("/api/settings", json={"save_tokens": True}).json()["save_tokens"] is True
        assert isinstance(client.get("/api/keys").json(), list)


class Ctx(SimpleNamespace):
    async def approve(self, title, details, screenshot=None):
        self.asked = title
        return self.answer


async def test_files_write_read_and_refuse_outside(workspace):
    ctx = Ctx(answer=True)
    saved = await files.write_file({"path": "workspace/notes/a.md", "content": "hello"}, ctx)
    assert saved.ok and saved.data["bytes"] == 5
    assert (await files.read_file({"path": "workspace/notes/a.md"}, ctx)).data["text"] == "hello"

    again = await files.write_file({"path": "workspace/notes/a.md", "content": "x"}, ctx)
    assert not again.ok and "already exists" in again.text

    ctx.answer = False
    denied = await files.write_file({"path": "workspace/notes/a.md", "content": "x", "overwrite": True}, ctx)
    assert not denied.ok and ctx.asked == "Replace a file"

    outside = await files.write_file({"path": "C:/Windows/evil.txt", "content": "x"}, ctx)
    assert not outside.ok and outside.text.startswith("Refused:")
    sneaky = await files.write_file({"path": "workspace/../../escape.txt", "content": "x"}, ctx)
    assert not sneaky.ok
