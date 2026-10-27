"""Walks through a flow, where a question's right answer sits, and when a flow is really "got".

Example: Claude walks Mia through "Checkout" in 6 stops, she predicts each next stop, then explains the
flow back. That walk is recorded. The flow counts as "got" only when, on a LATER day, she answers a question
about it right: right answers on the day of the walk only show that she just saw it.

The answer position comes from here, not from Claude: in a hand trial the right answer sat first three
times in a row, and the card highlights the first option, so the pattern gave answers away.
"""

from __future__ import annotations

import random
from typing import Any

NOT_WALKED, WALKED, GOT = "not walked", "walked", "got"
EXPLAIN_RESULTS = ("full", "partial", "missed", "skipped")


def pick_slot(recent: list[int], choices: int, rng: random.Random) -> int:
    """Where the right answer goes among `choices` believable options (1-based).

    Uniform, except a slot that held the right answer twice in a row is left out the third time,
    so a run like "always the first one" can't happen, by habit or by chance.
    """
    slots = list(range(1, choices + 1))
    if choices > 1 and len(recent) >= 2 and recent[-1] == recent[-2] and recent[-1] in slots:
        slots.remove(recent[-1])
    return rng.choice(slots)


def new_walk(flow: str, day: str, stops: int, asked: int, right: int, explain: str) -> dict[str, Any]:
    if explain not in EXPLAIN_RESULTS:
        raise ValueError(f"explain must be one of {EXPLAIN_RESULTS}")
    if min(stops, asked, right) < 0 or right > asked:
        raise ValueError("stops, asked and right must be 0 or more, and right can't exceed asked")
    return {"flow": flow, "date": day, "stops": stops, "asked": asked, "right": right, "explain": explain}


def flow_status(page: str, walks: list[dict[str, Any]], questions: list[dict[str, Any]]) -> str:
    """"not walked", "walked", or "got": walked, then every answer about it on the latest later day was right.

    A later miss takes a flow back from "got" to "walked" until it is answered right again.
    """
    dates = sorted(w["date"] for w in walks if w.get("flow") == page and w.get("date"))
    if not dates:
        return NOT_WALKED
    first = dates[0]
    later = [
        h for q in questions if q.get("source") == f"flow:{page}"
        for h in q.get("history", []) if h.get("date", "") > first
    ]
    if not later:
        return WALKED
    last_day = max(h["date"] for h in later)
    return GOT if all(h["result"] == "right" for h in later if h["date"] == last_day) else WALKED
