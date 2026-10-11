import asyncio

from fakes import call, make_crew

from teamloop.tools import registry
from teamloop.tools.registry import ToolResult


def install_risky(monkeypatch):
    async def risky(args, ctx):
        if not await ctx.approve("Run a command", "Remove-Item test.txt\n\nin C:\\Users\\me"):
            return ToolResult(False, "The person said no, so I didn't run it: Remove-Item test.txt")
        return ToolResult(True, "Deleted test.txt.")

    monkeypatch.setitem(registry.REGISTRY, "risky", registry.Tool("risky", "", {"type": "object"}, "memory", risky))


def answer_cards(crew, answers, asked):
    async def run():
        with crew.bus.subscribe() as queue:
            while True:
                e = await queue.get()
                if e["type"] == "approval":
                    asked.append(e["title"])
                    crew.gate.answer(e["id"], answers.pop(0))
    return asyncio.create_task(run())


def tool_texts(crew):
    return [m["content"] for c in crew.router.calls for m in c["messages"] if m["role"] == "tool"]


async def test_a_no_is_not_asked_again_until_the_person_says_so(tmp_path, monkeypatch):
    install_risky(monkeypatch)
    crew = make_crew(tmp_path, [call("risky"), "Okay, I left it.",       # 1: asked, denied
                                call("risky"), "Left it alone.",         # 2: an unrelated message brings it back
                                call("risky"), "Deleted."])              # 3: after "ask me again"
    asked = []
    answering = answer_cards(crew, [False, True], asked)
    await asyncio.sleep(0)
    for text in ("delete test.txt", "now open the file please"):
        await crew.post("dm-desk", text)
        await crew.wait_idle("dm-desk")
    assert asked == ["Run a command"]  # the second time, no card at all
    assert "already said no" in tool_texts(crew)[-1]

    await crew.post("dm-desk", "ask me again")
    await crew.wait_idle("dm-desk")
    assert crew.store.messages("dm-desk")[-1]["text"].startswith("Okay: the next time")
    await crew.post("dm-desk", "go on, delete it")
    await crew.wait_idle("dm-desk")
    answering.cancel()
    assert asked == ["Run a command", "Run a command"] and tool_texts(crew)[-1] == "OK: Deleted test.txt."


async def test_no_answer_counts_as_a_no_for_the_rest_of_the_job(tmp_path, monkeypatch):
    """Yang's debug pass row 11: the card expired and Desk at once re-ran the command and raised a second card."""
    install_risky(monkeypatch)
    crew = make_crew(tmp_path, [call("risky"), call("risky"), "It's waiting for your OK.",  # one job, tried twice
                                call("risky"), "Asked again."])                             # a new message
    crew.gate.timeout = 0.05
    asked = []
    with crew.bus.subscribe() as queue:
        for _ in range(2):
            await crew.post("dm-desk", "delete test.txt")
            await crew.wait_idle("dm-desk")
        while not queue.empty():
            e = queue.get_nowait()
            if e["type"] == "approval":
                asked.append(e["id"])
    texts = list(dict.fromkeys(tool_texts(crew)))  # each model call re-sends earlier tool results
    assert texts[0].startswith("FAILED: No one answered the approval card in time, so it counts as a no")
    assert "not asked again" in texts[1]
    assert len(asked) == 2  # one card per message: the retry in the same job didn't ask again; the new message did


async def test_stop_is_not_remembered_as_a_no(tmp_path, monkeypatch):
    install_risky(monkeypatch)
    crew = make_crew(tmp_path, [call("risky")])
    await crew.post("dm-desk", "delete test.txt")
    for _ in range(50):
        if crew.gate.pending_in("dm-desk"):
            break
        await asyncio.sleep(0.01)
    await crew.stop("dm-desk")
    assert crew.gate._denied == {}
    await crew.wait_idle("dm-desk")
    last = crew.store.messages("dm-desk")[-1]
    assert (last["text"], last["kind"]) == ("Stopped.", "stopped")  # the UI shows it plainly, no cheer
