"""Talk to the crew from a terminal, no server needed.

    python -m teamloop.cli "what apps are open"     one task, then exit
    python -m teamloop.cli                          chat until you type "exit"
    python -m teamloop.cli --chat dm-desk "..."     talk to one bot (default: the Team chat, S leads)

Same crew, chats, keys and tracing as the server. Approval cards are asked right here (y/N).
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import sys
from typing import Any, Callable

from teamloop import kits, trace
from teamloop.crew.bots import BOTS

QUIT = {"exit", "quit", "bye", ":q"}


def _name(bot_id: str) -> str:
    bot = BOTS.get(bot_id)
    return f"{bot.emoji} {bot.name}" if bot else bot_id


async def _show(crew: Any, chat_id: str, queue: asyncio.Queue, ask: Callable[[str], str], out: Callable) -> None:
    while True:
        e = await queue.get()
        if e["type"] == "approval":  # cards from any chat: a routine may need an answer too
            prompt = f"  ? {_name(e['bot'])} asks: {e['title']}\n    {e['details']}\n    Approve? [y/N] "
            answer = await asyncio.to_thread(ask, prompt)
            crew.gate.answer(e["id"], answer.strip().lower() in ("y", "yes", "ok", "haan", "ha"))
        elif e.get("chat_id") != chat_id:
            continue
        elif e["type"] == "message" and e["message"]["sender"] != "user":
            out(f"{_name(e['message']['sender'])}: {e['message']['text']}")
        elif e["type"] == "step" and e.get("status") == "start":
            out(f"  · {_name(e['bot'])} → {e['tool']}")
        elif e["type"] == "step" and e.get("status") == "fail":
            out(f"  ✗ {e['tool']}: {e.get('text', '')}")


async def run(text: str | None, chat_id: str = "team", crew: Any = None,
              ask: Callable[[str], str] = input, out: Callable = print) -> int:
    if crew is None:
        from teamloop.keys import vault
        from teamloop.server.app import build_crew

        kits.load_all()
        with contextlib.suppress(OSError, ValueError):
            vault.export_to_env()
        trace.init()
        crew = build_crew()
    if crew.store.get_chat(chat_id) is None:
        out(f"There's no chat called {chat_id}. Chats: {', '.join(c['id'] for c in crew.store.chats())}.")
        return 2
    with crew.bus.subscribe() as queue:
        shower = asyncio.create_task(_show(crew, chat_id, queue, ask, out))
        try:
            if text:
                await crew.post(chat_id, text)
                await crew.wait_idle(chat_id)
            else:
                out('Talking to the crew. Type "exit" to leave, "stop" to stop the work.')
                while True:
                    line = (await asyncio.to_thread(ask, "you> ")).strip()
                    if line.lower() in QUIT:
                        break
                    if line:
                        await crew.post(chat_id, line)
                        await crew.wait_idle(chat_id)
            await asyncio.sleep(0.05)  # let the last events print
        except (EOFError, KeyboardInterrupt):
            await crew.stop(chat_id)
        finally:
            shower.cancel()
            trace.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m teamloop.cli", description="Talk to the TeamLoop crew.")
    parser.add_argument("task", nargs="*", help="what to do; leave out to chat")
    parser.add_argument("--chat", default="team", help="chat id: team (default), dm-s, dm-desk, dm-web, ...")
    args = parser.parse_args(argv)
    with contextlib.suppress(AttributeError):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # bot emoji on any console
    logging.basicConfig(level=logging.WARNING)
    return asyncio.run(run(" ".join(args.task) or None, args.chat))


if __name__ == "__main__":
    sys.exit(main())
