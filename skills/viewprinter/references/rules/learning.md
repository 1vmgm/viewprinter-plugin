# learning: Link each post to what made it, and compare it only with its own account's normal

## Priority: MEDIUM

## What goes wrong

- A format is called a winner because of one viral post.
- A two-day-old post is compared with a two-week-old one, a trial reel with an ordinary
  Reel, or one account's numbers with another's, and the wrong format gets dropped.
- A promoted post's ad impressions count as organic views and inflate the baseline.
- Weeks later nobody can say which version of a video a post was, so the result teaches
  nothing.

## Link every post when it is scheduled

Run this once for each destination `posts_save` returns, while the details are at hand:

    python3 scripts/learn.py link --post-id <post> --account-id <account> \
      --batch <batch> --item <item> --version <n> --format <format> [--paid-support]

- The post id plus the account id is the key. Each destination becomes one line in a
  monthly log, `history/publications/<YYYY-MM>.jsonl` in the project's
  `.viewprinter/content-memory`; the first link creates it, so run it from the project
  root or pass `--memory`. Agents working in parallel can link at the same time.
- Records are never rewritten: repeating the same link is fine, a different one is
  refused.
- Versions up to 1.4.0 wrote one file per destination and cannot read the logs. Those
  files are still read here; `learn.py compact` folds them into the logs, and
  `--remove-originals` then deletes each file whose identical record is logged. Run it
  only once every install that reads this memory is updated.
- Whether the logs are committed is the project's own git policy. The folder carries a
  `.gitattributes` so git merges them line by line: two branches that both link do not
  conflict.
- Use the format's ID from the project's format records (`formats/<id>/` in content
  memory), or the name the user already uses when there are none. A record's `aliases`
  fold old names into its ID in the report. `--paid-support` marks a post that will run
  as an ad.
- To backfill, use only receipts that name the post id. Never match posts to videos by
  caption or by how they look.

## Compare fairly

1. **Collect everything**: `posts_list` for the accounts involved, every source and
   every page, starting well before the oldest linked post so each age has peers. Save
   each page as JSON. A ranked list (`rank_by`) is a sample, not a census.
2. **List the promoted posts**: every post that ran as an ad, from the ad platform's own
   record, linked or not, as a JSON list of post ids.
3. **Run the report**:

       python3 scripts/learn.py report --posts <page1.json> --posts <page2.json> \
         --promoted <promoted.json> --markdown <report.md>

The report compares each linked post only with the same account's other measured posts
on the same platform, at the same age (under 1 day, 1–3 days, 3–7 days, 7–30 days,
older) and in the same mode (trial or ordinary), against their median: views, engagement
per view, and watch time per view. Promoted posts leave both the comparison and the
baselines. Posts not yet measured are listed separately, never counted as zero.

## Decide per format

The report suggests; the user decides.

| Suggestion | When | Next batch |
|---|---|---|
| Double down | Median at least 1.5x the accounts' normal, two thirds of posts above it | More of it, varying only what the format allows |
| Vary | Mixed, carried by one outlier, or strong on engagement but not reach | Change one thing at a time: hook, length, proof, cover |
| Retire | Five or more posts at half the normal views and weak engagement | Stop making it; keep the record so nobody rebuilds it |
| Keep testing | Fewer than three posts at 72 hours or older, or no fair baseline | Keep posting; read again at the next age |

One viral post is a reason to vary around it, not proof of a format. Say which job a
format does when it wins reach but not engagement, or the reverse.

## Context

- Know each counter before combining it. Whether a platform's view count includes replays
  has changed before; never add replays to views without checking. See `reading-results`.
- Changing the hook, song, cover and length together is exploration. A controlled test
  changes one thing.
- Views, reach and engagement do not show installs or sales.
