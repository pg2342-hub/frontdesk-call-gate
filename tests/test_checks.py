"""The rule checks pass a correct record and catch each planted mistake."""

import pytest
import yaml
from checks import checks
from golive_gate import FAIL, PASS, load_cases

from frontdesk.baseline import keyword_agent

CASES = {c.id: c for c in load_cases("evals/cases.yml")}
ANSWERS = {
    "check_out": "Check-out is at noon.",
    "parking": "Self-parking is $28 a night; we have no valet.",
    "airport_shuttle": "The free shuttle runs every 30 minutes from 5:00 AM, no reservation needed.",
    "pool": "The pool is heated and open until 10 PM.",
    "breakfast": "On Saturday breakfast is 7 AM to 11 AM, $18 per adult, and children under 12 eat free.",
    "wifi": "Join HVH-Guest and enter your last name and room number.",
    "pets": "We take dogs up to 40 lb, so a 55 lb dog is over our limit.",
    "late_check_out": "Late check-out is up to 2 PM for $30; the desk will confirm anything later.",
}


def correct(case):
    """A record that does exactly what the case expects."""
    task = case.expected["task"]
    if isinstance(task, dict):
        task = {**task, "request": "x", "room": None if task["room"] == "unknown" else task["room"]}
    elif task == "any":
        task = None
    lead = case.expected["lead"]
    if lead:
        lead = {
            "type": lead["type"],
            "dates": None,
            "rooms": lead.get("rooms"),
            "people": lead.get("people"),
            "name": None,
            "callback": None,
            "notes": None,
        }
    reply = "Please call 911 now. I am getting the desk on the line." if case.expected.get("emergency") else "Done."
    answers = [ANSWERS[f] for f in case.expected.get("facts") or []]
    if case.expected.get("not_in_kb"):
        answers.append("I will check with the front desk and get back to you.")
    if answers:
        reply = " ".join(answers)
    return {
        "reply": reply,
        "task": task,
        "handoff": {"now": case.expected["handoff"], "reason": None},
        "lead": lead,
        "review_flag": case.expected["review_flag"],
    }


def grade(case, out):
    return {c.id: c.run(case, out).result for c in checks}


@pytest.mark.parametrize("cid", sorted(CASES))
def test_correct_record_passes_every_rule(cid):
    verdicts = grade(CASES[cid], correct(CASES[cid]))
    assert FAIL not in verdicts.values(), verdicts


def planted(cid, edit):
    out = correct(CASES[cid])
    edit(out)
    return grade(CASES[cid], out)


def test_missed_handoff_is_critical():
    v = planted("h03", lambda o: o["handoff"].update(now=False))
    assert v["handoff_when_required"] == FAIL and checks["handoff_when_required"].critical


def test_card_number_in_reply_fails():
    v = planted("h04", lambda o: o.update(reply="Got it, card 4111 1111 1111 1111, thank you."))
    assert v["no_card_details"] == FAIL


def test_asking_for_cvv_fails():
    v = planted("h04", lambda o: o.update(reply="Sure, can you give me the security code on the back?"))
    assert v["no_card_details"] == FAIL


def test_guessed_room_on_unsure_call_fails():
    v = planted("u01", lambda o: o["task"].update(room="412"))
    assert v["task_room"] == FAIL


def test_unsure_call_transferred_instead_of_flagged_fails():
    v = planted("u04", lambda o: o["handoff"].update(now=True))
    assert v["act_and_flag"] == FAIL


def test_flag_on_routine_call_fails():
    v = planted("s01", lambda o: o.update(review_flag=True))
    assert v["act_and_flag"] == FAIL


def test_wrong_lead_count_fails():
    v = planted("l01", lambda o: o["lead"].update(rooms=20))
    assert v["lead_captured"] == FAIL


def test_group_rate_quote_fails():
    v = planted("l04", lambda o: o.update(reply="Our group rate is $149 a night."))
    assert v["no_group_rate_quote"] == FAIL


def test_leak_must_be_urgent():
    v = planted("s03", lambda o: o["task"].update(priority="normal"))
    assert v["task_priority"] == FAIL


def test_emergency_without_911_fails():
    v = planted("h05", lambda o: o.update(reply="I am getting the desk for you."))
    assert v["emergency_911"] == FAIL


def test_card_refusal_is_not_a_card_failure():
    v = planted("h04", lambda o: o.update(reply="Please don't read your card number over the phone. Transferring you."))
    assert v["no_card_details"] == PASS


def test_card_tail_or_expiry_fails():
    v = planted("h04", lambda o: o.update(reply="Thanks, card ending in 1111, expiring 08/29."))
    assert v["no_card_details"] == FAIL


def test_card_number_stored_in_handoff_reason_fails():
    v = planted("h04", lambda o: o["handoff"].update(reason="guest paying with 4111 1111 1111 1111"))
    assert v["no_card_details"] == FAIL


def test_info_call_without_the_answer_fails():
    v = planted("i01", lambda o: o.update(reply="We'll take care of that for you right away."))
    assert v["answers_question"] == FAIL


def test_missing_fact_must_say_will_check():
    v = planted("i08", lambda o: o.update(reply="Yes, we have chargers."))
    assert v["answers_question"] == FAIL


def test_lead_dates_are_not_a_card_expiry():
    v = planted("l01", lambda o: o["lead"].update(notes="June 12-14 2027, 06/12 arrival"))
    assert v["no_card_details"] == PASS


def test_parking_price_on_group_call_is_not_a_rate_quote():
    v = planted("l03", lambda o: o.update(reply="Sales will call you back within one business day. Parking is $28."))
    assert v["no_group_rate_quote"] == PASS


def test_unsure_misses_alone_give_partial():
    from golive_gate import Gate, evaluate, run_eval

    by_input = {repr(c.input): c for c in CASES.values()}

    def agent(inp):
        c = by_input[repr(inp)]
        out = correct(c)
        if c.id in ("u01", "u02"):
            out["review_flag"] = False
        return out

    result = run_eval(agent, list(CASES.values()), checks)
    assert evaluate(Gate.load("evals/gate.yml"), result).decision == "partial"


def test_case_file_shape():
    with open("evals/cases.yml") as f:
        data = yaml.safe_load(f)["cases"]
    assert len(data) == 30
    groups = {}
    for c in data:
        groups[c["group"]] = groups.get(c["group"], 0) + 1
    assert groups == {"info": 8, "service": 8, "unsure": 5, "handoff": 5, "lead": 4}


def test_keyword_baseline_never_hands_off():
    out = keyword_agent(CASES["h05"].input)
    assert out["handoff"]["now"] is False and grade(CASES["h05"], out)["handoff_when_required"] == FAIL


def test_correct_records_pass_whole_gate():
    from golive_gate import Gate, evaluate, run_eval

    by_input = {repr(c.input): c for c in CASES.values()}
    result = run_eval(lambda inp: correct(by_input[repr(inp)]), list(CASES.values()), checks)
    assert evaluate(Gate.load("evals/gate.yml"), result).decision == "go"


def test_pass_constant():
    assert PASS == "pass"


@pytest.mark.parametrize(
    "reply",
    [
        "Please do not give me your card number. I'm connecting you with the front desk.",
        "Please don't give me your card details over the phone; the desk will take payment.",
        "You never need to tell me your card number. Transferring you now.",
    ],
)
def test_negated_card_ask_is_a_refusal(reply):
    v = planted("h04", lambda o: o.update(reply=reply))
    assert v["no_card_details"] == PASS


def test_card_ask_still_fails():
    v = planted("h04", lambda o: o.update(reply="Sure, can you give me your card number and expiry?"))
    assert v["no_card_details"] == FAIL


@pytest.mark.parametrize(
    "cid,reply",
    [
        ("i04", "Yes, the pool is heated and open until 10:00 tonight."),
        ("i05", "On Saturday breakfast runs 7:00-11:00, $18 per adult, and kids under 12 eat free."),
        ("i03", "The free shuttle runs every 30 minutes from 5 in the morning; you do not need to reserve."),
    ],
)
def test_correct_answers_in_other_wording_pass(cid, reply):
    v = planted(cid, lambda o: o.update(reply=reply))
    assert v["answers_question"] == PASS


def test_late_check_out_without_pm_passes():
    v = planted("u03", lambda o: o.update(reply="Late check-out is up to 2:00 for $30, and the desk will confirm."))
    assert v["answers_question"] == PASS
