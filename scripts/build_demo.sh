#!/usr/bin/env bash
# Rebuild the GitHub Pages demo in docs/ from the recorded live run (no API key needed).
set -euo pipefail
cd "$(dirname "$0")/.."
golive run evals/golive.yml --out docs >/dev/null || true
golive run evals/golive.baseline.yml --out docs/baseline >/dev/null || true
python scripts/summarize.py > docs/summary.json
rm -f docs/report.md docs/baseline/report.md
python - <<'PY'
import json
from pathlib import Path

s = json.loads(Path("docs/summary.json").read_text())
notes = {
    "docs/index.html": (
        "An AI front desk for a fictional 180-room airport hotel, graded on 30 constructed guest calls "
        f"(3 runs each) with <a href='https://github.com/pg2342-hub/golive-gate'>golive-gate</a>. "
        f"Recorded live run of {s['model']}: {s['calls']} agent calls, mean {s['mean_latency_s']:.1f} s and "
        f"${s['mean_cost_usd']:.4f} per call; judge ${s['judge_cost_usd']:.2f} in total. "
        "Rules grade what a rule can state exactly; a Claude judge grades whether answers are grounded and "
        "whether the guest is told what happens next. "
        "<a href='baseline/'>See a no-model keyword baseline blocked by the same gate</a>. "
        "<a href='https://github.com/pg2342-hub/frontdesk-call-gate'>Code on GitHub</a>."
    ),
    "docs/baseline/index.html": (
        "The no-model keyword baseline on the same 30 calls and gate: it never hands a call to a person and "
        "never captures a sales lead, so the gate blocks it. <a href='../'>Back to the Claude agent</a>."
    ),
}
for path, note in notes.items():
    p = Path(path)
    p.write_text(p.read_text().replace("</h1>", f"</h1>\n<p>{note}</p>", 1))
PY
touch docs/.nojekyll
echo "demo written to docs/ (recorded Claude run) and docs/baseline/ (keyword baseline)"
