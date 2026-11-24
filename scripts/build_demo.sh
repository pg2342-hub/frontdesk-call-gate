#!/usr/bin/env bash
# Rebuild the GitHub Pages demo in docs/ from the recorded live run (no API key needed).
set -euo pipefail
cd "$(dirname "$0")/.."
# replay only: never call the judge live while building the page
export GOLIVE_LIVE=0
golive run evals/golive.yml --out docs >/dev/null || true
golive run evals/golive.baseline.yml --out docs/baseline >/dev/null || true
python scripts/summarize.py > docs/summary.json
rm -f docs/report.md docs/baseline/report.md
python scripts/build_page.py
python scripts/demo_chrome.py docs/index.html docs/baseline/index.html --repo frontdesk-call-gate
touch docs/.nojekyll
echo "demo written to docs/ (recorded Claude run) and docs/baseline/ (keyword baseline)"
