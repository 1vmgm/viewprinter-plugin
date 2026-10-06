#!/usr/bin/env bash
# Render the documented minimal brief locally; no remote account changes.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REVIEW_TMP=$(mktemp -d)
trap 'rm -rf "$REVIEW_TMP"' EXIT
cp "$SKILL_DIR/templates/group.json" "$REVIEW_TMP/group.json"
python3 "$SKILL_DIR/scripts/build_review.py" --manifest "$REVIEW_TMP/group.json" --output "$REVIEW_TMP/review.html"
