# reading-results: Measured when it was measured, and missing is not zero

## Priority: MEDIUM

## What goes wrong

A follower count is quoted as if it were live, or an account that has never been
measured is rendered as "0 followers" — which reads as failure rather than as
absence.

## Two honesty constraints

- **Numbers are as of the last sweep, not live.** Every account and post carries
  the time it was measured. Quote that time rather than implying the number is
  current.
- **An unmeasured account has no metrics at all** — not zeroes. Say it has not
  been measured yet.

## Per destination, not aggregate

`posts_list` reports numbers for each destination separately, because the same
post does not do the same numbers everywhere. Summing them into one figure throws away
the finding the user actually wants: which destination worked.

`accounts_list` with `metrics: true` gives followers, posts, total likes and
following per account, each with how far it moved over the period, ordered by
followers.

## Context

Read publication from each destination, not only the parent post. A parent may
still say `scheduled` while a destination reports `published` with its live URL.
Report queued, published, failed and unverified destinations separately. For a
trial reel, successful publication does not establish later automatic sharing
to followers. Compare trials with other trials of similar age; their initial
non-follower audience differs from an ordinary Reel's audience.

- Not every platform reports every metric. A metric a platform does not return
  is absent, not zero — the same rule as an unmeasured account.

## Public cadence versus private and unlisted uploads

Before assessing posting frequency or crowded time slots, establish each
YouTube destination's visibility. Unlisted advertising assets can share the
same channel and appear in `posts_list` alongside public uploads; they do not
represent the same organic feed schedule. A video URL, published status or
missing privacy field does not establish that it is public.

Join the exact post/account to its accepted request or an exposed saved setting.
Keep public organic, unlisted/private and unknown visibility separate in counts
and comparisons. If the read tool omits visibility, record the evidence used to
classify each exception. Do not call clustered ad-asset
uploads a public posting collision or move them merely to improve organic spacing.

## Comment authorship

When separating audience comments from the account's own replies, cross-check
`authorKind` with returned author identifiers and the connected account's identity.
A reply by the connected account can be misclassified as a person; a known matching
account username is still an owned reply. Exclude it from independent audience
responses, preserve raw totals, and report the mismatch with target/comment IDs for
a product fix. Do not silently treat a classification flag as ground truth.

## Disclosure-label audits

A missing disclosure field in `posts_list` is unknown, not disabled. Distinguish
three facts: the choice the caller submitted, the options the service saved and
sent, and the label the social platform displayed. Publication success alone
proves none of those label states. Use an accepted request or an exposed saved
setting to audit the caller's choice; use platform evidence for the visible label.

When tools omit these settings, report the limitation and record the capability
gap. How publishing works today does not prove the settings of every earlier
publication, or what the platform displayed.

## Draft targets and partial retention curves

A pending destination under a **draft** parent is held, even if its stored
scheduled time has passed. Separate held drafts from future queued deliveries
and overdue scheduled deliveries; consult the saved hold reason before calling
it a publication failure. Preserve the draft until the user's choice is resolved.

Before interpreting a derived retention percentage, compare it with the returned
curve, bucket duration and known video duration. A partial curve's midpoint is
not necessarily the video's halfway point. Preserve raw observations, flag a
derived-value inconsistency for a product fix, and omit that derived value from
the performance conclusion rather than silently treating it as measured truth.

## Keep handoffs synchronized with execution

After scheduling or moving destinations, regenerate any user-facing schedule or
asset handoff from verified post/account/time receipts and a current queue read.
Do not leave the earlier proposal's cadence, destinations or unresolved-label
wording beside assets the user is still reviewing. Show the verification time,
actual placement totals, partial final days, and routing splits. Distinguish
already-scheduled posts from future campaign reservations; active daily campaigns
are not proof those future posts have been created or will publish successfully.

Keep one canonical handoff path, update its downloadable bundle too, and refresh
the existing review tab after rewriting a static HTML file. Verify the rendered
heading and counts, because an open file tab can still show the old document.
A correct file on disk does not establish that the user is seeing the correction.

## Link to the exact ViewPrinter result

When a user wants ViewPrinter links, link the dashboard post dialog, using IDs
from `posts_list`: `https://viewprinter.tech/dashboard?post=<post.id>`. For a
specific account/platform result, add `&delivery=<target.id>` from that same
post. `delivery` is the target ID, not the social account ID or platform post ID.
The link opens inside the signed-in workspace; it is not a public share page.

Keep social `externalUrl` values as provenance. Do not substitute a similar
clip or guess a dashboard ID for an unmatched external/ad-platform post. Mark
that row as having no matched ViewPrinter post. Update saved report links as
well as the chat handoff.

`posts_list` returns external social URLs but no dashboard URL, so build the
dashboard link from the IDs as above rather than reusing an external URL.
