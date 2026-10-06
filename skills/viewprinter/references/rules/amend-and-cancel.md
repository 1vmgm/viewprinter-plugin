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

## Moving existing posts to another account

Re-read each post without account filters, then replace its complete destination list.
For a move within one platform, preserve the existing post, media, caption and accepted
platform settings. Resolve the replacement account's queue and campaign reservations;
state any necessary time adjustment before saving. Existing approval of disclosure
choices carries forward for the same posts. Do not recreate posts merely to change
accounts, and do not release older held copies of the same creative.

Checkpoint the removed account as `canceled`, checkpoint and link the new account, and
verify the full returned destination list. The current API removes dropped target rows.
Consequently, an old publication link can survive even though `posts_list` no longer
returns that target. Never infer a removal from an account-filtered or partial response.

For an ongoing local review, import the complete unfiltered readback with its
observation timestamp and `readScope: {completeTargets: true, accountFilter: false,
postIds: [...]}`. The content-production delivery helper can then mark a missing
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

Read `campaigns_list` and identify the account by its stable id. If a campaign
also serves other accounts, use `campaigns_save` with the complete remaining
`account_ids` to remove only the requested account. Pause a campaign whose only
destination is the requested account. Do not pause unrelated destinations or
delete campaign history merely to stop one profile.

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

Finally re-read campaigns, the account's queue and the changed post ids. Report
campaign membership removed, deliveries removed/cancelled and anything already
in flight separately. Published posts stay in place. Record each change with
`scripts/learn.py checkpoint`, so a later resume does not recreate or resend it:
`--status canceled` on every account removed from a post and `--status amended` on
every account that keeps it, with the post id and the before/after account ids in
`--details`. Pass the post's batch id as `--batch`, or for a campaign-sourced post the
campaign id. `--item` and `--version` may be left out: the event joins the post's
placement by post id.

## Context

- Deleting media a pending post depends on is a different way to break a post.
  See `media-upload` for the delete warning.
