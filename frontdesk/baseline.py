"""A keyword baseline with no model: the kind of first version the gate exists to stop.

It turns every request into a housekeeping or engineering task for the calling room,
never hands a call to a person, and never captures a sales lead.
"""

from __future__ import annotations

import re

BROKEN = ("not working", "isn't", "broken", "leak", "water", "warm", "noise", "remote", "air")


def keyword_agent(case_input: dict) -> dict:
    text = case_input["transcript"].lower()
    m = re.search(r"room (\d{3})", case_input["line"]) or re.search(r"room (\d{3})", text)
    room = m.group(1) if m else None
    department = "engineering" if any(k in text for k in BROKEN) else "housekeeping"
    question = text.rstrip().endswith("?") and not text.startswith(("can", "could"))
    task = None
    if not question:
        task = {"department": department, "room": room, "request": case_input["transcript"], "priority": "normal"}
    return {
        "reply": "Thanks for calling. We'll take care of that for you right away.",
        "task": task,
        "handoff": {"now": False, "reason": None},
        "lead": None,
        "review_flag": False,
    }
