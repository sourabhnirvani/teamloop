import asyncio
import time

from fakes import make_crew

from teamloop.server.telegram import Bridge

OWNER = "555"


class FakeTelegram:
    """Stands in for httpx: records every Bot API call, never touches the network."""

    def __init__(self):
        self.sent = []

    async def post(self, url, json=None, data=None, files=None):
        self.sent.append((url.rsplit("/", 1)[-1], json or data))
        return _Res()

    def texts(self):
        return [p["text"] for m, p in self.sent if m == "sendMessage"]


class _Res:
    def json(self):
        return {"ok": True, "result": True}


def text_update(text, sender=OWNER, age=0):
    return {"update_id": 1, "message": {"chat": {"id": int(sender)}, "text": text, "date": time.time() - age}}


async def started(tmp_path, script, owner=OWNER):
    crew = make_crew(tmp_path, script)
    tg = FakeTelegram()
    bridge = Bridge(crew, "TOKEN", [owner] if owner else [], tg)
    task = asyncio.create_task(bridge.forward())
    await asyncio.sleep(0)
    return crew, tg, bridge, task


async def settle():
    for _ in range(5):
        await asyncio.sleep(0)


async def test_owner_message_reaches_crew_and_reply_comes_back(tmp_path):
    crew, tg, bridge, task = await started(tmp_path, ["Hi from S."])
    await bridge.handle(text_update("hello"))
    await crew.wait_idle("team")
    await settle()
    task.cancel()
    assert [m["text"] for m in crew.store.messages("team")] == ["hello", "Hi from S."]
    assert any(t.endswith("S: Hi from S.") for t in tg.texts())
    assert not any("hello" in t for t in tg.texts())  # the person's own words are not echoed back


async def test_every_allowed_person_can_talk_and_hears_replies(tmp_path):
    crew, tg, bridge, task = await started(tmp_path, ["On it."])
    bridge.owners.append("666")
    await bridge.handle(text_update("hello", sender="666"))
    await crew.wait_idle("team")
    await settle()
    task.cancel()
    assert [m["text"] for m in crew.store.messages("team")] == ["hello", "On it."]
    assert sorted(p["chat_id"] for m, p in tg.sent if m == "sendMessage") == ["555", "666"]


async def test_strangers_and_old_messages_are_ignored(tmp_path):
    crew, tg, bridge, task = await started(tmp_path, [])
    await bridge.handle(text_update("open calculator", sender="999"))
    await bridge.handle(text_update("open calculator", age=600))
    task.cancel()
    assert crew.store.messages("team") == []
    assert tg.sent == []


async def test_without_owner_it_only_tells_the_chat_id(tmp_path):
    crew, tg, bridge, task = await started(tmp_path, [], owner=None)
    await bridge.handle(text_update("hi", sender="777"))
    task.cancel()
    assert crew.store.messages("team") == []
    assert tg.texts() == ["Set TELEGRAM_CHAT_ID=777 in .env and restart TeamLoop."]


async def test_approval_card_buttons_answer_the_gate(tmp_path):
    crew, tg, bridge, task = await started(tmp_path, [])
    asked = asyncio.create_task(crew.gate.ask("team", "desk", "Close Notepad", "It has unsaved work."))
    await settle()
    method, card = tg.sent[-1]
    assert method == "sendMessage" and "Close Notepad" in card["text"]
    approve = card["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    await bridge.handle({"update_id": 2, "callback_query": {
        "id": "q1", "from": {"id": int(OWNER)}, "data": approve,
        "message": {"chat": {"id": int(OWNER)}, "message_id": 9}}})
    assert await asked is True
    task.cancel()
    assert [m for m, _ in tg.sent][-2:] == ["answerCallbackQuery", "editMessageReplyMarkup"]


async def test_stranger_cannot_press_approve(tmp_path):
    crew, tg, bridge, task = await started(tmp_path, [])
    crew.gate.timeout = 0.05
    asked = asyncio.create_task(crew.gate.ask("team", "desk", "Shut down", "Now."))
    await settle()
    approve = tg.sent[-1][1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    await bridge.handle({"update_id": 2, "callback_query": {"id": "q1", "from": {"id": 999}, "data": approve}})
    assert await asked is False
    task.cancel()


async def test_chat_command_switches_to_one_bot(tmp_path):
    crew, tg, bridge, task = await started(tmp_path, ["Scout here."])
    await bridge.handle(text_update("/chat scout"))
    assert bridge.chat == "dm-scout"
    await bridge.handle(text_update("find X"))
    await crew.wait_idle("dm-scout")
    await settle()
    task.cancel()
    assert crew.store.messages("team") == []
    assert any("Scout here." in t for t in tg.texts())
