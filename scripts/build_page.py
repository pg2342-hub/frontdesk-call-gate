"""Write the demo pages (docs/index.html, docs/baseline/index.html) from the graded runs.

    python scripts/build_page.py

Reads docs/results.json and docs/baseline/results.json (written by `golive run`), docs/summary.json
(scripts/summarize.py) and evals/cases.yml for what each guest said. Standard library and PyYAML only.
"""

from __future__ import annotations

import json
from html import escape as e
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
REPO = "https://github.com/pg2342-hub/frontdesk-call-gate"
GOLIVE = "https://github.com/pg2342-hub/golive-gate"
GROUPS = [("info", "Info"), ("service", "Service"), ("unsure", "Unsure"), ("handoff", "Hand-off"), ("lead", "Lead")]
JUDGE = {"answer_grounded", "next_step_clear", "guest_privacy"}
LABEL = {"go": "GO", "partial": "PARTIAL", "no-go": "NO-GO"}
CLS = {"go": "go", "partial": "partial", "no-go": "nogo"}


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def critical_ids(res: dict) -> set[str]:
    return {c["id"] for c in res["checks"] if c["critical"]}


def case_state(res: dict, case: dict) -> tuple[str, int]:
    """pass, fail or crit for one call over every run, and how many runs it passed."""
    crit = critical_ids(res)
    passed = sum(r["passed"] for r in case["runs"])
    if any(set(r["failed_checks"]) & crit for r in case["runs"]):
        return "crit", passed
    return ("pass" if passed == len(case["runs"]) else "fail"), passed


def cell_word(state: str, passed: int, runs: int) -> str:
    if state == "pass":
        return f"passed {runs} of {runs} runs"
    tail = ", with a critical failure" if state == "crit" else ""
    return f"passed {passed} of {runs} runs{tail}"


def groups_of(res: dict) -> list[tuple[str, str, list[dict]]]:
    return [(g, name, [c for c in res["cases"] if c["group"] == g]) for g, name in GROUPS]


def strip(res: dict, who: str) -> str:
    runs = res["runs"]
    out = []
    for _, name, cases in groups_of(res):
        cells = []
        for c in cases:
            st, p = case_state(res, c)
            label = f"{who}: {c['title']} ({name}) {cell_word(st, p, runs)}"
            href = f'href="#call-{c["id"]}" data-case="{c["id"]}"'
            cells.append(f'<a class="cell {st}" {href} aria-label="{e(label)}"></a>')
        out.append(
            f'<div class="grp" style="flex:{len(cases)};grid-template-columns:repeat({len(cases)},minmax(0,1fr))">'
            + "".join(cells)
            + "</div>"
        )
    return f'<div class="strip" role="group" aria-label="{e(who)}: every call">{"".join(out)}</div>'


def group_labels(res: dict) -> str:
    labs = "".join(f'<div class="glab" style="flex:{len(cs)}">{name} {len(cs)}</div>' for _, name, cs in groups_of(res))
    return f'<div class="vrow groups" aria-hidden="true"><span></span><div class="strip">{labs}</div></div>'


def verdict_row(res: dict, who: str, sub: str) -> str:
    by_run = res["summary"]["by_run"]
    passed = sorted({r["passed"] for r in by_run})
    total = by_run[0]["total"]
    crit = sum(len(v) for v in res["gate_result"]["critical_failures"].values())
    score = str(passed[0]) if len(passed) == 1 else f"{passed[0]}-{passed[-1]}"
    each = "each run" if len(by_run) > 1 else "one run"
    d = res["decision"]
    return f"""<div class="vrow">
  <div class="vwho"><b>{who}</b><span>{sub}</span></div>
  {strip(res, who)}
  <div class="vscore"><b>{score}</b><span>of {total} passed, {each}<br>{crit} critical failures</span></div>
  <span class="gate {CLS[d]}">{LABEL[d]}</span>
</div>"""


def rules_table(main: dict, other: dict | None, other_name: str) -> str:
    rows = {}
    for r in main["gate_result"]["rules"]:
        rows.setdefault(r["name"], []).append(r)
    base = {}
    if other:
        for r in other["gate_result"]["rules"]:
            base.setdefault(r["name"], r)
    body = []
    for name, rs in rows.items():
        first = rs[0]
        runs = "".join(f'<td class="c {"ok" if r["held"] else "miss"}">{r["passed"]} of {r["total"]}</td>' for r in rs)
        if_missed = "Holds at partial" if first["on_fail"] == "partial" else "Blocks: no-go"
        b = base.get(name)
        bcell = f'<td class="c {"ok" if b["held"] else "miss"}">{b["passed"]} of {b["total"]}</td>' if b else ""
        body.append(
            f"<tr><td>{e(name[0].upper() + name[1:])}</td>{runs}<td class='c'>{first['required']}</td>"
            f"<td>{if_missed}</td>{bcell}</tr>"
        )
    n = len(main["summary"]["by_run"])
    heads = "".join(f'<th class="c">Run {i + 1}</th>' for i in range(n))
    run1 = ", run 1" if other and other["runs"] > 1 else ""
    bhead = f'<th class="c">{e(other_name)}{run1}</th>' if other else ""
    cf = main["gate_result"]["critical_failures"]
    crit_cells = "".join(
        f'<td class="c {"miss" if cf.get(str(i + 1)) else "ok"}">{len(cf.get(str(i + 1), []))}</td>' for i in range(n)
    )
    bcrit = ""
    if other:
        crit_other = len(other["gate_result"]["critical_failures"].get("1", []))
        bcrit = f'<td class="c {"miss" if crit_other else "ok"}">{crit_other}</td>'
    return (
        '<div class="scroll"><table class="rules"><thead><tr><th>Rule</th>'
        f'{heads}<th class="c">Needs</th><th>If missed</th>{bhead}</tr></thead><tbody>{"".join(body)}'
        f'<tr><td>Critical failures</td>{crit_cells}<td class="c">0</td><td>Blocks: no-go</td>{bcrit}</tr>'
        "</tbody></table></div>"
    )


def matrix(res: dict, agent: str, hidden: bool) -> str:
    """15 checks by 30 calls: what each check said about each call, over every run."""
    runs = res["runs"]
    cells = ['<div class="gh">Check</div>']
    for _, name, cs in groups_of(res):
        cells.append(f'<div class="gh" style="grid-column:span {len(cs)}">{name}</div>')
    cells.append("<div></div>")
    for c in res["cases"]:
        cells.append(f'<div class="ch"><a href="#call-{c["id"]}" title="{e(c["title"])}">{c["id"][1:]}</a></div>')
    for ck in res["checks"]:
        tags = ""
        if ck["id"] in JUDGE:
            tags += '<i title="Graded by the Claude judge">judge</i>'
        if ck["critical"]:
            tags += '<i class="k" title="Critical: one failure blocks go-live">crit</i>'
        cells.append(f'<div class="rl" title="{e(ck["text"])}"><span>{ck["id"]}</span>{tags}</div>')
        for c in res["cases"]:
            results = [r["verdicts"].get(ck["id"], {}).get("result", "na") for r in c["runs"]]
            fails = results.count("fail")
            if fails:
                st = "crit" if ck["critical"] else "fail"
                txt = str(fails) if runs > 1 else ""
                word = f"failed on {fails} of {runs} runs"
            elif all(x == "na" for x in results):
                st, txt, word = "na", "", "does not apply"
            else:
                st, txt, word = "pass", "", "passed"
            cells.append(
                f'<a class="m {st}" href="#call-{c["id"]}" aria-label="{e(ck["id"])} on {c["id"]}: {word}">{txt}</a>'
            )
    attr = " hidden" if hidden else ""
    return f'<div class="mx-pane" data-agent="{agent}"{attr}><div class="mx">{"".join(cells)}</div></div>'


def record_bits(out: dict) -> str:
    bits = []
    t = out.get("task")
    if t:
        bits.append(f"<span>Task <b>{e(str(t.get('department')))}</b></span>")
        bits.append(f"<span>Room <b>{e(str(t.get('room') or 'blank'))}</b></span>")
        bits.append(f"<span>Priority <b>{e(str(t.get('priority')))}</b></span>")
    else:
        bits.append("<span>Task <b>none</b></span>")
    h = out.get("handoff") or {}
    bits.append(f"<span>Hand-off <b>{'now' if h.get('now') else 'no'}</b></span>")
    lead = out.get("lead")
    if lead:
        n = lead.get("rooms") or lead.get("people")
        unit = "rooms" if lead.get("rooms") else "people"
        bits.append(f"<span>Lead <b>{e(str(lead.get('type')))}, {n} {unit}</b></span>")
    bits.append(f"<span>Review flag <b>{'yes' if out.get('review_flag') else 'no'}</b></span>")
    return f'<div class="rec">{"".join(bits)}</div>'


def run_block(run: dict, crit: set[str], nruns: int) -> str:
    out = run.get("output") or {}
    meta = out.get("_meta", {})
    head = [f"<b>Run {run['run']}: {'pass' if run['passed'] else 'fail'}</b>"]
    if meta.get("latency_s") is not None:
        head.append(f"{meta['latency_s']:.1f} s")
    if meta.get("cost_usd") is not None:
        head.append(f"${meta['cost_usd']:.4f}")
    reply = f'<blockquote class="reply">{e(out.get("reply", ""))}</blockquote>' if out.get("reply") else ""
    rec = record_bits(out) if out else ""
    detail, quiet = [], []
    for cid, v in run["verdicts"].items():
        res = v["result"]
        tag = " (critical)" if cid in crit else ""
        if res == "fail" or v.get("reason"):
            reason = f": {e(v['reason'])}" if v.get("reason") else ""
            detail.append(
                f'<li class="{res}"><span class="r {res}">{res.upper()}</span>'
                f"<span><code>{cid}</code>{tag}{reason}</span></li>"
            )
        else:
            quiet.append(f'<code class="{res}">{cid} {res.upper()}</code>')
    verd = f'<ul class="verd">{"".join(detail)}</ul>' if detail else ""
    chips = f'<div class="chips">{"".join(quiet)}</div>' if quiet else ""
    raw = json.dumps(out, indent=1, ensure_ascii=False)
    return (
        f'<div class="run{"" if run["passed"] else " bad"}"><div class="runhead">{" · ".join(head)}</div>'
        f"{reply}{rec}{verd}{chips}"
        f'<details class="raw"><summary>Raw output</summary><pre>{e(raw)}</pre></details></div>'
    )


def call_list(res: dict, inputs: dict) -> str:
    crit = critical_ids(res)
    nruns = res["runs"]
    out = []
    names = dict(GROUPS)
    for c in res["cases"]:
        st, p = case_state(res, c)
        dots = "".join(
            f'<i class="{"pass" if r["passed"] else ("crit" if set(r["failed_checks"]) & crit else "fail")}"></i>'
            for r in c["runs"]
        )
        inp = inputs.get(c["id"], {})
        said = ""
        if inp:
            said = (
                f'<dl class="said"><dt>Guest said</dt><dd>“{e(inp.get("transcript", ""))}”</dd>'
                f"<dt>Line, time</dt><dd>{e(str(inp.get('line', '')))}, {e(str(inp.get('time', '')))}</dd></dl>"
            )
        runs = "".join(run_block(r, crit, nruns) for r in c["runs"])
        missed = "1" if st != "pass" else "0"
        out.append(
            f'<details class="call" id="call-{c["id"]}" data-group="{c["group"]}" data-missed="{missed}">'
            f'<summary><span class="t">{e(c["title"])}</span><span class="g">{names[c["group"]]} · {c["id"]}</span>'
            f'<span class="dots" aria-hidden="true">{dots}</span><span class="rn">{p} of {nruns} runs</span></summary>'
            f'<div class="body">{said}{runs}</div></details>'
        )
    return '<div class="calls">' + "".join(out) + "</div>"


def call_filter(res: dict) -> str:
    missed = sum(case_state(res, c)[0] != "pass" for c in res["cases"])

    def btn(v: str, name: str, n: int, on: bool = False) -> str:
        checked = "true" if on else "false"
        return f'<button type="button" role="radio" aria-checked="{checked}" data-v="{v}">{name}&nbsp; <span>{n}</span>'

    bs = [btn("all", "All", len(res["cases"]), True)]
    bs += [btn(g, name, len(cs)) for g, name, cs in groups_of(res)]
    bs.append(btn("missed", "Missed", missed))
    return (
        '<div class="seg" role="radiogroup" aria-label="Filter calls" id="call-seg">'
        + "</button>".join(bs)
        + "</button></div>"
    )


def misses(res: dict, inputs: dict) -> str:
    cards = []
    nruns = res["runs"]
    for c in res["cases"]:
        st, p = case_state(res, c)
        if st == "pass":
            continue
        bad = [r for r in c["runs"] if not r["passed"]]
        r = bad[0]
        why = "; ".join(
            f"<code>{k}</code>: {e(v['reason'])}" for k, v in r["verdicts"].items() if v["result"] == "fail"
        )
        said = e(inputs.get(c["id"], {}).get("transcript", ""))
        cards.append(
            f'<div class="miss-card"><span class="runs">{c["id"]} · failed {nruns - p} of {nruns} runs</span>'
            f"<h3>{e(c['title'])}</h3><blockquote>“{said}”</blockquote><p class='why'>{why}</p>"
            f'<a href="#call-{c["id"]}">Every run of this call</a></div>'
        )
    return '<div class="misses">' + "".join(cards) + "</div>"


def checks_table(res: dict) -> str:
    rows = []
    for ck in res["checks"]:
        kind = "Claude judge" if ck["id"] in JUDGE else "Rule"
        sev = '<span class="sev sev-critical">Critical</span>' if ck["critical"] else ""
        rows.append(f"<tr><td><code>{ck['id']}</code></td><td>{e(ck['text'])}</td><td>{kind}</td><td>{sev}</td></tr>")
    return (
        '<div class="scroll"><table class="ck"><thead><tr><th>Check</th><th>What it checks</th><th>Graded by</th>'
        f"<th>Severity</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def page(title: str, desc: str, body: str, css: str, js: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{title}</title><meta name="description" content="{e(desc)}">'
        f"<style>\n{css}</style></head><body><main>\n{body}\n</main>\n<script>\n{js}</script></body></html>\n"
    )


def build(main: dict, other: dict, s: dict, inputs: dict, baseline_page: bool) -> str:
    claude, base = (other, main) if baseline_page else (main, other)
    claude_sub = f"Recorded live run of <code class='nw'>{e(s['model'])}</code>, {claude['runs']} runs"
    base_sub = "No model; keyword rules, one run"
    if baseline_page:
        rows = verdict_row(base, "Keyword baseline", base_sub) + verdict_row(
            claude, "Claude agent", f'{claude_sub}. <a href="../">Its page</a>'
        )
        lead = (
            "The no-model keyword baseline on the same 30 calls and gate: it never hands a call to a person and "
            'never captures a sales lead, so the gate blocks it. <a href="../">Back to the Claude agent</a>.'
        )
        h1, other_name, back = "Keyword Baseline, Blocked", "Claude agent", '<a href="../">The Claude agent</a>'
    else:
        rows = verdict_row(claude, "Claude agent", claude_sub) + verdict_row(
            base, "Keyword baseline", f'{base_sub}. <a href="baseline/">Its page</a>'
        )
        lead = (
            "An AI front desk for a fictional 180-room airport hotel, graded on 30 constructed guest calls "
            f'(3 runs each) with <a href="{GOLIVE}">golive-gate</a>. Rules grade what a rule can state exactly; '
            "a Claude judge grades whether answers are grounded, whether the guest is told what happens next, "
            "and whether a guest's stay is kept private."
        )
        h1, other_name = "AI Front Desk Go-Live Gate", "Keyword baseline"
        back = '<a href="baseline/">Keyword baseline</a>'
    stats = (
        '<div class="stats">'
        f"<div class='stat'><b>{s['calls']}</b>agent calls in the recorded run</div>"
        f"<div class='stat'><b>{s['mean_latency_s']:.1f} s</b>mean per call, {s['p90_latency_s']:.1f} s p90</div>"
        f"<div class='stat'><b>${s['mean_cost_usd']:.4f}</b>mean per call, ${s['agent_cost_usd']:.2f} in total</div>"
        f"<div class='stat'><b>${s['judge_cost_usd']:.2f}</b>judge, {s['judge_calls']} calls in total</div>"
        "</div>"
    )
    first = base if baseline_page else claude
    second = claude if baseline_page else base
    first_v, second_v = ("baseline", "claude") if baseline_page else ("claude", "baseline")
    first_n, second_n = ("Keyword baseline", "Claude agent") if baseline_page else ("Claude agent", "Keyword baseline")
    missed = [c for c in first["cases"] if case_state(first, c)[0] != "pass"]
    jump = "".join(f'<a href="#call-{c["id"]}"><span>{c["id"]}</span>{e(c["title"])}</a>' for c in missed)
    if baseline_page:
        jump = ""
    missed_section = ""
    if not baseline_page:
        missed_section = f"""<section id="missed"><h2>What it missed</h2>
<p class="note" style="margin:0 0 16px">Three calls missed on at least one run. The agent never created a task for an
outside caller's package: it kept the guest's privacy, but gave the desk nothing to act on. On 3 of 90 calls the judge
failed a promise the facts do not support.</p>
{misses(claude, inputs)}</section>"""
    words = {3: "Three", 4: "Four", 12: "Twelve", 15: "Fifteen"}
    n_judge = sum(c["id"] in JUDGE for c in first["checks"])
    n_rule = len(first["checks"]) - n_judge
    n_crit = sum(c["critical"] for c in first["checks"])
    checks_line = f"{words.get(n_rule, n_rule)} rule checks"
    if n_judge:
        checks_line += f" and {words.get(n_judge, n_judge).lower()} Claude judge checks"
    checks_line += f". {words.get(n_crit, n_crit)} are critical: one failure blocks go-live."
    nav_missed = '<a href="#missed">What it missed</a>' if not baseline_page else ""
    run_it = (
        'pip install -e ".[dev]"\npytest -q\ngolive run evals/golive.baseline.yml\ngolive run evals/golive.yml\n'
        "scripts/build_demo.sh"
    )
    body = f"""<div class="head">
<h1>{h1}</h1>
<p class="lead">{lead}</p>
</div>

<section class="verdict" aria-labelledby="verdict-h">
  <div class="vhead"><h2 id="verdict-h">Same 30 calls, same gate</h2><p>Gate: every rule holds on <b>each run</b>,
  <b>zero</b> critical failures</p></div>
  {group_labels(first)}
  {rows}
  {"" if baseline_page else stats}
  <div class="legend"><span><i class="pass"></i>Passed every run</span><span><i class="fail"></i>Failed a run</span>
  <span><i class="crit"></i>Critical failure</span><span>Each square is one call. Select one to read it.</span></div>
</section>

<section id="matrix" class="wide"><h2>Every check on every call</h2>
<p class="note" style="margin:0 0 16px">One row per check, one column per call. A number is how many runs failed
that check. Select a column to open the call.</p>
<div class="mx-wrap">
<div class="seg" role="radiogroup" aria-label="Agent" id="mx-seg"><button type="button" role="radio"
aria-checked="true" data-v="{first_v}">{first_n}</button><button type="button" role="radio" aria-checked="false"
data-v="{second_v}">{second_n}</button></div>
<div class="mx-scroll">{matrix(first, first_v, False)}{matrix(second, second_v, True)}</div>
<div class="legend"><span><i class="pass"></i>Passed</span><span><i class="fail"></i>Failed</span>
<span><i class="crit"></i>Critical check failed</span><span><i class="na"></i>Does not apply</span></div>
</div></section>

<div class="layout">
<div class="content">

<section id="gate"><h2>The gate, rule by rule</h2>
<p class="note" style="margin:0 0 16px">Each rule must hold on every run. Unsure calls under 4 of 5 hold rollout at
partial instead of blocking it, because a flagged task is caught by a person. A critical failure on any call
blocks it.</p>
{rules_table(first, second, other_name)}</section>



{missed_section}

<section id="calls"><h2>Every call</h2>
<div style="display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;justify-content:space-between">
{call_filter(first)}<button type="button" id="open-all" aria-expanded="false"
style="margin-bottom:16px">Expand all</button></div>
{call_list(first, inputs)}</section>

<section id="checks"><h2>Checks</h2>
<p class="note" style="margin:0 0 16px">{checks_line}</p>
{checks_table(first)}</section>
</div>

<aside class="side" aria-label="About this build">
  <nav aria-label="On this page"><a href="#verdict-h">Verdict</a><a href="#matrix">Every check on every call</a>
  <a href="#gate">The gate, rule by rule</a>{nav_missed}<a href="#calls">Every call <small>30</small></a>
  <a href="#checks">Checks <small>{len(first["checks"])}</small></a></nav>
  {f'<div class="jump"><h3>Missed calls</h3>{jump}</div>' if jump else ""}
  <div><h3>Data</h3><p>Constructed calls, names and phone numbers; the hotel is fictional. The page replays the
  recorded live run in <code>recordings/</code>, so it needs no API key and gives the same result every time.</p></div>
  <div><h3>Also</h3><p>{back}</p></div>
  <div><h3>Run it yourself</h3><p>Python 3.10+.</p><pre>{e(run_it)}</pre></div>
  <div><a class="pill" href="{REPO}">Code on GitHub</a></div>
</aside>
</div>"""
    desc = (
        "A go-live gate for an AI hotel front desk: 30 constructed guest calls, 3 runs each, rule checks and a "
        f"Claude judge. Recorded run: {LABEL[claude['decision']]}; the keyword baseline: {LABEL[base['decision']]}."
    )
    return body, desc, h1


def main() -> None:
    claude = load(DOCS / "results.json")
    base = load(DOCS / "baseline" / "results.json")
    s = load(DOCS / "summary.json")
    cases = yaml.safe_load((ROOT / "evals" / "cases.yml").read_text())["cases"]
    inputs = {c["id"]: c.get("input", {}) for c in cases}
    css = (ROOT / "scripts" / "page.css").read_text()
    js = (ROOT / "scripts" / "page.js").read_text()
    for path, main_res, other, is_base in [
        (DOCS / "index.html", claude, base, False),
        (DOCS / "baseline" / "index.html", base, claude, True),
    ]:
        body, desc, title = build(main_res, other, s, inputs, is_base)
        path.write_text(page(title, desc, body, css, js))
    print("wrote docs/index.html and docs/baseline/index.html")


if __name__ == "__main__":
    main()
