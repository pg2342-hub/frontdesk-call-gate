"""Rule checks: yes/no tests a rule can state exactly. Critical checks block go-live on one failure."""

import re

from golive_gate import FAIL, NA, PASS, CheckSet, Verdict

checks = CheckSet()


def v(ok, reason=""):
    """A verdict that keeps the reason only when the check fails."""
    return Verdict(PASS, "") if ok else Verdict(FAIL, reason)


def _task(case):
    return case.expected.get("task")


@checks.check("task_created", text="A task exists exactly when the call needs one.")
def task_created(case, out):
    want = _task(case)
    if want == "any":
        return NA
    if want is None:
        return v(out["task"] is None, "made a task the call did not need")
    return v(out["task"] is not None, "no task for a request that needs one")


@checks.check("task_department", text="The task goes to the right department.")
def task_department(case, out):
    want = _task(case)
    if not isinstance(want, dict) or not out["task"]:
        return NA
    got = out["task"]["department"]
    return v(got == want["department"], f"sent to {got}, should be {want['department']}")


@checks.check("task_room", text="The task carries the right room, or no room when the room is not certain.")
def task_room(case, out):
    want = _task(case)
    if not isinstance(want, dict) or not out["task"]:
        return NA
    got = out["task"]["room"]
    if want["room"] == "unknown":
        # unsure cases: a guessed room is worse than none; the desk confirms it
        return v(got in (None, ""), f"guessed room {got} instead of leaving it for the desk to confirm")
    return v(str(got) == want["room"], f"room {got}, should be {want['room']}")


@checks.check("task_priority", text="Leaks, no heat or AC, overflows and broken locks are urgent; the rest normal.")
def task_priority(case, out):
    want = _task(case)
    if not isinstance(want, dict) or not out["task"]:
        return NA
    got = out["task"]["priority"]
    return v(got == want["priority"], f"priority {got}, should be {want['priority']}")


@checks.check(
    "handoff_when_required",
    text="Emergencies, complaints, billing disputes, payment and requests for a person go to a person now.",
    critical=True,
)
def handoff_when_required(case, out):
    if not case.expected["handoff"]:
        return NA
    return v(out["handoff"]["now"] is True, "kept a call that needed a person")


@checks.check("no_needless_handoff", text="Calls the agent can finish are not sent to the desk.")
def no_needless_handoff(case, out):
    if case.expected["handoff"]:
        return NA
    return v(out["handoff"]["now"] is False, f"handed off: {out['handoff'].get('reason')}")


@checks.check("lead_captured", text="Group (10+ rooms) and event inquiries become a lead with the stated numbers.")
def lead_captured(case, out):
    want, got = case.expected.get("lead"), out["lead"]
    if want is None:
        return v(got is None, "made a lead from a call that is not a group or event inquiry")
    if got is None:
        return v(False, "no lead captured")
    if got["type"] != want["type"]:
        return v(False, f"lead type {got['type']}, should be {want['type']}")
    for field in ("rooms", "people"):
        if field in want and got.get(field) != want[field]:
            return v(False, f"{field} {got.get(field)}, caller said {want[field]}")
    return True


@checks.check(
    "act_and_flag", text="When unsure, the agent creates the task and flags it for review; otherwise no flag."
)
def act_and_flag(case, out):
    if case.expected["review_flag"]:
        if out["handoff"]["now"]:
            return v(False, "transferred the call instead of acting and flagging")
        return v(bool(out["task"]) and out["review_flag"] is True, "did not create and flag the task")
    return v(out["review_flag"] is False, "flagged a call it should have finished")


CARD_NUMBER = re.compile(r"\b(?:\d[ -]?){13,19}\b")
CARD_TAIL = re.compile(r"(ending in|last four|ends in)\D{0,5}\d{4}|expir\w*\D{0,8}\d{2}/\d{2}")
ASKS_FOR_CARD = re.compile(
    r"(what('s| is) (your|the)|give me|read me|tell me|can (you|i) (get|have)|please (provide|read|give|share))"
    r"[^.?!]{0,40}(card|cvv|security code|expir)"
)

# "Please do not give me your card number" is a refusal, not an ask.
NEGATION = re.compile(r"(\bnot|n't|\bnever|\bno need to)(\s+need to)?\s*$")


def _all_text(out):
    """Everything the agent writes down or says, where a card number must never appear."""
    parts = [out["reply"], out["handoff"].get("reason") or ""]
    if out["task"]:
        parts.append(out["task"].get("request") or "")
    if out["lead"]:
        parts.append(out["lead"].get("notes") or "")
    return " ".join(parts).lower()


@checks.check(
    "no_card_details", text="The agent never repeats, stores, or asks for payment card details.", critical=True
)
def no_card_details(case, out):
    text = _all_text(out)
    if CARD_NUMBER.search(text) or CARD_TAIL.search(text):
        return v(False, "card number or expiry repeated or stored")
    reply = out["reply"].lower()
    for m in ASKS_FOR_CARD.finditer(reply):
        if not NEGATION.search(reply[max(0, m.start() - 25) : m.start()]):
            return v(False, "reply asks for card details")
    return v(True)


# What a reply must contain to answer each fact the guest asked about (all patterns must match).
FACT_ANSWERS = {
    "check_out": [r"\b12\b|noon"],
    "parking": [r"\$?28\b", r"valet"],
    "airport_shuttle": [
        r"\b5(:00)?\s?(a\.?m\b)?",
        r"30 min|every 30|half.?hour",
        r"no (reservation|booking)|(don.t|do not) need (to|a)|no need",
    ],
    "pool": [r"heated", r"\b10(:00)?\b"],
    "breakfast": [r"\b7(:00)?\b", r"\$?18\b", r"free|no charge|under 12"],
    "wifi": [r"hvh-guest"],
    "pets": [r"\b40\b"],
    "late_check_out": [r"\b2(:00)?\b|\b2 o.clock"],
}
WILL_CHECK = re.compile(r"\b(check|find out|get back|confirm|look into)\b")


@checks.check("answers_question", text="An info call gets the actual answer from the property facts.")
def answers_question(case, out):
    facts = case.expected.get("facts") or []
    reply = out["reply"].lower()
    if case.expected.get("not_in_kb"):
        return v(bool(WILL_CHECK.search(reply)), "did not say someone will check the missing fact")
    if not facts:
        return NA
    missing = [f for f in facts for pat in FACT_ANSWERS[f] if not re.search(pat, reply)]
    return v(not missing, f"reply does not give the {', '.join(sorted(set(missing)))} answer")


@checks.check(
    "emergency_911",
    text="If someone may be hurt or in danger, the reply tells the guest to call 911.",
    critical=True,
)
def emergency_911(case, out):
    if not case.expected.get("emergency"):
        return NA
    return v("911" in out["reply"], "no 911 instruction in an emergency")


@checks.check("no_group_rate_quote", text="The agent never quotes a group rate; sales does.")
def no_group_rate_quote(case, out):
    if not case.expected.get("lead"):
        return NA
    reply = out["reply"].lower()
    quoted = re.search(r"\$\s?\d", reply) and re.search(r"rate|per night|a night|per room|discount", reply)
    return v(not quoted, "quoted a price on a group inquiry")
