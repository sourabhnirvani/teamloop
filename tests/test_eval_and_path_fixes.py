"""Fixes for what the live evals found: a recovery eval that passed with no failure, PowerShell variables in file
paths, and the lead copying Desk's $env:USERPROFILE hint into instructions."""

import os
import re

import pytest

from evals import run as evals
from teamloop import kits
from teamloop.crew import bots
from teamloop.tools import files, registry


def test_folder_variables_expand_inside_the_allowed_folders(monkeypatch):
    desktop = files.roots()["desktop"].resolve()
    monkeypatch.setenv("USERPROFILE", str(desktop.parent))
    monkeypatch.setenv("TEMP", str(desktop))
    assert files.resolve(rf"$env:USERPROFILE\{desktop.name}\a.txt") == desktop / "a.txt"
    assert files.resolve(r"%TEMP%\b.txt") == desktop / "b.txt"
    assert files.resolve(r"$TEMP\c.txt") == desktop / "c.txt"


def test_a_variable_cannot_reach_outside_the_allowed_folders(monkeypatch):
    monkeypatch.setenv("TEMP", str(files.roots()["desktop"]))
    with pytest.raises(ValueError):
        files.resolve(r"%TEMP%\..\..\..\Windows\x.txt")
    # variables outside the allowlist stay literal: a harmless name inside the workspace, never C:\Windows
    workspace = files.roots()["workspace"].resolve()
    for raw in (r"$env:WINDIR\System32\drivers\etc\hosts", r"%SystemRoot%\win.ini"):
        assert files.resolve(raw).is_relative_to(workspace), raw


def test_secret_variables_never_expand_into_a_path(monkeypatch):
    key = "gsk_" + "fakekeyfortheexpandtest0123456789abcdEF"
    monkeypatch.setenv("GROQ_API_KEY", key)
    monkeypatch.setenv("NVIDIA_API_KEY", key)
    for raw in ("Documents/$env:GROQ_API_KEY.txt", "Documents/%NVIDIA_API_KEY%.txt", "Documents/${GROQ_API_KEY}.txt",
                "Documents/$GROQ_API_KEY.txt"):
        assert key not in str(files.resolve(raw)), raw
        assert key not in files.expand(raw), raw


def test_the_lead_sees_what_each_teammate_does_but_not_their_working_notes():
    lead = bots.system_prompt(bots.BOTS["s"])
    desk = bots.system_prompt(bots.BOTS["desk"])
    assert "$env:USERPROFILE" in desk and "$env:USERPROFILE" not in lead
    assert re.search(r"- desk: Desk, Computer\. You run the Windows laptop", lead)
    assert "exact path the tool returned" in bots.RULES


class FakeEval:
    def __init__(self, fail_through_tool: bool):
        self.fail_through_tool = fail_through_tool

    async def say(self, text):
        path = re.search(r"workspace/evals/(\S+)", text).group(1)
        args = {"path": f"workspace/evals/{path}", "content": "recovered"}
        if self.fail_through_tool:          # the crew's way: the save fails once (simulated), then it retries
            first = await registry.run("write_file", args, None)
            assert not first.ok
            await registry.run("write_file", args, None)
        else:                               # a "recovery" that never met a failure
            real = files.resolve(args["path"])
            real.parent.mkdir(parents=True, exist_ok=True)
            real.write_text("recovered", encoding="utf-8")
        return "saved"


async def test_the_recovery_eval_fails_unless_a_failure_really_happened():
    kits.load_all()
    with pytest.raises(AssertionError, match="never happened"):
        await evals.live_recovery(FakeEval(fail_through_tool=False))
    assert "retried" in await evals.live_recovery(FakeEval(fail_through_tool=True))
    # and again in the same process: it still really fails first
    assert "retried" in await evals.live_recovery(FakeEval(fail_through_tool=True))
