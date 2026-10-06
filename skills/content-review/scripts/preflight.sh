#!/usr/bin/env bash
# Exercises the documented path offline: the Python helpers this skill runs
# start and print their usage. Read-only; it writes, serves and sends nothing.
set -uo pipefail
FAIL=0
ok()  { printf "  \033[32m✓\033[0m %s\n" "$1"; }
bad() { printf "  \033[31m✗\033[0m %s\n" "$1"; FAIL=1; }
HERE="$(cd "$(dirname "$0")" && pwd)"

python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null \
  && ok "python3 3.11 or newer" || bad "python3 3.11 or newer is required"
for script in review_hub.py review_gallery.py; do
  python3 "$HERE/$script" --help >/dev/null 2>&1 && ok "$script starts" || bad "$script does not start"
done

echo
[ $FAIL -eq 0 ] && echo "  preflight PASSED" || { echo "  preflight FAILED"; exit 1; }
