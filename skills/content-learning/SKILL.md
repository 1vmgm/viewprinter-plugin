---
name: content-learning
description: Learn from what was posted. Tie each published post back to the batch item, version and format that made it, compare its results fairly with the same account's other posts of a similar age, and decide per format whether to double down, vary or retire it, then carry that decision into the next batch. Use once posts have been out for a few days, when asked what is working or which format to make more of, and before planning the next batch.
---

# Content learning

Content production makes a format and a batch. Posting sends it out. This skill closes
the loop: it finds out what each format actually did, compares that fairly, and turns
it into the next decision. It is the step that makes content better over time instead
of just more of it.

It judges organic creative performance: reach, retention and engagement relative to
what the same account normally gets. It does not judge installs, sales or ad returns;
those need attribution and belong to the paid-growth skill or the user's own analytics.
Reading and reporting never authorize posting, editing posts or changing campaigns.

## 1. Link every publication when it goes out

A result is only useful if it can be traced to the exact version that produced it. So
record the link at the moment of scheduling, not weeks later:

```sh
python3 <skill-directory>/scripts/learn.py link --post-id <post> --account-id <account> \
  --batch <batch-id> --item <item-id> --version <n> --format <format-id> [--paid-support]
```

- The join key is the ViewPrinter post ID plus the account ID. Each destination is one
  line in a monthly log in the project's content memory,
  `history/publications/<YYYY-MM>.jsonl`. Records are immutable; an identical retry is
  accepted, a conflicting one is refused. Per-post files from earlier versions are still
  read; `learn.py compact` folds them into the logs. Earlier versions cannot read the
  logs, so use `--remove-originals` (which deletes the folded files) only once every
  install that reads this memory is updated. The folder's `.gitattributes` makes git
  merge the logs line by line for projects that commit them.
- Mark `--paid-support` when a post is promoted. Promoted posts count ad impressions as
  views, so they are kept out of organic comparisons and baselines.
- **Backfill** older posts from publishing receipts that name the post ID. Never match
  by caption or by "it looks like the same video": captions get rewritten and similar
  edits exist. If the only evidence is indirect, record it with a `note` saying how the
  match was made, or leave the post unlinked.

### Nothing linked yet

A project's first report often has nothing to compare, and `learn.py report` says so.
Tell the user, and summarize each account's recent normal from the saved `posts_list`
pages instead of giving a format verdict. Ask which past posts belong to which format;
link the ones the user attributes with `--note "user-attested"` and leave the rest
unlinked. From the next batch on, link every post when it is scheduled.

## 2. Collect a complete census

Use `posts_list` with the accounts and date window being reviewed, every relevant
`source`, and every `nextCursor` page. Start the window well before the oldest linked
post so its age bucket has peers, and include every account a linked post went to. Save
each raw response as JSON in a dated report folder under the project's content memory
(`reports/<date>/`), with the report it produced. A ranked sample (`rank_by`) is capped and cannot show what
was left out; use it for questions about the top, never as the census.

Keep the observation time. Counters are as of the last sweep, not live, and an
unmeasured destination has no metrics at all, which is not the same as zero.

## 3. Run the comparison

```sh
python3 <skill-directory>/scripts/learn.py report --posts <page1.json> --posts <page2.json> \
  --markdown <report.md> --json <report.json>
```

For each linked publication, the report finds the same account's other measured posts
on the same platform, in the same age bucket (under 1 day, 1–3 days, 3–7 days, 7–30
days, older) and the same mode (trial or regular), and compares against their median:
views, engagement per view, and watch time per view. Every post in the saved responses
counts toward baselines, linked or not; promoted posts never do. A post boosted after it
was linked, or one never linked at all, is only known to be promoted if you say so: pass
`--promoted <file.json>`, a list of post IDs (or `{postId, accountId}` objects) taken from
the ad platform's record of which posts it ran. It then summarizes each
format and suggests a decision. Posts that are pending, failed, missing from the saves or
not yet measured are listed separately.

Default rules (override with `--rules <file.json>`): a baseline needs 5 peers; a
decision needs 3 comparable publications at least 72 hours old; "double down" needs a
median of 1.5× baseline with two thirds above it; "retire" needs 5 publications at or
below 0.5× views and 0.8× engagement. Read [method](references/method.md) before
interpreting the numbers.

## 4. Decide per format

The report suggests; the user decides. Present the suggestion with its evidence and
what it would take to change it.

| Decision | Means | Next batch |
|---|---|---|
| **Double down** | The format beats its accounts' normal, consistently | More items that preserve its invariants; vary only the allowed dimensions |
| **Vary** | Mixed: some posts land, others don't, or one outlier carries it | Change one dimension at a time (hook, length, proof, cover) as a controlled test; keep the rest fixed |
| **Retire** | Consistently below normal on both reach and engagement | Stop producing it; keep the format record and the finding so nobody rebuilds it by accident |
| **Keep testing** | Too few, too young, or no fair baseline | Keep posting at the current pace; re-read at the next age bucket |

A single viral post is a reason to vary around it, not proof of a format. A format that
wins on reach but not engagement, or the reverse, is not a clean double down; say which
job it does.

## 5. Record and carry forward

- Write a finding event in content memory for each decision: the question, the report
  and saved responses used as evidence, the verdict, confidence, scope, and what would
  change it (`history/findings/`, via the content-production memory helper).
- Update the format: a new format revision when its definition changes, or its status
  when it is retired.
- Put the next read in `state/carry-forward.json` with a date: formats marked keep
  testing or vary get re-read when their posts reach the next age bucket.
- A conclusion that reaches beyond one batch (a platform pattern, a competitor, an
  audience shift) goes into the project's research notes with its date.
- Promote a lesson into a project skill only when it changes a repeatable decision.
  Project taste stays in project memory; this skill stays general.

## Boundaries

- Never add replays to a view counter or sum observations of the same destination. See
  the counter notes in the method reference and in the content-publishing skill.
- Keep platforms, trial and regular posts, and promoted and organic posts separate.
- Report what could not be measured instead of filling it with zeros.
- Views, reach and engagement do not establish installs or revenue.
