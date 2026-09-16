# Where this skill goes, and how to change it everywhere

One product, one set of guidance, five places that want it in a different
shape. This is the map, so a correction lands everywhere rather than in the
place you happened to be looking.

**`skills/` is the source.** Edit there. Everything else is generated from it
or published from it, and anything you write directly into a channel is a
second copy that will quietly disagree with this one. That has already
happened once: the first ClawHub release was a separately written fourth
skill, it was the weakest of the four, and its source was deleted while the
listing stayed live.

## The channels

| Channel | What it gets | Update by | Needs |
| --- | --- | --- | --- |
| **Claude Code plugin** | `skills/` directly — three skills | pushing to `main` | nothing |
| **ClawHub** | built package, one SKILL.md + references + evals | `clawhub skill publish` | ClawHub login (GitHub, age-gated) |
| **claude-plugins-community** | the marketplace listing | PR to the marketplace repo | — |
| **OpenAI ChatGPT app** | a zip uploaded to the submission form | re-upload on the next version | dashboard login |
| **LobeHub** | nothing — **blocked** | — | repo access we declined |

### Claude Code plugin

`skills/{posting,media,accounts}/SKILL.md`, loaded by `.claude-plugin/plugin.json`.
No build, no publish: what is on `main` is what users get.

### ClawHub

Published as `@1vmgm/viewprinter-social-manager`.

```bash
node clawhub/build.mjs
npx clawhub skill publish clawhub/dist/viewprinter-social-manager \
  --slug viewprinter-social-manager --owner 1vmgm --version <next> \
  --changelog "..." --categories automation \
  --topics viewprinter,tiktok,instagram,scheduling
```

`build.mjs` copies the three skills into `references/` and strips their
frontmatter — that frontmatter is Claude Code's routing metadata, and inside
the package it would be a second description competing with the real one.
`dist/` is ignored; never edit it.

Things learned the hard way:

- **`--dry-run` does not validate the owner.** It accepted a handle that does
  not exist. A real publish is the only test.
- **No delete in the CLI.** The web UI has one under Settings; the CLI has
  only rename, merge and `--migrate-owner`.
- **Every version is scanned.** 1.1.0 failed with eight findings, four of them
  from a single generated HTML comment that read as prompt injection. Do not
  put instructions in comments inside the package.
- **The scanner reads the description as a promise.** It flagged undeclared
  media deletion and workspace-wide listing because the description only
  mentioned posting. If the skill gains a capability, say so in the
  description in the same commit.

### OpenAI ChatGPT app

The Skills tab of the submission form takes a zip. The version uploaded on
2026-09-15 came from a folder that no longer exists, so **it is stale** — it
predates the refusal rule and the connection instructions. Nothing to do while
a review is live; on the next submission, zip `clawhub/dist/…` rather than
building a third variant.

### LobeHub — blocked, on purpose

`lhm plugin publish` and `lhm skill publish` both refuse without a verified
GitHub account, and connecting asks for repository access. Declined 2026-09-16:
a directory listing is not worth read access to every repo. Revisit only if
they ship a GitHub App with per-repository selection.

`lhm plugin init --url <server>` does work and generates a manifest, but it
reads the description from a local `package.json`, not from the MCP server.

## When the guidance changes

1. Edit the relevant file under `skills/`.
2. Push. Claude Code users have it.
3. `node clawhub/build.mjs` and publish a new ClawHub version.
4. If the change alters what the skill can *do* rather than how it does it,
   update the description in `clawhub/SKILL.md` too — the scanner compares them
   and so does every reviewer.
5. Leave a note in the submissions ledger
   (`.claude/search-insights-memory/history/submissions.json` in the main repo)
   so the next person knows which channels are current.

## What must never drift

Two rules exist in more than one place because they have to survive a reader
who loads only one file. If either changes, change it in **all** of them:

- **Publishing is irreversible, and `media_delete` erases bytes.** Confirm both
  explicitly. In `clawhub/SKILL.md` and `skills/posting`, `skills/media`.
- **A refusal is not a sales pitch.** When publishing is not enabled on an
  account, relay the refusal and never mention plans, prices, trials or
  upgrades. In `clawhub/SKILL.md` and `skills/posting`. This one is not
  optional: it is what the ChatGPT app was rejected for on 2026-09-15.
