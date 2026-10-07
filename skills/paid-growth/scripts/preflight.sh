#!/usr/bin/env bash
# Exercises the documented path offline: the Python helpers this skill runs
# start and print their usage. Read-only; it writes, serves and sends nothing.
set -uo pipefail
FAIL=0
ok()  { printf "  \033[32m✓\033[0m %s\n" "$1"; }
bad() { printf "  \033[31m✗\033[0m %s\n" "$1"; FAIL=1; }
HERE="$(cd "$(dirname "$0")" && pwd)"

# python3 on macOS and Linux; a Windows install is often python, or the py launcher.
PYTHON=""
for candidate in python3 python "py -3"; do
  if $candidate -c 'import sys; sys.exit(sys.version_info < (3, 9))' >/dev/null 2>&1; then
    PYTHON="$candidate"
    break
  fi
done
[ -n "$PYTHON" ] && ok "$PYTHON is 3.9 or newer" || bad "Python 3.9 or newer is required (python3, python or py -3)"
for script in arena.py; do
  [ -n "$PYTHON" ] && $PYTHON "$HERE/$script" --help >/dev/null 2>&1 && ok "$script starts" || bad "$script does not start"
done

echo
[ $FAIL -eq 0 ] && echo "  preflight PASSED" || { echo "  preflight FAILED"; exit 1; }
