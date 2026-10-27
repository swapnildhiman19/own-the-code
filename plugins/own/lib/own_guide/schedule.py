"""When a quiz question comes back.

Missed (or "not sure")  -> back in 1 day, then 3, 7 and 21 days while it keeps being
                           right; a miss anywhere restarts at 1 day.
Right the first time    -> back once, ~14 days later ("still remember?"); right again -> done.
Right at the 21-day step -> done ("got it").

Only what a question tests and its correct answer are stored, never the exact wording:
every return is asked in new words, so recalling "it was option A" doesn't work.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

LADDER = [1, 3, 7, 21]
CHECK_GAP = 14
RESULTS = ("right", "miss", "not-sure")


def _iso(day: dt.date) -> str:
    return day.isoformat()


def new_question(qid: int, today: dt.date, **fields: Any) -> dict[str, Any]:
    question = {
        "id": f"q{qid}",
        "kind": fields.get("kind", "trace"),
        "tests": fields.get("tests", ""),
        "answer": fields.get("answer", ""),
        "links": list(fields.get("links") or []),
        "source": fields.get("source", ""),
        "feature": fields.get("feature", ""),
        "created": _iso(today),
        "status": "new",
        "step": None,
        "next_due": None,
        "misses": 0,
        "history": [],
    }
    return question


def apply_result(question: dict[str, Any], result: str, today: dt.date) -> dict[str, Any]:
    """Record one answer and move the question along its ladder."""
    if result not in RESULTS:
        raise ValueError(f"result must be one of {RESULTS}")
    question["history"].append({"date": _iso(today), "result": result})
    right = result == "right"
    status = question["status"]

    if not right:
        question["misses"] += 1
        question.update(status="learning", step=0, next_due=_iso(today + dt.timedelta(days=LADDER[0])))
        return question

    if status == "new":
        question.update(status="check", step=None, next_due=_iso(today + dt.timedelta(days=CHECK_GAP)))
    elif status == "check":
        question.update(status="done", step=None, next_due=None)
    elif status == "learning":
        step = question.get("step") or 0
        if step >= len(LADDER) - 1:
            question.update(status="done", step=None, next_due=None)
        else:
            step += 1
            question.update(step=step, next_due=_iso(today + dt.timedelta(days=LADDER[step])))
    return question


def due(questions: list[dict[str, Any]], today: dt.date, limit: int) -> list[dict[str, Any]]:
    """Questions due now: oldest first, then the most-missed. At most `limit`."""
    waiting = [
        q for q in questions
        if q["status"] in ("learning", "check") and q["next_due"] and q["next_due"] <= _iso(today)
    ]
    waiting.sort(key=lambda q: (q["next_due"], -q["misses"], q["id"]))
    return waiting[:limit]


def due_count(questions: list[dict[str, Any]], today: dt.date) -> int:
    return len(due(questions, today, limit=10**6))


def upcoming(questions: list[dict[str, Any]], today: dt.date, limit: int = 5) -> list[dict[str, Any]]:
    """The next returns after today, soonest first."""
    later = [q for q in questions if q["status"] in ("learning", "check") and q["next_due"] and q["next_due"] > _iso(today)]
    later.sort(key=lambda q: (q["next_due"], q["id"]))
    return later[:limit]


def is_solid(question: dict[str, Any]) -> bool:
    """Answered right the last time it was asked."""
    return bool(question["history"]) and question["history"][-1]["result"] == "right"
