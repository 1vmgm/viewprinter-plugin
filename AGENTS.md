# AGENTS.md

This repository is public. Everything in it ships to customers as the
ViewPrinter plugin.

## What belongs here

General skills any ViewPrinter customer can use, and the scripts and checks
that keep them working. What real use teaches belongs in the skills as a
general rule — "a carousel refuses a trial reel" — never as the case that
taught it.

A project's own voice, formats and accounts belong in that project's content
skill, which `content-production` helps the customer create. The plugin
carries the method, never the project.

## Naming a skill

Two lowercase words naming the work, not the product. The content pipeline is
`content-<stage>` — production, review, publishing, learning — and work outside
it names its subject: `account-profiles`. No `viewprinter-`
prefix; every client already namespaces a plugin's skills, as in
`viewprinter:content-review`.

The folder, the `name` in SKILL.md and `skill_name` in `evals/evals.json` are
the same string, and the validator fails otherwise. A new skill also needs its
entry in `SKILLS` in `scripts/release_files.py`, a row in content-publishing's
"The rest of this plugin" table, an executable `scripts/preflight.sh` and
`agents/openai.yaml`.

## What never does

Nothing from our own projects or anyone else's: brand or account names,
handles, people, account, post or page ids, private links, screenshots,
exports. Feedback notes, audits and account inventories go in `private/`,
which git ignores, or in the project's own repository.

## The check

`scripts/lint_privacy.py` refuses account and post ids, home paths, private
addresses and every term in `private/denylist.txt`. The commit hook runs it on
staged files — enable it once per clone with
`git config core.hooksPath .githooks` — and CI runs it on every push.

CI has no denylist, so names are only caught on a machine that has one: keep
it current. A genuine false positive is marked on its own line with
`privacy-lint: allow`.
