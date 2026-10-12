"""Final-pass repro: with "close notepad without saving" in a DM's history, the same "open notepad and type ..." made
Desk close Notepad again. Earlier person messages now reach the model marked as handled; only the newest is plain,
except the request a "try again" points back to."""

from fakes import make_crew

from teamloop.crew import team


def _users(history):
    return [m["content"] for m in history if m["role"] == "user"]


def test_only_the_newest_person_message_is_unmarked(tmp_path):
    crew = make_crew(tmp_path, [])
    for text in ("open notepad and type hello", "close notepad without saving", "open notepad and type hello"):
        crew.store.add_message("dm-desk", "user", text)
        crew.store.add_message("dm-desk", "desk", "Done.")
    crew.store.add_message("dm-desk", "user", "open notepad and type hello")   # the message being answered
    users = _users(crew.history("dm-desk", "desk"))
    assert users and all(u.startswith(team.EARLIER) for u in users)
    assert team.EARLIER + "close notepad without saving" in users


def test_try_again_keeps_the_request_it_points_to(tmp_path):
    crew = make_crew(tmp_path, [])
    crew.store.add_message("dm-s", "user", "write a note called x on the Desktop")
    crew.store.add_message("dm-s", "s", 'Not done: save the file (no tool ran for it). Say "try again" and I\'ll do it.')
    crew.store.add_message("dm-s", "user", "try again")
    users = _users(crew.history("dm-s", "s"))
    assert users == ["write a note called x on the Desktop"]


async def test_the_model_sees_the_marks(tmp_path):
    crew = make_crew(tmp_path, ["Opened Notepad.", "Typed it."])
    crew.store.add_message("dm-desk", "user", "close notepad without saving")
    crew.store.add_message("dm-desk", "desk", "Closed it without saving.")
    await crew.post("dm-desk", "open notepad and type hello")
    await crew.wait_idle("dm-desk")
    sent = crew.router.calls[0]["messages"]
    plain = [m["content"] for m in sent if m["role"] == "user" and not m["content"].startswith(team.EARLIER)]
    assert plain == ["open notepad and type hello"]
