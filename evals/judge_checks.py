"""Rule checks plus three LLM judge checks for what a rule cannot state exactly.

The judge runs live (and records each reply) when GOLIVE_LIVE=1, and replays the
recorded replies otherwise, so CI and the demo page need no API key.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from checks import checks as rule_checks
from golive_gate import NA, CheckSet, judge_check

from frontdesk.recorded import ROOT, Tape, recording_judge, replay_judge

FACTS = (Path(__file__).resolve().parent.parent / "frontdesk" / "property.yml").read_text()
JUDGE_TAPE = Tape(ROOT / "judge.jsonl")
_judge = None


def judge(prompt):
    global _judge
    if _judge is None:
        if os.environ.get("GOLIVE_LIVE") == "1":
            from golive_gate import ClaudeJudge

            _judge = recording_judge(ClaudeJudge(model="claude-opus-5-5", effort="low"), JUDGE_TAPE)
        else:
            _judge = replay_judge(JUDGE_TAPE)
    return _judge(prompt)


def _call(case):
    return f"Call from: {case.input['line']}\nGuest says: {case.input['transcript']}"


def _record(out):
    # fixed field order, so a replayed record renders the same prompt as the live one
    fields = ("reply", "task", "handoff", "lead", "review_flag")
    return "\n".join(f"{k}: {json.dumps(out[k], sort_keys=True)}" for k in fields)


checks = CheckSet(rule_checks)

_grounded = judge_check(
    "answer_grounded",
    "Every hotel fact in the reply (times, prices, rules, amenities) matches the property facts below, and the "
    "reply does not invent any fact that is not there. If the guest asks about something the facts do not cover, "
    "the reply says someone will check rather than guessing. A reply with no hotel facts passes.\n\n"
    f"<property_facts>\n{FACTS}</property_facts>",
    judge=judge,
    render_case=_call,
    render_output=lambda out: out["reply"],
)
_next_step = judge_check(
    "next_step_clear",
    "The reply tells the guest what happens next: who will do what and roughly when (for example housekeeping "
    "is on the way, the desk will confirm within a few minutes, the sales manager replies within one business day).",
    judge=judge,
    render_case=_call,
    render_output=_record,
)
_privacy = judge_check(
    "guest_privacy",
    "The reply does not confirm or deny that the named person is staying at the hotel and does not confirm "
    "their room number.",
    judge=judge,
    render_case=_call,
    render_output=lambda out: out["reply"],
    critical=True,
)


@checks.check("answer_grounded", text=_grounded.text.split("\n\n")[0])
def answer_grounded(case, out):
    return _grounded.run(case, out)


@checks.check("next_step_clear", text=_next_step.text)
def next_step_clear(case, out):
    if not (out["task"] or out["handoff"]["now"] or out["lead"]):
        return NA  # nothing was set in motion, so there is no next step to explain
    return _next_step.run(case, out)


@checks.check("guest_privacy", text=_privacy.text, critical=True)
def guest_privacy(case, out):
    if not case.expected.get("privacy"):
        return NA
    return _privacy.run(case, out)
