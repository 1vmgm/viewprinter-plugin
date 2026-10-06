# connecting: Only the user can finish it

## Priority: MEDIUM

## What goes wrong

The agent tries to complete a connection it cannot complete, or polls
`accounts_connect` in a loop waiting for something that needs a human.

## Account inventories and connection health

For a product inventory, compare `products_list` (when available) with the full
`accounts_list`; product membership alone can omit older or renamed accounts.
Use `groups_list` to check grouping. Report product-linked accounts separately
from likely related accounts outside it, and leave uncertain ownership explicit.
A suggestive handle alone does not establish that an account belongs to a brand.

A ViewPrinter product or group is not evidence of a Facebook–Instagram Page
pairing. If the live account schema has no linked-account field, report that
limitation. Confirm the pairing in Meta's Linked accounts setting when browser
inspection is authorized, or use a username/screenshot the user supplies and
record that source explicitly. Do not infer pairings from similar handles or
an equal number of Facebook and Instagram accounts.

For a live profile or branding edit, verify that the browser's selected account
is the same destination returned by ViewPrinter. Duplicate Pages can share a
name and avatar. On Facebook, an API Page ID may redirect to a different numeric
public-profile ID for the same Page; compare the resolved profile and admin
asset links, not numeric equality alone. If the logged-in account manages a
different same-named Page, report the distinction and resolve the intended
destination before editing. A successful browser login does not establish
access to the connected destination.

Preserve the returned `status` and inspect `refreshTokenExpiresAt` and
`scopeCoverage` alongside it. If an account says `active` but its recorded expiry
is in the past, report both facts and mark connection health unresolved. This is
not proof that publishing works or that the token is unusable: the metadata may
be stale. `needs_reauth` explicitly calls for reconnecting. Null expiry or scope
coverage means the tool did not report it; it does not prove permanent access or
complete permissions. Missing permissions may affect only some capabilities.

An inventory does not require a test publication or initiating OAuth. Include
the retrieval date, profile links, display names, and account IDs in any saved
baseline. The account listing does not expose bios, banners, or link-in-bio
content, so treat those as a separate branding audit. Do not infer profile-edit
capabilities from the ability to publish posts.

## The flow

`accounts_connect` returns a link. **You cannot complete the connection** — it
needs the person's own session and their consent on the platform's site.

Hand over the link, tell them to sign in and approve, and **stop**. Call
`accounts_connect` again afterwards and it reports the connected account.

**Do not poll.** Wait until they say they are done.

## Reconnecting is the same flow

Accounts fall out of authorisation on their own — tokens expire, permissions get
revoked, platforms change their terms. `accounts_list` and `groups_list` both
report which accounts are in that state.

There is no repair tool. Reconnecting is the same `accounts_connect` flow, and
it is the user's to complete.

## Context

- Start any posting work from `accounts_list`. Assuming an account is connected
  and discovering otherwise at schedule time wastes the whole composition.
