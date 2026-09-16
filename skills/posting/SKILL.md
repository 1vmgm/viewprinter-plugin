---
description: Schedule a social post to one or more connected accounts through ViewPrinter — checking platform rules first, then queueing, amending or cancelling it. Use when the user wants to post, schedule, draft, reschedule or cancel something on TikTok, Instagram, Facebook, YouTube or X.
---

# Scheduling a post

Five platforms can publish today: **TikTok, Instagram, Facebook, YouTube, X.**
Each has different rules about what a post may contain, and the server rejects a
post that breaks them rather than silently fixing it.

## Read the rules before composing, not after being rejected

Call `platforms_list` **first**, naming the platforms you intend to post to. With
no arguments it returns every platform with its accepted media kinds, counts and
caption limit. Naming platforms adds recommended sizes and durations, the
per-platform options, and the quirks that change how a post is treated.

This is cheaper than composing a post, having it refused, and guessing at why.

Three constraints are worth holding in mind because they eliminate whole plans:

- **A post is either a video or a set of images. Never both.** There is no
  arrangement of `media_ids` that mixes them.
- **YouTube cannot post images.** A YouTube destination needs a video.
- **X is the only platform that accepts a caption with no media.** Every other
  platform refuses a text-only post.

Do not hardcode caption limits or media counts from memory — they change per
platform and `platforms_list` is the source of truth.

## Choosing destinations

Get ids from `accounts_list`, or name a group from `groups_list`. The two
combine, and duplicates across them collapse to one delivery.

**Every destination must be in one workspace.** A post spanning two is refused.

**A group is expanded at the moment you schedule.** It is shorthand for "these
members, now" — not a live link. Adding an account to the group afterwards does
not add it to a post already scheduled. If the user's intent is "always everyone
in this group", say so plainly rather than letting them assume it updates.

**Check `groups_list` before naming a group.** A post naming a group is refused
outright if *any* member needs reconnecting, and the error arrives after you have
composed the whole thing. `groups_list` reports how many members are in that
state.

## Scheduling

`posts_schedule` records the intent and queues it. Nothing publishes during the
call.

- Omit `scheduled_at` to send as soon as possible; otherwise pass ISO 8601.
  Resolve relative times ("tomorrow at 9") against the user's timezone and state
  the absolute time back to them — a post going out a day early is not
  recoverable.
- `media_ids` order **is** the slideshow order.
- `platform_options` is keyed by platform. An unknown key is refused, not
  ignored, so check `platforms_list` for what each option does and where it
  applies.
- Pass `idempotency_key` and reuse it on retry. A retry without one is how a
  post goes out twice.

### Drafts: two different things share the word

- `draft: true` on the post **holds it in ViewPrinter.** Nothing is queued and
  nothing reaches any platform. `posts_update` with `draft: false` sends it.
- The per-platform `draft` option inside `platform_options` **uploads to the
  platform** for a creator to finish there.

These are unrelated. Confirm which the user means before choosing — the first
sends nothing anywhere, the second puts content on the platform.

## If scheduling is refused for the account

`posts_schedule` can come back saying publishing is not set up on the account.
Nothing was saved when that happens — the post does not exist in any partial
state, so there is nothing to clean up and nothing to tell the user is pending.

Relay the refusal as written and stop. **Do not offer to sell anything, do not
describe plans or prices, and do not go looking for a signup, trial or upgrade
link.** You are running inside somebody else's client, and turning a refusal
into a sales pitch is both unwelcome there and against the rules of every app
directory this plugin is distributed through.

Connecting accounts, uploading media and every read stay available regardless,
so keep working on whatever part of the request still functions rather than
treating the whole thing as blocked.

## After scheduling

`posts_list` shows every post with the state of each destination. Call it before
changing anything; `posts_update` and `posts_cancel` both take a `post_id` from
there.

**`posts_update` only works while every destination is still pending.** Once any
destination has started publishing the post is frozen — schedule a new one
instead of trying to amend it. Changing `scheduled_at` re-aims delivery; there is
no separate publish step.

**`posts_cancel` cannot recall what is already going out.** Destinations that
have not started are cancelled; any mid-publish come back in `still_going`.
Report that honestly rather than telling the user it was cancelled.
