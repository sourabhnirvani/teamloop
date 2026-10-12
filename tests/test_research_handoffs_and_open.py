"""Final-pass demo run 1: S sent Scout and Web back 7 times for a detail nobody asked for and never saved, opened or
set the reminder; and Web's browser_open (reading an article) counted as "open it"."""

import asyncio

from fakes import make_crew

from teamloop.crew import coverage, team
from teamloop.crew.context import TurnCtx

GOAL = ("Research the top 3 free LLM APIs for students, write a short report on the Desktop, open it, and remind me "
        "about it every Monday.")


async def test_a_third_research_handoff_is_refused_and_others_are_not(tmp_path):
    crew = make_crew(tmp_path, ["Found three.", "More details.", "Saved Desktop/r.md.", "Opened it."])
    job = TurnCtx("team", "s", crew, asyncio.Event())
    first = await crew.delegate(job, "scout", "Find the top 3 free LLM APIs with links")
    second = await crew.delegate(job, "web", "Read their pricing pages")
    third = await crew.delegate(job, "scout", "Find more details about the third one")
    assert first.ok and second.ok
    assert not third.ok and third.text == team.ENOUGH_RESEARCH
    assert (await crew.delegate(job, "writer", "Save Desktop/r.md with the report")).ok   # not research: fine
    assert (await crew.delegate(job, "desk", "Open Desktop/r.md")).ok
    assert job.handoffs == ["scout", "web", "writer", "desk"]


async def test_a_new_job_gets_a_fresh_research_budget(tmp_path):
    crew = make_crew(tmp_path, ["a", "b", "c"])
    first_job = TurnCtx("team", "s", crew, asyncio.Event())
    await crew.delegate(first_job, "scout", "x")
    await crew.delegate(first_job, "scout", "y")
    assert (await crew.delegate(TurnCtx("team", "s", crew, asyncio.Event()), "scout", "z")).ok


def test_reading_an_article_in_the_browser_is_not_opening_the_report():
    used = {"delegate", "web_search", "browser_open", "browser_read", "write_file", "schedule_routine"}
    assert coverage.missing(GOAL, used) == ["open it"]
    assert coverage.missing(GOAL, used | {"open_file"}) == []


def test_opening_a_website_still_counts_browser_open():
    assert coverage.missing("open the neatlogs website", {"browser_open"}) == []
    assert coverage.missing("open https://neatlogs.com", {"browser_open"}) == []
