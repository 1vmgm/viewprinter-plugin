#!/usr/bin/env bash
# Render the documented minimal brief locally; no remote account changes.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REVIEW_TMP=$(mktemp -d)
trap 'rm -rf "$REVIEW_TMP"' EXIT
cp "$SKILL_DIR/templates/group.json" "$REVIEW_TMP/group.json"
# python3 on macOS and Linux; a Windows install is often python, or the py launcher.
PYTHON=""
for candidate in python3 python "py -3"; do
  if $candidate -c 'import sys; sys.exit(sys.version_info < (3, 9))' >/dev/null 2>&1; then
    PYTHON="$candidate"
    break
  fi
done
[ -n "$PYTHON" ] || { echo "Python 3.9 or newer is required (python3, python or py -3)" >&2; exit 1; }
$PYTHON "$SKILL_DIR/scripts/build_review.py" --manifest "$REVIEW_TMP/group.json" --output "$REVIEW_TMP/review.html"
