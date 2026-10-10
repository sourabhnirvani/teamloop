"""Telegram bridge: talk to the crew from your phone. Only the one owner chat is listened to,
because this bot can drive the laptop. Runs in-process next to the server (long polling, no webhook)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time

import httpx

from teamloop import config
from teamloop.crew.bots import BOTS

log = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/{method}"
POLL_SECONDS = 30
MAX_AGE = 120  # messages sent while the server was off are dropped, not run late
LIMIT = 4000   # Telegram allows 4096 characters per message
HELP = ("Talk to the crew here. /chat to see chats, /chat scout to talk to one bot, "
        "/chat team to go back, /stop to stop the work.")


class Bridge:
    def __init__(self, crew, token: str, owner: str | None, client: httpx.AsyncClient):
        self.crew, self.token, self.owner, self.client = crew, token, owner, client
        self.chat = "team"
        self.offset = 0

    async def call(self, method: str, files: dict | None = None, **params) -> object:
        url = API.format(token=self.token, method=method)
        if files:
            res = await self.client.post(url, data={k: str(v) for k, v in params.items()}, files=files)
        else:
            res = await self.client.post(url, json=params)
        body = res.json()
        if not body.get("ok"):
            raise RuntimeError(f"Telegram {method} failed: {body.get('description')}")
        return body["result"]

    async def run(self) -> None:
        await asyncio.gather(self.poll(), self.forward())

    # ---- Telegram -> crew ---------------------------------------------------------------------
    async def poll(self) -> None:
        while True:
            try:
                updates = await self.call("getUpdates", offset=self.offset, timeout=POLL_SECONDS,
                                          allowed_updates=["message", "callback_query"])
            except (httpx.HTTPError, RuntimeError, ValueError) as e:
                log.warning("telegram poll failed: %s", e)
                await asyncio.sleep(5)
                continue
            for update in updates:
                self.offset = update["update_id"] + 1
                try:
                    await self.handle(update)
                except Exception:
                    log.exception("telegram update failed")

    async def handle(self, update: dict) -> None:
        if "callback_query" in update:
            return await self.on_button(update["callback_query"])
        msg = update.get("message") or {}
        sender, text = str(msg.get("chat", {}).get("id", "")), (msg.get("text") or "").strip()
        if not sender or not text:
            return
        if not self.owner:  # first run: tell the person their chat id so they can lock the bot to it
            await self.send(sender, f"Set TELEGRAM_CHAT_ID={sender} in .env and restart TeamLoop.")
            return
        if sender != self.owner or time.time() - msg.get("date", 0) > MAX_AGE:
            return
        if text.startswith("/"):
            return await self.command(text)
        await self.crew.post(self.chat, text)

    async def command(self, text: str) -> None:
        name, _, arg = text[1:].partition(" ")
        name, arg = name.split("@")[0].lower(), arg.strip().lower()
        if name == "stop":
            await self.crew.post(self.chat, "stop")
        elif name == "chat" and arg:
            chat = next((c for c in self.crew.store.chats()
                         if arg in (c["id"], c["title"].lower(), f"dm-{arg}")), None)
            if chat is None:
                await self.send(self.owner, f"No chat called {arg}.")
            else:
                self.chat = chat["id"]
                await self.send(self.owner, f"Now talking in {chat['title']}.")
        elif name == "chat":
            titles = ", ".join(c["title"] for c in self.crew.store.chats())
            await self.send(self.owner, f"Chats: {titles}.")
        else:
            await self.send(self.owner, HELP)

    async def on_button(self, query: dict) -> None:
        if str(query.get("from", {}).get("id", "")) != self.owner:
            return
        verdict, _, approval_id = (query.get("data") or "").partition(":")
        taken = self.crew.gate.answer(approval_id, verdict == "ok")
        note = ("Approved." if verdict == "ok" else "Denied.") if taken else "That card already closed."
        await self.call("answerCallbackQuery", callback_query_id=query["id"], text=note)
        message = query.get("message") or {}
        if message:
            await self.call("editMessageReplyMarkup", chat_id=message["chat"]["id"],
                            message_id=message["message_id"], reply_markup={"inline_keyboard": []})

    # ---- crew -> Telegram ---------------------------------------------------------------------
    async def forward(self) -> None:
        with self.crew.bus.subscribe() as queue:
            while True:
                event = await queue.get()
                if not self.owner:
                    continue
                try:
                    await self.deliver(event)
                except (httpx.HTTPError, RuntimeError, ValueError, OSError) as e:
                    log.warning("telegram send failed: %s", e)

    async def deliver(self, event: dict) -> None:
        kind = event["type"]
        if kind == "approval":  # cards from any chat: a routine may need an answer too
            await self.send_card(event)
        elif event.get("chat_id") != self.chat:
            return
        elif kind == "message" and event["message"]["sender"] != "user":
            await self.send(self.owner, f"{_name(event['message']['sender'])}: {event['message']['text']}")
        elif kind == "typing" and event.get("on"):
            await self.call("sendChatAction", chat_id=self.owner, action="typing")

    async def send_card(self, event: dict) -> None:
        text = f"{_name(event['bot'])} asks: {event['title']}\n{event['details']}"[:1000]
        buttons = {"inline_keyboard": [[{"text": "Approve", "callback_data": f"ok:{event['id']}"},
                                        {"text": "Deny", "callback_data": f"no:{event['id']}"}]]}
        shot = config.workspace() / "shots" / (event.get("screenshot") or "").rsplit("/", 1)[-1]
        if event.get("screenshot") and shot.is_file():
            await self.call("sendPhoto", files={"photo": (shot.name, shot.read_bytes(), "image/png")},
                            chat_id=self.owner, caption=text, reply_markup=json.dumps(buttons))
        else:
            await self.call("sendMessage", chat_id=self.owner, text=text, reply_markup=buttons)

    async def send(self, chat_id: str, text: str) -> None:
        for start in range(0, len(text), LIMIT):
            await self.call("sendMessage", chat_id=chat_id, text=text[start:start + LIMIT])


def _name(bot_id: str) -> str:
    bot = BOTS.get(bot_id)
    return f"{bot.emoji} {bot.name}" if bot else bot_id


async def run(crew) -> None:
    """Start the bridge when TELEGRAM_TOKEN is set; TELEGRAM_CHAT_ID locks it to one person."""
    token = os.environ.get("TELEGRAM_TOKEN", "").strip()
    if not token:
        return
    owner = os.environ.get("TELEGRAM_CHAT_ID", "").strip() or None
    if not owner:
        log.warning("TELEGRAM_CHAT_ID is not set: the bot only replies with your chat id until it is")
    async with httpx.AsyncClient(timeout=POLL_SECONDS + 10) as client:
        await Bridge(crew, token, owner, client).run()
