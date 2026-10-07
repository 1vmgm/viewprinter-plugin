#!/usr/bin/env python3
"""Refuse anything private before it reaches this public repository.

Everything here ships to customers. What real use teaches belongs in the skills
as general rules; the evidence — account and post ids, handles, home paths,
private addresses — never does. See AGENTS.md.

  lint_privacy.py            check every file git would publish
  lint_privacy.py --staged   check what is staged (the commit hook)

Built-in patterns are generic, so they are safe to publish and CI runs them on
every push. Names that are private in themselves (a brand, a handle, a page id)
go one per line in private/denylist.txt, which git ignores and CI never sees.

Findings are masked: on a public repository the CI log is public too.
"""

# Annotations such as `str | None` are 3.10 syntax; deferring them lets the commit hook run
# on macOS's built-in Python 3.9.
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DENYLIST = REPO / "private" / "denylist.txt"
ALLOW_MARK = "privacy-lint: allow"
# Addresses this repository publishes on purpose.
ALLOWED_EMAILS = {"hello@vmgmsoftware.com"}

PATTERNS = {
    # A ViewPrinter account or workspace id: 32 letters and digits, both cases.
    # Excludes hex digests (one case) and long camelCase keys (no digits).
    "account id": re.compile(
        r"(?<![A-Za-z0-9])(?=[A-Za-z0-9]{32}(?![A-Za-z0-9]))"
        r"(?=[A-Za-z0-9]*\d)(?=[A-Za-z0-9]*[a-z])(?=[A-Za-z0-9]*[A-Z])[A-Za-z0-9]{32}"
    ),
    # A ViewPrinter post or media id: 25 lower-case letters and digits.
    "post id": re.compile(
        r"(?<![A-Za-z0-9])(?=[a-z0-9]{25}(?![A-Za-z0-9]))"
        r"(?=[a-z0-9]*\d)(?=[a-z0-9]*[a-z])[a-z0-9]{25}"
    ),
    "home path": re.compile(r"/Users/[^/\s]+/|/home/[^/\s]+/|C:\\Users\\[^\\\s]+\\"),  # privacy-lint: allow
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
}


def denied_terms() -> list[str]:
    if not DENYLIST.is_file():
        return []
    return [
        line.strip()
        for line in DENYLIST.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def mask(text: str) -> str:
    return f"{text[:3]}…({len(text)} chars)"


def findings(text: str, terms: list[str]) -> list[tuple[int, str, str]]:
    """(line number, what, masked match) for each private thing in `text`."""
    found = []
    lowered_terms = [t.lower() for t in terms]
    for number, line in enumerate(text.splitlines(), 1):
        if ALLOW_MARK in line:
            continue
        for what, pattern in PATTERNS.items():
            for match in pattern.finditer(line):
                value = match.group(0)
                if what == "email" and (
                    value.lower() in ALLOWED_EMAILS
                    or value.lower().endswith(("@example.com", "@example.org"))
                ):
                    continue
                found.append((number, what, mask(value)))
        lowered = line.lower()
        for term in lowered_terms:
            if term in lowered:
                found.append((number, "private term", mask(term)))
    return found


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout


def published_files() -> list[str]:
    """Tracked files plus untracked ones git would add: everything not ignored."""
    tracked = git("ls-files").splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    return sorted(set(tracked + untracked))


def read(path: str, staged: bool) -> str | None:
    """A file's text, or None for a binary or missing file."""
    try:
        data = (
            subprocess.run(
                ["git", "show", f":{path}"], cwd=REPO, capture_output=True, check=True
            ).stdout
            if staged
            else (REPO / path).read_bytes()
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    if b"\0" in data:
        return None
    return data.decode("utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--staged", action="store_true", help="check the index")
    args = parser.parse_args(argv)

    terms = denied_terms()
    paths = (
        git("diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines()
        if args.staged
        else published_files()
    )
    problems = 0
    for path in paths:
        text = read(path, args.staged)
        if text is None:
            continue
        for number, what, masked in findings(text, terms):
            print(f"  {path}:{number}: {what} {masked}")
            problems += 1
    if problems:
        print(
            f"  privacy lint FAILED — {problems} private value(s). Generalise the "
            "lesson into the skill, move the evidence to private/, or mark a "
            f"genuine false positive with '{ALLOW_MARK}'."
        )
        return 1
    scope = "staged files" if args.staged else f"{len(paths)} files"
    extra = f", {len(terms)} private terms" if terms else ", no local denylist"
    print(f"  privacy lint PASSED ({scope}{extra})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
