"""Two bugs from the multi-skill before/after: "page down" crashed press_keys, and Groq's default models were retired."""

import pytest

from teamloop.computer import tools, uia
from teamloop.models import providers as P

RETIRED_ON_GROQ = {"llama-3.3-70b-versatile", "llama-3.1-8b-instant"}  # 404 from Groq on 12 Oct 2026


@pytest.mark.parametrize("keys, code", [
    ("page down", "{PGDN}"), ("page_down", "{PGDN}"), ("PageDown", "{PGDN}"), ("pgdown", "{PGDN}"),
    ("pgdn", "{PGDN}"), ("pg up", "{PGUP}"), ("Page-Up", "{PGUP}"), ("ctrl+page down", "^{PGDN}"),
    ("up arrow", "{UP}"), ("spacebar", "{SPACE}"), ("Escape", "{ESC}"), ("f5", "{F5}"), ("ctrl+s", "^s"),
])
def test_key_spellings_map_to_codes_pywinauto_knows(keys, code):
    assert uia.keys_to_sendkeys(keys) == code
    assert uia.unknown_key(keys) is None


async def test_an_unknown_key_is_a_plain_answer_not_a_crash():
    result = await tools.press_keys({"keys": "hyperdrive"}, None)
    assert not result.ok and result.text.startswith('I don\'t know the key "HYPERDRIVE"')


def test_groq_defaults_are_models_groq_still_serves():
    groq = P.PROVIDERS["groq"]
    assert groq.models and not set(groq.models) & RETIRED_ON_GROQ
    assert groq.models[0] == "openai/gpt-oss-120b"
