"""Agents for golive-gate. golive calls each with case.input and grades what comes back.

- recorded_agent: replays the last live run from recordings/ (no key; CI and the demo use this)
- live_agent:     calls Claude now and appends each record to recordings/ (needs ANTHROPIC_API_KEY)
- keyword_agent:  the no-model baseline the gate must block
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from golive_gate import Response

from frontdesk.baseline import keyword_agent as _keyword
from frontdesk.recorded import ROOT, Tape, recording_agent, replay_agent

AGENT_TAPE = Tape(ROOT / "agent.jsonl")
_live = None


def _as_response(record):
    meta = record.get("_meta", {})
    return Response(record, cost_usd=meta.get("cost_usd", 0.0))


def recorded_agent(case_input):
    return _as_response(replay_agent(AGENT_TAPE)(case_input))


def live_agent(case_input):
    global _live
    if _live is None:  # created on first use, so importing this file needs no key
        from frontdesk.agent import ClaudeFrontDesk

        _live = recording_agent(ClaudeFrontDesk(), AGENT_TAPE)
    return _as_response(_live(case_input))


def keyword_agent(case_input):
    return _keyword(case_input)
