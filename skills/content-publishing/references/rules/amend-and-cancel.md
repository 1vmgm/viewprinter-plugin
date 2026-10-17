# amend-and-cancel: What can still change, and what cannot be recalled

## Priority: HIGH

## What goes wrong

A post is reported as cancelled when part of it is already going out, or an
amendment is attempted on a post that is frozen and the failure is a surprise.

## Read first

`posts_list` shows posts with the state of each destination, or one post given
its `post_id`. Call it before changing anything; `posts_save` takes the
`post_id` from there, both to amend and to cancel.

## Amending

**The caption and destinations can only change while every destination is
still pending.** Once any destination has started publishing, only the time can
change — new words mean a new post. Passing `account_ids` or `groups` replaces
the destination list entirely.

Changing `scheduled_at` re-aims delivery. There is no separate publish step.

## Replacing a slot without losing the displaced post

When making room for new content, preserve the displaced approved post's
publishing commitment. A held draft, cancellation, saved media file or backlog
note is not a reschedule. Choose a concrete future date that fits the queue and
campaign reservations, then change the original post's time. Preserve its media,
caption, destinations and accepted platform settings.

If the user says displaced posts must be rescheduled, treat that as an invariant
across every replacement in the task. Do not substitute a hold because the next
few days are full; find the next valid slot. A move is complete only after both
the new placement and the displaced original read back with their intended
accounts and future times. Reconcile the full before/after inventory, recording
old and new times beside exact post IDs. Say "rescheduled" only for those verified
moves. Retiring or replacing the content itself is a distinct decision and must
be covered by the user's instruction.

When auditing a suspected missed post, distinguish approved displaced content
from original review drafts, platform-native drafts, explicitly paused content,
failed deliveries and cancelled copies whose replacements are already queued or
published. Match by post/account and media or recorded version identity, not by
caption alone. Recover confirmed omissions under the existing authorization;
keep uncertain cases explicit instead of silently publishing duplicates.

## Planning a queue reflow

When the user wants a plan before changes, prepare exact new placements and old/new
post times locally; do not save live drafts or reschedule posts merely to validate the
proposal. Count active campaign reservations once, including slots not generated yet.
An account-filtered queue can hide other targets, so read each proposed moved post in
full before deciding its scope.

Preserve the user's priority and seasonal constraints through the entire cascade.
Give every displaced post a concrete later slot, check spacing and capacity there,
and retain weekday-sensitive wording when selecting its date. Rank measured creatives
through content-learning; label young or unmeasured editorial choices rather than
calling them failed. Before an authorized execution, refresh the queue and move the
cascade's tail first so a weaker post does not consume the next stronger one's slot.

## Priority cascades under account caps

Use this workflow when adding stronger content would exceed a user's posting cap.
Load the project's current caps, timezone, spacing, protected campaigns or tests,
and account roles. These are project strategy, not product defaults. A one-run
secondary-account instruction stays in that run's plan unless the user makes it
standing policy.

Inventory the requested day and enough later days to give every displaced item a
valid destination. Reconcile paginated posts with campaign reservations, counting
already generated campaign posts only once. If returned ordering differs from the
requested sort, sort the complete local inventory by its timestamps; do not infer
empty days from a partial page.

For a priority cascade, use evidence from each creative or its verified published
cross-post, with the account, age, trial mode and measurement time attached. Do not
call a whole format weak or treat unmeasured work as zero. Compare within account
and age cohorts before using another platform's results as a planning signal.
A moved item takes the first suitable later slot occupied by a clearly weaker item;
continue until the remaining item has an open slot. Do not push a stronger item to
the queue's end while weaker work stays ahead. Preserve seasonal deadlines,
date-sensitive copy and protected tests throughout; do not create extra moves when
an open slot or inconclusive evidence makes them unnecessary.

The reviewable plan names each creative/version and media identity, complete account
list, old and new local time with timezone, UTC time, native caption/settings changes,
capacity and spacing before/after, and why each displacement is warranted. Distinguish
measured evidence from an editorial prediction. A plan-only request creates no remote
drafts or queue mutations. Existing authorization remains valid; do not add a new
approval gate when the user already authorized execution.

Execute an authorized plan from the tail, rereading the affected posts and their
slots immediately before each write. Pause the dependent chain on a refusal, race
or uncertain result. Verify every move before advancing; record confirmed moves
so a retry resumes without duplication. Finish with a complete inventory
reconciliation: every displaced creative has a scheduled replacement, every new
placement is verified, and no affected account-day exceeds its cap.

## Moving existing posts to another account

Re-read each post without account filters, then replace its complete destination list.
For a move within one platform, preserve the existing post, media, caption and accepted
platform settings. Resolve the replacement account's queue and campaign reservations;
state any necessary time adjustment before saving. Existing approval of disclosure
choices carries forward for the same posts. Do not recreate posts merely to change
accounts, and do not release older held copies of the same creative.

When a project forbids duplicate content across its accounts, an account transfer
must leave exactly one intended placement for that creative. Check the source and
destination accounts' published, publishing, scheduled, draft and relevant failed
or cancelled history, following every page. Match media IDs, checksums and recorded
creative/version aliases, not captions alone: changing a caption, cover, filename
or upload ID does not make the video new. A prior publication on either account
cannot be undone by moving its queued twin. Do not transfer that creative to the
other account; select another eligible item. Keep unresolved identity checks explicit.

Prefer amending the complete destination list on the original pending post. If the
intended transfer also changes an immutable platform option, such as trial versus
regular mode, a replacement may be necessary. Make that exception and the exact
mode explicit in the plan. Under authorization, create and verify its future
replacement first, then remove only the superseded pending destination, preserving
other destinations. Never withdraw the original before its replacement is confirmed.
Before either can publish, verify the original destination is absent or cancelled
and there is exactly one active intended placement. If removal fails, stop the
incoming cascade and resolve the conflicting copies before their delivery times;
do not claim the transfer complete. Record the old-to-new post mapping so queue
counts and delivery history treat this as a preserved commitment, not extra content.

Checkpoint the removed account as `canceled`, checkpoint and link the new account, and
verify the full returned destination list. The current API removes dropped target rows.
Consequently, an old publication link can survive even though `posts_list` no longer
returns that target. Never infer a removal from an account-filtered or partial response.

For an ongoing local review, import the complete unfiltered readback with its
observation timestamp and `readScope: {completeTargets: true, accountFilter: false,
postIds: [...]}`. The content-review delivery helper can then mark a missing
old destination **removed**, with evidence, without inventing an API cancellation.
Update the intended plan separately: retain the old target as withdrawn with the
reason for the authorized move, and add the replacement workspace/account. Rebuild
the same format gallery. An omitted target in a partial page or account-filtered
read is not removal evidence; older snapshots cannot override newer observations.

## Cancelling

`posts_save` with the `post_id` and `cancel: true`. **It cannot recall what is
already going out.** Destinations that have not started are cancelled; any
mid-publish come back in `still_going`.

Report that honestly. "Cancelled" when two of five are already live is a lie the
user will discover on their own feed.

## Stopping campaigns for one account

Campaign tools exist only on accounts with campaigns turned on. When `campaigns_list`
is available, read it and identify the account by its stable id. If a campaign
also serves other accounts, use `campaigns_save` with the complete remaining
`account_ids` to remove only the requested account. Pause a campaign whose only
destination is the requested account. Do not pause unrelated destinations or
delete campaign history merely to stop one profile.

When the campaign tools are not available, say so and tell the user to change the
campaign in ViewPrinter. Still audit the queue below: `posts_list` with
`source: ["campaign"]` lists the posts campaigns made.

Campaign membership changes do not replace a queue audit. Read `posts_list`
for that account with scheduled and draft statuses, follow every cursor, and
identify the campaign-sourced posts. An account-filtered response can show only
the matching destinations of a shared post. **Re-read each affected `post_id`
without filters before deciding how to stop it.**

- If the post has only the requested destination, use `cancel: true`.
- If every destination is still pending and other accounts should continue,
  use `posts_save` with the complete remaining `account_ids`. This removes the
  unwanted delivery while preserving the shared post for the other accounts.
  Omit caption, time and draft fields; read them back to confirm preservation.
- If the post is already in progress, respect the amendment limits above.
  Do not use whole-post cancellation to silently stop other accounts. Report
  any destination the available tools cannot stop within the authorized scope.

Finally re-read campaigns (when available), the account's queue and the changed post ids. Report
campaign membership removed, deliveries removed/cancelled and anything already
in flight separately. Published posts stay in place. Record each change with
`python3 <skill-directory>/scripts/learn.py checkpoint`, run from the project folder (see
`learning`), so a later resume does not recreate or resend it:
`--status canceled` on every account removed from a post and `--status amended` on
every account that keeps it, with the post id and the before/after account ids in
`--details <file.json>` (or `--details -` with the JSON object on stdin). Pass the post's batch id as `--batch`, or for a campaign-sourced post the
campaign id. `--item` and `--version` may be left out: the event joins the post's
placement by post id.

## Context

- Deleting media a pending post depends on is a different way to break a post.
  `media-upload` has the rule for deleting.
