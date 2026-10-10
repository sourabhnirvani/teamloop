"""neatlogs spans, captured in memory in a separate process (nothing is sent anywhere)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("neatlogs")

ROOT = Path(__file__).resolve().parent.parent

SCRIPT = r"""
import asyncio, json, os, sys
sys.path[:0] = [sys.argv[1], sys.argv[2]]
os.environ.pop("TEAMLOOP_TRACE", None)
os.environ["TEAMLOOP_WORKSPACE"] = sys.argv[3]
os.environ["GROQ_API_KEY"] = "gsk_" + "s" * 40
import neatlogs
from neatlogs.core.telemetry_v2 import InMemoryDiagnosticSpanExporter
exporter = InMemoryDiagnosticSpanExporter()
neatlogs.init(api_key="local-test", endpoint="http://127.0.0.1:9", workflow_name="test",
              register_shutdown_handlers=False, instrumentations=[], _doctor_probe_exporter=exporter)
from teamloop import trace
trace._neat = neatlogs
from fakes import call, make_crew
from pathlib import Path

async def main():
    crew = make_crew(Path(sys.argv[3]), [call("remember", fact="likes tea, key gsk_" + "s" * 40), "Noted."])
    await crew.post("dm-s", "remember that I like tea")
    await crew.wait_idle("dm-s")

asyncio.run(main())
neatlogs.flush(3000)
out = []
for env in exporter.get_finished_envelopes():
    attrs = env.attributes if isinstance(env.attributes, dict) else {}
    out.append({"name": env.name, "kind": env.kind, "id": env.span_id, "parent": env.parent_span_id,
                "internal": attrs.get("neatlogs.internal"), "input": attrs.get("input.value"),
                "output": attrs.get("output.value")})
print("SPANS=" + json.dumps(out))
"""


def test_turns_and_tools_are_visible_spans_with_inputs_and_outputs(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "TEAMLOOP_TRACE"}
    done = subprocess.run([sys.executable, "-c", SCRIPT, str(ROOT), str(ROOT / "tests"), str(tmp_path)],
                          capture_output=True, text=True, timeout=120, env=env, encoding="utf-8")
    line = next((ln for ln in done.stdout.splitlines() if ln.startswith("SPANS=")), None)
    assert line, done.stderr[-2000:]
    spans = {s["name"]: s for s in json.loads(line[len("SPANS="):])}

    flow, turn, tool = spans["chat message"], spans["S turn"], spans["remember"]
    assert (flow["kind"], turn["kind"], tool["kind"]) == ("WORKFLOW", "AGENT", "TOOL")
    assert turn["parent"] == flow["id"] and tool["parent"] == turn["id"]
    assert flow["internal"] is False and turn["internal"] is False and tool["internal"] is False
    assert flow["input"] == "remember that I like tea" and turn["output"] == "Noted."
    assert "likes tea" in tool["input"] and tool["output"].startswith("OK: ")
    assert "gsk_" not in json.dumps(spans)  # keys are hidden before they reach neatlogs
