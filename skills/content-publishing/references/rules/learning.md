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

    python3 <skill-directory>/scripts/learn.py link --post-id <post> --account-id <account> \
      --batch <batch> --item <item> --version <n> --format <format> [--paid-support]

- The post id plus the account id is the key. Each destination becomes one line in a
  monthly log, `history/publications/<YYYY-MM>.jsonl` in the project's
  `.viewprinter/content-memory`, which the first link creates. Run it with the project
  folder as the working directory, or pass `--memory <project>/.viewprinter/content-memory`;
  it refuses to start memory inside the installed skills, where an update would erase it.
  Agents working in parallel can link at the same time.
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
- To backfill, use receipts that name the post id, or the user's own attribution recorded
  with `--note "user-attested"` (see content-learning). Never match posts to videos by
  caption or by how they look.

### Keep review galleries synchronized

When the creative belongs to an ongoing format in the review workspace, keep its canonical
review and exact item/version IDs. Record the complete intended workspace/account
plan in each item's `distribution.targets`, including authorized destinations that
have not yet saved successfully. A successful subset must not look like a complete
plan. Preserve rejected or withdrawn destinations with an explicit reason.

Store finalized native `captions` (and YouTube title), copyRevision, media hash and
approval/finalization evidence with that version. After linking every destination,
save dated `posts_list` readbacks and run the content-review skill's
`review_delivery.py`, then `review_gallery.py`. See its workspace reference for the
manifest and receipt schemas. Keep accepted request fields separately when readback
does not expose them; never label those fields independently verified.

The local review finishes at scheduling. Refresh it after the accepted handoff or an explicitly requested creative/copy revision; do not keep it polling publication status. Every required destination must have an accepted receipt before the item is Scheduled. A published receipt can establish past scheduling, but the review has no Posted stage. Later delivery failures and performance are managed in the ViewPrinter product, not reopened as review tasks. Preserve accepted scheduling evidence and original observation times when importing later delivery records for learning.

New creative versions, changed copy/media or added required destinations need their own matching handoff. A new unscheduled batch makes its existing format active again. Archive is an optional local organization action, independent of scheduling; it preserves source files and remote posts. This bookkeeping does not authorize additional publication, remote group changes or deployment.

## Compare and decide in content-learning

Reading which posts and formats worked belongs to the
[content-learning](../../../content-learning/SKILL.md) skill. It runs `learn.py report`
over saved `posts_list` pages, compares each linked post only with the same account's
posts of the same platform, age and mode, leaves promoted posts out, and suggests per
format whether to double down, vary or retire it. The report suggests; the user decides.
One viral post is a reason to vary around it, not proof of a format.

## Context

- Know each counter before combining it. Whether a platform's view count includes replays
  has changed before; never add replays to views without checking. See `reading-results`.
- Changing the hook, song, cover and length together is exploration. A controlled test
  changes one thing.
- Views, reach and engagement do not show installs or sales.

## Inspect the creative behind the numbers

For the extraction record and production handoff, read content-learning's
[creative anatomy](../../../content-learning/references/creative-anatomy.md).

Match the published media to its source export before diagnosing why it worked. Post
captions are not on-screen hooks, and a current preferred generator is not evidence of
which model made an older winner: use the source requests or mark it unknown.

A video-analysis model can extract candidate text and visual events. When possible,
withhold performance counts during that first pass, then check its observations against
the exported frames and edit timeline. Estimated timestamps and inferred viewer motives
are not measurements. Compare both strong posts and relevant weaker peers; an observed
creative difference is a hypothesis until a fair test isolates it.
