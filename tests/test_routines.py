from datetime import datetime

import pytest
from fakes import make_crew

from teamloop.crew import routines

SAT_2030 = datetime(2026, 10, 10, 20, 30)  # a Saturday


@pytest.mark.parametrize("schedule,expected", [
    ("every day at 9am", datetime(2026, 10, 11, 9, 0)),
    ("every monday at 9", datetime(2026, 10, 12, 9, 0)),
    ("every weekday at 18:30", datetime(2026, 10, 12, 18, 30)),
    ("every saturday at 9pm", datetime(2026, 10, 10, 21, 0)),
    ("every 2 hours", datetime(2026, 10, 10, 22, 30)),
    ("in 10 minutes", datetime(2026, 10, 10, 20, 40)),
    ("tomorrow at 8am", datetime(2026, 10, 11, 8, 0)),
    ("Every  Day  at 12am", datetime(2026, 10, 11, 0, 0)),
])
def test_schedules(schedule, expected):
    assert routines.next_run(schedule, SAT_2030) == expected


def test_bad_or_past_schedules():
    assert routines.next_run("today at 8am", SAT_2030) is None
    with pytest.raises(ValueError):
        routines.next_run("whenever you feel like it", SAT_2030)
    with pytest.raises(ValueError):
        routines.next_run("every day at 25:00", SAT_2030)


async def test_due_routine_posts_into_chat_and_reschedules(tmp_path):
    crew = make_crew(tmp_path, ["Here's your weekly report."])
    row = routines.add(crew, "dm-s", "send me the weekly report", "every monday at 9am")
    assert await routines.run_due(crew, now=row["next_run"] + 1) == 1
    await crew.wait_idle("dm-s")
    texts = [m["text"] for m in crew.store.messages("dm-s")]
    assert texts == ["⏰ Routine: send me the weekly report", "send me the weekly report", "Here's your weekly report."]
    again = routines.listing(crew, "dm-s")[0]
    assert again["next_run"] > row["next_run"] + 6 * 86400
    assert routines.cancel(crew, row["id"]) and routines.listing(crew) == []


async def test_one_off_routine_runs_once(tmp_path):
    crew = make_crew(tmp_path, ["ok"])
    row = routines.add(crew, "dm-s", "remind me to stretch", "in 5 minutes")
    await routines.run_due(crew, now=row["next_run"] + 1)
    await crew.wait_idle("dm-s")
    assert routines.listing(crew) == []
    assert await routines.run_due(crew, now=row["next_run"] + 999) == 0
