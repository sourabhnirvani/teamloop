"""Fixes for what the live evals found: a recovery eval that passed with no failure, PowerShell variables in file
paths, and the lead copying Desk's $env:USERPROFILE hint into instructions."""

import os
import re

import pytest

from evals import run as evals
from teamloop import kits
from teamloop.crew import bots
from teamloop.tools import files, registry


def test_powershell_and_percent_variables_expand_inside_the_allowed_folders():
    desktop = files.roots()["desktop"].resolve()
    os.environ["TL_TEST_DIR"] = str(desktop)
    assert files.resolve(r"$env:TL_TEST_DIR\a.txt") == desktop / "a.txt"
    assert files.resolve(r"%TL_TEST_DIR%\b.txt") == desktop / "b.txt"


def test_a_variable_cannot_reach_outside_the_allowed_folders():
    os.environ["TL_TEST_DIR"] = str(files.roots()["desktop"])
    for raw in (r"%TL_TEST_DIR%\..\..\..\Windows\x.txt", r"$env:WINDIR\System32\drivers\etc\hosts",
                r"$env:SystemRoot\win.ini"):
        with pytest.raises(ValueError):
            files.resolve(raw)


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
