#!/usr/bin/env bash
# Every skill has the same shape, so an agent (or a person) knows where to look without
# reading the tree. This is the Agent Skills anatomy — SKILL.md plus three bundled
# folders — with the two additions this repo relies on: templates/ for the shape of a
# skill's memory, and scripts/preflight.sh so the documented path gets exercised.
#
#   SKILL.md            required — frontmatter with name + description
#   PREREQUISITES.md    optional — what must be installed or logged in
#   README.md           optional
#   references/         docs read on demand; subfolders allowed
#   scripts/            code that runs; scripts/preflight.sh is required
#   templates/          the shape of the memory dir, JSON only
#   assets/             files copied into output
#   evals/              test prompts for the skill
#
# Anything else at a skill root fails. Content placed elsewhere goes stale because nothing
# links to it, and a second convention is one more thing to remember.
set -uo pipefail
cd "$(dirname "$0")/.."
FAIL=0
ALLOWED_FILES='SKILL.md|PREREQUISITES.md|README.md'
ALLOWED_DIRS='references|scripts|templates|assets|evals'
for sk in skills/*/; do
  name=${sk#skills/}; name=${name%/}
  f="$sk/SKILL.md"
  if [ ! -f "$f" ]; then printf "  \033[31m✗\033[0m %-28s missing SKILL.md\n" "$name"; FAIL=1; continue; fi
  head -20 "$f" | grep -q '^name:'        || { printf "  \033[31m✗\033[0m %-28s SKILL.md has no name: frontmatter\n" "$name"; FAIL=1; }
  head -20 "$f" | grep -q '^description:' || { printf "  \033[31m✗\033[0m %-28s SKILL.md has no description: frontmatter\n" "$name"; FAIL=1; }
  [ -x "$sk/scripts/preflight.sh" ]       || { printf "  \033[31m✗\033[0m %-28s scripts/preflight.sh missing or not executable\n" "$name"; FAIL=1; }
  for e in "$sk"* "$sk".[!.]*; do
    [ -e "$e" ] || continue
    b=$(basename "$e")
    if [ -d "$e" ]; then
      echo "$b" | grep -qE "^($ALLOWED_DIRS)$" || { printf "  \033[31m✗\033[0m %-28s stray directory %s/\n" "$name" "$b"; FAIL=1; }
    else
      echo "$b" | grep -qE "^($ALLOWED_FILES)$" || { printf "  \033[31m✗\033[0m %-28s stray root file %s\n" "$name" "$b"; FAIL=1; }
    fi
  done
  # templates hold the shape of memory: JSON only
  while IFS= read -r t; do
    printf "  \033[31m✗\033[0m %-28s non-JSON in templates/: %s\n" "$name" "${t#$sk}"; FAIL=1
  done < <(find "$sk/templates" -type f ! -name '*.json' 2>/dev/null)
  [ $FAIL -eq 0 ] && printf "  \033[32m✓\033[0m %s\n" "$name"
done
# A SKILL.md anywhere else is installed as a skill. `npx skills add owner/repo`
# scans the whole repository, so clawhub/SKILL.md — a build input — was being
# installed alongside the real one, with its references left behind in dist/ and
# every link in it dead. Generated copies live under a different name.
while IFS= read -r stray; do
  printf "  \033[31m✗\033[0m %-28s SKILL.md outside skills/: %s\n" "(repo)" "$stray"; FAIL=1
done < <(find . -name SKILL.md -not -path './.git/*' -not -path './skills/*' -not -path '*/dist/*' -not -path '*/node_modules/*' 2>/dev/null | sed 's|^\./||')

echo
[ $FAIL -eq 0 ] && echo "  shape lint PASSED" || { echo "  shape lint FAILED — see the layout at the top of scripts/lint-shape.sh"; exit 1; }
