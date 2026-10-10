"""Desk's terminal: a PowerShell per chat.

`cd` sticks between runs, every run reads back its exit code and output, and long jobs (servers,
builds) run in the background with their output in workspace/jobs/. Deleting, killing processes,
registry, services and power ask first (risk.command_risk); wiping disks is refused.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import os
import secrets
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from teamloop import config
from teamloop.computer import risk
from teamloop.keys.redact import redact
from teamloop.tools.registry import ToolResult, tool

TIMEOUT = 60
MAX_TIMEOUT = 600
KEEP = 4000          # characters of each stream the model gets back
TAIL_LINES = 40
_MARK = "__TEAMLOOP_CWD__"
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_NEW_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

_cwd: dict[str, Path] = {}  # chat id -> where `cd` left that chat's terminal


@dataclass
class Job:
    id: str
    chat_id: str
    command: str
    proc: subprocess.Popen
    log: Path
    started: float


_jobs: dict[str, Job] = {}


def shell() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def here(chat_id: str) -> Path:
    cwd = _cwd.get(chat_id)
    return cwd if cwd and cwd.is_dir() else Path.home()


def _script(command: str, cwd: Path) -> str:
    where = str(cwd).replace("'", "''")
    return "\n".join([
        "[Console]::OutputEncoding = [Text.Encoding]::UTF8",
        "$ProgressPreference = 'SilentlyContinue'",
        f"Set-Location -LiteralPath '{where}'",
        "$global:LASTEXITCODE = 0",
        command,
        "$__ok = $?",
        "$__code = if ($LASTEXITCODE) { $LASTEXITCODE } elseif ($__ok) { 0 } else { 1 }",
        f"[Console]::Out.WriteLine('{_MARK}' + (Get-Location).ProviderPath)",
        "exit $__code",
    ])


def _argv(command: str, cwd: Path) -> list[str]:
    encoded = base64.b64encode(_script(command, cwd).encode("utf-16-le")).decode()
    return [shell() or "powershell", "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-EncodedCommand", encoded]


def _kill_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=_NO_WINDOW)
    else:  # pragma: no cover - TeamLoop runs on Windows
        os.kill(pid, 9)


def _read(fh) -> str:
    fh.seek(0)
    return fh.read().decode("utf-8", "replace").replace("\r\n", "\n")


def _split_mark(stdout: str) -> tuple[str, Path | None]:
    lines, cwd = [], None
    for line in stdout.split("\n"):
        if line.startswith(_MARK):
            cwd = Path(line[len(_MARK):].strip())
        else:
            lines.append(line)
    return "\n".join(lines).strip("\n"), cwd


def _tail(text: str) -> str:
    text = redact(text)
    return text if len(text) <= KEEP else "…" + text[-KEEP:]


async def run(command: str, cwd: Path, timeout: float = TIMEOUT) -> tuple[int | None, str, str, Path | None]:
    """(exit code or None on timeout, stdout, stderr, the folder the command ended in)."""
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(_argv(command, cwd), stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                cwd=cwd, creationflags=_NO_WINDOW)
        deadline = time.monotonic() + timeout
        timed_out = False
        try:
            while proc.poll() is None:
                if time.monotonic() > deadline:
                    timed_out = True
                    _kill_tree(proc.pid)
                    with contextlib.suppress(subprocess.TimeoutExpired):
                        proc.wait(5)
                    break
                await asyncio.sleep(0.05)
        except BaseException:  # Stop pressed: never leave the command running
            _kill_tree(proc.pid)
            raise
        code = None if timed_out else proc.returncode
        stdout, new_cwd = _split_mark(_read(out))
        return code, stdout, _read(err).strip("\n"), new_cwd


async def _allowed(command: str, cwd: Path, ctx) -> ToolResult | None:
    level = risk.command_risk(command)
    if level == risk.NEVER:
        return ToolResult(False, "Refused: that command can wipe disks or boot settings, so the crew never runs it.")
    if level == risk.ASK and not await ctx.approve("Run a command", f"{command}\n\nin {cwd}"):
        return ToolResult(False, f"The person said no, so I didn't run it: {command}")
    return None


@tool("run_command",
      "Run a PowerShell command in this chat's terminal and get its exit code and output. `cd` sticks between "
      "runs. For servers, watchers and long builds set background=true, then check with job_output.",
      {"command": {"type": "string", "description": "PowerShell command line"},
       "background": {"type": "boolean", "description": "start it as a background job and return at once"},
       "timeout": {"type": "integer", "description": f"seconds to wait (default {TIMEOUT}, max {MAX_TIMEOUT})"},
       "required": ["command"]},
      kit="terminal")
async def run_command(args: dict, ctx) -> ToolResult:
    command = str(args.get("command") or "").strip()
    if not command:
        return ToolResult(False, "Give me a command to run.")
    if not shell():
        return ToolResult(False, "PowerShell isn't available on this computer.")
    cwd = here(ctx.chat_id)
    refused = await _allowed(command, cwd, ctx)
    if refused:
        return refused
    if args.get("background"):
        return start_job(command, cwd, ctx.chat_id)

    timeout = min(max(int(args.get("timeout") or TIMEOUT), 1), MAX_TIMEOUT)
    code, stdout, stderr, new_cwd = await run(command, cwd, timeout)
    if new_cwd and new_cwd.is_dir():
        _cwd[ctx.chat_id] = new_cwd
    data = {"exit_code": code, "cwd": str(here(ctx.chat_id)), "stdout": _tail(stdout), "stderr": _tail(stderr)}
    if code is None:
        return ToolResult(False, f"It was still running after {timeout} seconds, so I stopped it; "
                                 "run long jobs with background=true.", data)
    lines = len(stdout.splitlines()) + len(stderr.splitlines())
    said = f"{lines} line{'s' if lines != 1 else ''} of output" if lines else "no output"
    return ToolResult(code == 0, f"Ran it in {cwd}: exit code {code}, {said}.", data)


def start_job(command: str, cwd: Path, chat_id: str) -> ToolResult:
    folder = config.workspace() / "jobs"
    folder.mkdir(parents=True, exist_ok=True)
    job_id = "job-" + secrets.token_hex(3)
    log = folder / f"{job_id}.log"
    with open(log, "wb") as fh:
        proc = subprocess.Popen(_argv(command, cwd), stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.STDOUT,
                                cwd=cwd, creationflags=_NO_WINDOW | _NEW_GROUP)
    _jobs[job_id] = Job(job_id, chat_id, command, proc, log, time.time())
    return ToolResult(True, f"Started {job_id} in the background in {cwd}.", {"job": job_id, "pid": proc.pid})


def _job_state(job: Job) -> str:
    code = job.proc.poll()
    return "running" if code is None else f"finished with exit code {code}"


def _job_tail(job: Job) -> str:
    try:
        text = job.log.read_bytes().decode("utf-8", "replace").replace("\r\n", "\n")
    except OSError:
        return ""
    lines = [ln for ln in text.split("\n") if not ln.startswith(_MARK)]
    return _tail("\n".join(lines[-TAIL_LINES:]).strip("\n"))


@tool("job_output", "See this chat's background jobs, or one job's status and latest output.",
      {"job": {"type": "string", "description": "job id from run_command; leave out to list jobs"}},
      kit="terminal")
async def job_output(args: dict, ctx) -> ToolResult:
    job_id = str(args.get("job") or "").strip()
    if not job_id:
        mine = [j for j in _jobs.values() if j.chat_id == ctx.chat_id]
        if not mine:
            return ToolResult(True, "There are no background jobs in this chat.")
        listed = [{"job": j.id, "command": j.command, "state": _job_state(j)} for j in mine]
        return ToolResult(True, f"{len(mine)} background job{'s' if len(mine) != 1 else ''} in this chat.",
                          {"jobs": listed})
    job = _jobs.get(job_id)
    if job is None:
        return ToolResult(False, f"There is no job called {job_id}.")
    return ToolResult(True, f"{job.id} is {_job_state(job)}.",
                      {"job": job.id, "command": job.command, "output": _job_tail(job)})


@tool("stop_job", "Stop a background job (and everything it started).",
      {"job": {"type": "string"}, "required": ["job"]}, kit="terminal")
async def stop_job(args: dict, ctx) -> ToolResult:
    job = _jobs.get(str(args.get("job") or "").strip())
    if job is None:
        return ToolResult(False, "There is no job with that id.")
    if job.proc.poll() is not None:
        return ToolResult(True, f"{job.id} had already {_job_state(job)}.")
    await asyncio.to_thread(_kill_tree, job.proc.pid)
    await asyncio.to_thread(job.proc.wait, 10)
    return ToolResult(True, f"Stopped {job.id}.", {"output": _job_tail(job)})
