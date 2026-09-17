#!/usr/bin/env bash
# Fails if anything machine-specific leaks into a file we ship.
#
# Trimmed from vmgm/agent-skills. That repo ships REUSABLE skills installed
# against any property, so a hardcoded domain is a bug there and its linter bans
# them. This repo ships a skill for ONE product, where
# https://viewprinter.tech/api/mcp is the correct and necessary value — so the
# domain checks are deliberately absent. Copying that linter whole would fail on
# the one value that is supposed to be there.
#
# What survives the trim is what leaks in any repo:
#
#   absolute home paths   /Users/someone/ — true of a machine, not of the skill
#   long numeric ids      6+ digits: account, workspace and platform ids
#   stray root copies     a file duplicated between a skill root and a subfolder
#
# Evidence is allowed only in a file carrying "WORKED EXAMPLE", which prints as
# a warning instead of failing.
set -uo pipefail
cd "$(dirname "$0")/.."
FAIL=0

# Scoped to what ships. scripts/ is excluded because this file contains the
# patterns it bans, and a linter that fails on itself teaches people to skip it.
SCAN=$(find skills clawhub -type f \( -name '*.md' -o -name '*.sh' \) ! -path '*/dist/*' | sort)

BANNED='(/Users/[a-z]+/|[0-9]{6,})'
while IFS= read -r f; do
  [ -n "$f" ] || continue
  hits=$(grep -nE "$BANNED" "$f" 2>/dev/null | grep -vE 'example\.(com|org)|<your|<this' || true)
  [ -z "$hits" ] && continue
  if grep -q 'WORKED EXAMPLE' "$f"; then
    printf "  \033[33m~\033[0m %-52s evidence (labelled)\n" "$f"
  else
    printf "  \033[31m✗\033[0m %-52s LEAK\n" "$f"
    echo "$hits" | head -3 | sed 's/^/        /'
    FAIL=1
  fi
done <<< "$SCAN"

# A file whose basename also exists in a subdirectory is a stray copy — usually a
# multi-source `cp` that landed in the skill root. They go stale silently because
# nothing references them, and an agent grepping the tree finds the old content.
for sk in skills/*/; do
  for f in "$sk"*.md "$sk"*.sh; do
    [ -e "$f" ] || continue
    b=$(basename "$f")
    case "$b" in SKILL.md|PREREQUISITES.md|README.md) continue;; esac
    dupe=$(find "$sk" -mindepth 2 -name "$b" | head -1)
    if [ -n "$dupe" ]; then
      printf "  \033[31m✗\033[0m %-52s STRAY ROOT COPY of %s\n" "$f" "${dupe#$sk}"
      FAIL=1
    fi
  done
done

echo
if [ $FAIL -eq 0 ]; then
  echo "  portability lint PASSED"
else
  echo "  portability lint FAILED — move the value into .mcp.json, label the file as a worked example, or delete the stray root copy"
  exit 1
fi
