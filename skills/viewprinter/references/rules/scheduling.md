# scheduling: Get approval, state the absolute time, and do not post twice

## Priority: CRITICAL

## What goes wrong

- A relative time is passed through unresolved and the post goes out a day
  early. **That is not recoverable.**
- A retry after a lost response sends the post twice.
- Success is reported before the tool returned, so the user believes something
  is queued that is not.

## Before scheduling

Make sure the content, destinations and time are covered by the user's approval.
Use approval already given in the conversation; ask only for missing or changed
details. **State the resolved time and destinations before the action.**

Publishing cannot be recalled by these tools.

## Calling it

`posts_schedule` records the intent and queues it (unless `draft: true`). A
queued post can begin publishing immediately.

- Omit `scheduled_at` to send as soon as possible; otherwise pass ISO 8601.
  Resolve relative times ("tomorrow at 9") against the user's timezone and state
  the absolute time back to them.
- **Pass `idempotency_key` and reuse it on retry.** A retry without one is how a
  post goes out twice.
- `media_ids` order **is** the slideshow order.
- `platform_options` is keyed by platform. An unknown key is refused, not
  ignored — check `platforms_list` for what each option does and where it
  applies.

## Afterwards

**Report success only after the tool returns**, and distinguish queue acceptance
from delivery. A post that is queued has not yet gone out.

## Context

- Applies to releasing a held draft as well as to a fresh post: `posts_update`
  with `draft: false` sends it, and that needs the same approval.
