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

For a bulk instruction that refers to existing work, reconcile the approved,
unscheduled inventory across the conversation's batches before choosing the
count. Keep source batch, item and final version with every placement; the most
recent gallery section is not necessarily the complete requested scope. State
the resolved inventory and use the authorization already given.

## Promotional-content and AI labels require an explicit choice

**Always ask whether the user wants promotional-content and AI labels before
publishing or scheduling, unless their explicit answer already covers this
post or batch.** These are separate choices. Approval to post, an account's
business status, a brand mention, generated media, or an old agent's payload
is not consent to enable them.

This applies to TikTok `brandOrganicToggle` (own-brand promotion),
`brandContentToggle` (paid partnership), and `isAigc` (AI-generated content),
and Instagram `isAiGenerated`, plus equivalent options exposed by
`platforms_list` on other platforms. Explain the applicable choices in plain
language; do not bundle paid partnership with own-brand promotion.

Ask, for example: "For this batch, do you want the own-brand promotional label
on TikTok? Separately, do you want AI-generated labels on TikTok and Instagram?"
Ask about paid partnership when applicable. Wait for the answer; silence or a
preselected UI option is not consent. One explicit answer can cover the named
batch and platforms; do not ask again within that approved scope.

Only enable a flag after an explicit opt-in. If the user declines an optional
label, omit its parameter rather than inheriting `true` from an example,
template, prior post, or draft. Check saved options before releasing a draft;
if the tools cannot inspect or change them, resolve that before sending it.
Do not add disclosure wording to captions or overlays without approval either.

If current platform rules require a disclosure, explain the requirement and
ask how the user wants to proceed. Keep that destination held until resolved;
do not silently enable the flag or promise that omission prevents labels the
platform applies itself. Record the user's choices with the publishing request.

## Calling it

`posts_save` without a `post_id` records the intent and queues it (unless
`draft: true`). A queued post can begin publishing immediately.

- Omit `scheduled_at` to send as soon as possible; otherwise pass ISO 8601.
  Resolve relative times ("tomorrow at 9") against the user's timezone and state
  the absolute time back to them.
- **Pass `idempotency_key` and reuse it on retry.** A retry without one is how a
  post goes out twice.
- `media_ids` order **is** the slideshow order.
- `platform_options` is keyed by platform. An unknown key is refused, not
  ignored — check `platforms_list` for what each option does and where it
  applies.

## Instagram trial reels

### Check the account, not just the option

`platforms_list` reporting `trialReel` means ViewPrinter supports the option;
it does not establish that a particular Instagram account can use it. An
active connection and content-publishing permission do not establish trial
eligibility either. This matters especially for a newly connected account.

Check the current "About trial reels" guidance in the Instagram Help Center
for public-account, account-type, follower and recommendation requirements.
Follower thresholds can change; do not treat a remembered number or secondary
report as a verified current rule. Account metrics may be stale or absent;
missing followers are unknown, not zero.

Before a bulk trial rollout on an account without known trial access, look for
an explicit account eligibility result, or confirm the Trial option in its
Instagram sharing screen. If neither is available, report eligibility as
unverified. A held ViewPrinter draft validates the request, not Instagram's
acceptance. Any limited publishing check still needs authorization; if it is
refused, preserve the error and stop the dependent rollout. Never silently
substitute regular Reels. A successful trial on one account proves nothing
about another account's eligibility.

### Preserve the audience and promotion choice

When the live capabilities and connected schema expose `trialReel`, preserve
the user's chosen audience and promotion mode:

- `platform_options.instagram.trialReel: MANUAL` keeps a trial until the creator
  chooses to share it with everyone.
- `SS_PERFORMANCE` permits Instagram to share the trial with followers if it
  performs well. This is organic distribution, not a paid boost, and requires
  approval for that broader sharing.

Confirm current applicability with `platforms_list`; do not assume every media
type can be a trial. Omitting `trialReel` creates an ordinary Reel, and
`shareToFeed: false` is not a substitute. Never publish an ordinary Reel merely
to test whether the trial option works. For schema mismatches, follow
`platforms-first.md` and validate a held draft before releasing it.

Keep disclosure-label choices separate from trial promotion. Record the exact
options submitted. A published response alone does not prove trial mode or
later sharing to followers; use the accepted request for the former, and report
the latter as unknown unless the current tools explicitly expose that state.

## Afterwards

**Report success only after the tool returns**, and distinguish queue acceptance
from delivery. A post that is queued has not yet gone out.

For a batch, record a checkpoint after each successful save and readback, before
starting the next placement. Run it from the project folder (see `learning`):

    python3 <skill-directory>/scripts/learn.py checkpoint --batch <batch> --item <item> --version <n> \
      --account-id <account> --key <idempotency-key> --post-id <post> \
      --status saved [--details <file.json>|-]

Statuses are `held`, `saved`, `verified`, `amended`, `canceled` and `failed`. Pass the
idempotency key on every event: it is how a failed save is matched to the retry that
succeeds. Each event is one line in the batch's log, `history/posting/<batch>.jsonl`,
never a file per post or destination. `--details` carries only what a resume needs: the accepted
settings `posts_list` does not return, or the fields a readback verified. Do not keep
whole `posts_list` pages per destination. A later refusal does not roll back earlier
successes: run `learn.py checkpoints --batch <batch>` and reconcile it with the live
queue before reporting the saved count or retrying. Compare complete creative/version
IDs and idempotency keys; similarly named A/B variants are not the same request.
Never change a key to force a retry past a duplicate warning.

Keep the returned post id and each destination's account id with what was posted:
the file, its version and the batch it came from. A result can only be traced back
to the version that earned it if that record is made now: `<skill-directory>/scripts/learn.py link`,
described in `learning`.

Separate accepted request settings from independent readback evidence. Verify
the fields `posts_list` actually returns, and keep the exact accepted value in the
saved checkpoint's details for settings it does not expose, such as a cover or
disclosure flag. Do not say
an unreturned setting was read back. Report a requested but unsupported setting
as a capability gap, preserving the user's choice while unaffected placements
continue; omission is only acceptable when their instructions cover it.

## Context

- Applies to releasing a held draft as well as to a fresh post: `posts_save`
  with its `post_id` and `draft: false` sends it, and that needs the same
  approval.
