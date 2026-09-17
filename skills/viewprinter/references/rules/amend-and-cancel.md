# amend-and-cancel: What can still change, and what cannot be recalled

## Priority: HIGH

## What goes wrong

A post is reported as cancelled when part of it is already going out, or an
amendment is attempted on a post that is frozen and the failure is a surprise.

## Read first

`posts_list` shows every post with the state of each destination. Call it before
changing anything; `posts_update` and `posts_cancel` both take a `post_id` from
there.

## Amending

**`posts_update` only works while every destination is still pending.** Once any
destination has started publishing, the post is frozen — schedule a new one
rather than trying to amend it.

Changing `scheduled_at` re-aims delivery. There is no separate publish step.

## Cancelling

**`posts_cancel` cannot recall what is already going out.** Destinations that
have not started are cancelled; any mid-publish come back in `still_going`.

Report that honestly. "Cancelled" when two of five are already live is a lie the
user will discover on their own feed.

## Context

- Deleting media a pending post depends on is a different way to break a post.
  See `media-upload` for the delete warning.
