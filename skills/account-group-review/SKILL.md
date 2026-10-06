---
name: account-group-review
description: Audit and iterate a related group of social accounts in ViewPrinter. Prepare a persistent account brief and owner handoff with profile copy, branding assets, safe areas, link placements, and dated feature eligibility research. Use for account-group setup, profile reviews, rebrands, or checking which profile features a group can use; posting and queue changes use the viewprinter skill.
---

# Account group review

Turn a set of related accounts into a reusable, reviewable group brief. A group can
contain any subset of the supported platforms, multiple accounts on one platform,
and accounts shared with other groups. Do not create missing accounts just to fill
a four-platform checklist.

## Resolve the group

Read the user's existing account-role map and previous handoff before proposing
changes. Read the adjacent `viewprinter` skill and its `destinations` and
`reading-results` rules before using ViewPrinter tools.

Use `accounts_list`, `groups_list`, and `platforms_list` for the relevant platforms.
Match **workspace + account ID**, then retain the exact handle and profile URL.
Similar names, punctuation variants, and two Pages with the same display name are
different destinations. A confirmed user role takes priority over an older proposal.

Distinguish a local review group from a saved ViewPrinter destination group. Record
the remote group ID/name if one exists. Review work alone does not create or replace
remote membership. Reuse authorization already given for any requested changes.

## Load only the relevant account types

Platform is one dimension; native account subtype and feature entitlement are others.
An OAuth connection variant is not proof of a platform entitlement.

| Platform | Read for profile fields, links and eligibility |
|---|---|
| Instagram | [instagram.md](references/instagram.md): personal, creator, business |
| TikTok | [tiktok.md](references/tiktok.md): native account type and business entitlements |
| Facebook | [facebook.md](references/facebook.md): Page versus personal/professional profile |
| YouTube | [youtube.md](references/youtube.md): channel ownership and feature eligibility |

Initial coverage is these four platforms. Other platforms should be recorded as
unresearched until a sourced module is added, without blocking the rest of the group.

## Research and persist

Use [research.md](references/research.md) when adding or refreshing platform facts.
Store reusable facts, source URLs, source publication/update dates, observation dates,
scope and uncertainty in this skill's platform modules and `references/research.json`.
Keep account handles, branding choices, assets, schedules and approvals in the project.

Inspect public profiles and native settings when available. Missing biographies,
links or feature state in `accounts_list` mean **unknown**, not empty or disabled.
Record connection health, permissions and native feature access separately. A source
rule establishes possible eligibility; only account evidence establishes enabled state.
Do not collect identity documents, login credentials or verification codes in the brief.

## Prepare the review

Use [brief.md](references/brief.md) for the portable JSON shape. Keep a stable
`group.json` and `review.html` per group, with immutable revision snapshots and original
feedback. Each account needs current/proposed fields, exact ID/link, role, shared use,
feature states, next actions and evidence dates. Omit irrelevant platforms and fields.

Deliver real downloadable assets when branding is in scope. Reuse approved assets
when suitable; preserve their provenance. Measure exports, preview avatars as small
circles, and preview covers with clearly labeled crop assumptions. A local crop
simulation is not a saved platform preview. Separate profile branding safe areas from
video overlay safe areas; official ad guides are not universal organic-post guarantees.
Call out shared-account conflicts before proposing a separate identity for that account. Use one canonical `identityRef` for shared account copy, application state and assets; see [brief](references/brief.md#shared-account-identity). Rebuild every referencing group after a shared revision.

Generate the account review with the bundled Python helper (no dependencies):

```sh
python3 scripts/build_review.py --manifest /path/to/group.json --output /path/to/review.html
```

Use the shared dark-mode presentation and purple ViewPrinter accent; keep artwork colors intact and verify readable contrast and narrow layouts.

It creates a static review with per-field copy buttons and account links; it does not
apply anything. If the ViewPrinter content review hub is installed, read that plugin's
review instructions, register this same HTML as `account-group`, and reuse its server under Account Groups. Give the manifest `reviewHub.kind: account-group` and a stable group ID. Link content formats to this group; profile reviews remain secondary to content production. Otherwise
serve the output with the project's existing local preview workflow. Keep approvals
in conversation, not a second HTML form. Verify the served page, asset/download paths,
copy behavior and narrow layout before handoff. Test the HTTP status of every local
download and supporting link, not only image decoding. The shared hub restricts file
types and page roots: do not assume JSON, Markdown, CSV, ZIP, or a sibling HTML path
is served. The bundled renderer embeds the group-brief download; use registered hub
links for sibling reviews and HTML for supporting material. Preserve the hub allowlist.

## Iterate and apply within scope

Identify feedback by stable account reference and revision. Archive the previous
manifest before editing; preserve approved fields and unrelated group members.
Research updates do not invalidate creative approvals or authorize public edits.
After an authorized profile edit, reopen the public profile and verify saved copy,
links and crops. Mark fields `applied-unverified` until observed; retain before/after
evidence. Refresh connection/profile URLs after handle changes.

For cadence recommendations, inspect existing queue and campaign reservations with
timestamps, especially on shared accounts. Creative approval, queued delivery,
published delivery and profile application are separate states. Use `viewprinter`
for posting, remote-group writes or queue mutations; never imply this handoff queued
content. Finish with the review link, proposal/application state and specific gaps.
