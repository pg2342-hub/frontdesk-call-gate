# frontdesk-call-gate

[![CI](https://github.com/pg2342-hub/frontdesk-call-gate/actions/workflows/ci.yml/badge.svg)](https://github.com/pg2342-hub/frontdesk-call-gate/actions/workflows/ci.yml)

Demo page: https://pg2342-hub.github.io/frontdesk-call-gate/ (every call, check and judge verdict from the recorded live run; no install needed)

A go-live gate for an AI hotel front desk. Every guest call has to end in the right outcome: a correct answer, the right task for the right team and room, a live hand-off when a person is needed, or a sales lead for the group desk. This repo turns that into 30 test calls, yes/no checks and a gate that says **go, partial or no-go** before the agent takes calls on its own.

Built on [golive-gate](https://github.com/pg2342-hub/golive-gate).

## What is in it

| Part | File |
|---|---|
| The agent: one Claude call per guest call, structured output into one record (reply, task, hand-off, lead, review flag) | `frontdesk/agent.py` |
| Property facts for a fictional 180-room airport hotel, and the desk policy the agent follows | `frontdesk/property.yml`, `frontdesk/policy.md` |
| 30 constructed calls in five groups: info (8), service (8), unsure (5), hand-off (5), sales lead (4) | `evals/cases.yml` |
| 12 rule checks, 3 of them critical (missed hand-off, card details, 911 in an emergency) | `evals/checks.py` |
| 3 Claude judge checks for what a rule cannot state: is the answer grounded in the facts, is the guest told what happens next, and is a guest's stay kept private (critical) | `evals/judge_checks.py` |
| The gate, which must hold on each of 3 runs: 24 of the 25 info, service, hand-off and lead calls; every hand-off and lead call; 7 of 8 service calls; 0 critical failures. Unsure calls under 4 of 5 hold rollout at partial instead of blocking it | `evals/gate.yml` |
| A no-model keyword baseline the gate must block | `frontdesk/baseline.py` |

## The one judgment call: what the agent does when it is unsure

Room number missing, the room said does not match the line, a request outside policy, or a vague complaint. The agent **acts and flags**: it creates the task with what it knows, leaves the room blank rather than guessing, tells the guest the desk will confirm, and flags the task for a person to check within 10 minutes. It does not transfer the call for this. The `act_and_flag` and `task_room` checks hold it to that, and missing the unsure group's pass count holds rollout at partial rather than blocking it, because a flagged task is caught by a person. A critical failure on an unsure call, such as confirming a guest's stay to an outside caller, still blocks it.

## Run it

```
pip install -e ".[dev]"
pytest -q                                    # 66 tests, no network
golive run evals/golive.baseline.yml         # keyword baseline: NO-GO
golive run evals/golive.yml                  # replays the recorded Claude run: no key needed
GOLIVE_LIVE=1 ANTHROPIC_API_KEY=... golive run evals/golive.live.yml   # a fresh live run, recorded to recordings/
golive ablate evals/golive.baseline.yml      # which check catches what
```

## How the live run is recorded

The agent and the judge call Claude (`claude-opus-5-5`, low effort, structured output for the agent). A live run writes every reply to `recordings/`, with cost and latency per call. CI and the demo page replay that recording, so they need no API key and give the same result every time; `tests/test_pipeline.py` checks that a replay makes no API calls and reaches the same decision. The **Record a live run** workflow (Actions tab, needs the `ANTHROPIC_API_KEY` secret) refreshes the recording and the demo page.

## CI

Every push runs ruff, the tests, the baseline (which must come out no-go), and the recorded run through the golive-gate GitHub Action, which fails the build on no-go and writes the report to the job summary.

All calls, names and phone numbers are constructed. The hotel is fictional.
