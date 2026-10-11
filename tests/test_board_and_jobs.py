"""The Board (every handoff logged, plus your own tasks) and the Jobs tab (Desk's background terminal jobs)."""

import shutil
import sys
import time

import pytest
from fakes import FakeRouter, call, make_crew
from fastapi.testclient import TestClient

from teamloop.server.app import build_crew, create_app
from teamloop.tools import registry
from teamloop.tools.registry import ToolResult


async def test_delegation_is_logged_on_the_board(tmp_path):
    crew = make_crew(tmp_path, [call("delegate", bot="scout", instruction="Find the newest Node LTS.\nWith a link."),
                                "Node 24 LTS (https://nodejs.org).", "Done: Node 24."])
    seen = []
    with crew.bus.subscribe() as queue:
        await crew.post("team", "what's the newest node lts?")
        await crew.wait_idle("team")
        while not queue.empty():
            e = queue.get_nowait()
            if e["type"] == "task":
                seen.append(e["task"]["status"])
    [task] = crew.store.tasks()
    assert (task["title"], task["bot"], task["by"], task["source"]) == ("Find the newest Node LTS", "scout", "s", "delegate")
    assert task["status"] == "done" and "nodejs.org" in task["note"]
    assert seen == ["doing", "done"]  # the board moves live


async def test_failed_or_refused_step_is_blocked_with_the_reason(tmp_path, monkeypatch):
    async def risky(args, ctx):
        if not await ctx.approve("Run a command", "Remove-Item x.txt"):
            return ToolResult(False, "The person said no, so I didn't run it.")
        return ToolResult(True, "Deleted.")

    monkeypatch.setitem(registry.REGISTRY, "risky", registry.Tool("risky", "", {"type": "object"}, "memory", risky))
    crew = make_crew(tmp_path, [call("delegate", bot="desk", instruction="Delete x.txt"), call("risky"),
                                "You said no, so I left it.", "Okay, left it.",
                                call("delegate", bot="writer", instruction="Save notes.txt"), "Failed: disk is full.", "It failed."])
    crew.gate.timeout = 0.05  # nobody answers: counts as a no
    await crew.post("team", "delete x.txt")
    await crew.wait_idle("team")
    await crew.post("team", "save my notes")
    await crew.wait_idle("team")
    failed, refused = crew.store.tasks()  # newest first
    assert (refused["bot"], refused["status"]) == ("desk", "blocked") and "said no" in refused["note"]
    assert (failed["bot"], failed["status"]) == ("writer", "blocked") and failed["note"].startswith("Failed: disk is full")


def test_board_tasks_can_be_added_moved_and_removed(tmp_path):
    app = create_app(build_crew(tmp_path / "b.db", router=FakeRouter([])))
    with TestClient(app) as client:
        task = client.post("/api/tasks", json={"title": "  Plan the demo video  ", "bot": "writer"}).json()
        assert (task["title"], task["status"], task["bot"], task["source"]) == ("Plan the demo video", "todo", "writer", "manual")
        moved = client.patch(f"/api/tasks/{task['id']}", json={"status": "doing"}).json()
        assert moved["status"] == "doing" and moved["updated"] >= task["updated"]
        assert client.patch(f"/api/tasks/{task['id']}", json={"status": "later"}).status_code == 400
        assert client.post("/api/tasks", json={"title": " "}).status_code == 400
        assert [t["id"] for t in client.get("/api/tasks").json()] == [task["id"]]
        assert client.delete(f"/api/tasks/{task['id']}").json() == {"ok": True}
        assert client.get("/api/tasks").json() == []
        assert client.delete(f"/api/tasks/{task['id']}").status_code == 404


@pytest.mark.skipif(sys.platform != "win32" or not (shutil.which("pwsh") or shutil.which("powershell")),
                    reason="Desk's terminal is PowerShell on Windows")
def test_jobs_api_lists_shows_output_and_stops(tmp_path, monkeypatch):
    from teamloop import config
    from teamloop.computer import terminal

    monkeypatch.setattr(config, "workspace", lambda: tmp_path)
    started = terminal.start_job("Write-Output 'tick'; Start-Sleep -Seconds 30", tmp_path, "dm-desk")
    job_id = started.data["job"]
    app = create_app(build_crew(tmp_path / "j.db", router=FakeRouter([])))
    with TestClient(app) as client:
        listed = {j["id"]: j for j in client.get("/api/jobs").json()}
        assert listed[job_id]["state"] == "running" and listed[job_id]["chat_id"] == "dm-desk"
        for _ in range(50):  # PowerShell takes a moment to start
            if "tick" in client.get(f"/api/jobs/{job_id}").json()["output"]:
                break
            time.sleep(0.2)
        assert "tick" in client.get(f"/api/jobs/{job_id}").json()["output"]
        assert client.post(f"/api/jobs/{job_id}/stop").json()["state"] == "stopped"
        assert client.get("/api/jobs/job-nope").status_code == 404
