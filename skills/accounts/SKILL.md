---
description: Connect social accounts to ViewPrinter, see which are connected or need reconnecting, organise them into named groups, and read follower performance. Use when connecting an account, checking what is connected, fixing a disconnected account, or managing groups.
---

# Accounts and groups

## Seeing what is connected

`accounts_list` returns every account the user can post to, across all their
workspaces, with the workspace each belongs to and any groups it is in. The ids
it returns are what `posts_schedule` takes.

Start here. Assuming an account is connected and discovering otherwise at
schedule time wastes the whole composition.

## Connecting a new one

`accounts_connect` returns a link. **You cannot complete the connection** — it
needs the person's own session and their consent on the platform's site.

So: hand over the link, tell them to sign in and approve, and stop. Call
`accounts_connect` again afterwards and it reports the connected account. Do not
poll it in a loop; wait until they say they are done.

## Reconnecting

Accounts fall out of authorisation on their own — tokens expire, permissions get
revoked, platforms change their terms. `accounts_list` and `groups_list` both
report which accounts are in that state.

There is no repair tool. Reconnecting is the same `accounts_connect` flow, and it
is the user's to complete.

## Groups

A group is a **named set of accounts in one workspace**, so a post can name it
instead of listing ids.

- `groups_create` — names must be unique in the workspace, and are matched
  without regard to case. All members must share a workspace.
- `groups_update` — `account_ids` is the **full membership afterwards, not a list
  to add.** Whatever you send replaces what was there. To add one account, send
  the existing members plus the new one. Omit `account_ids` entirely to rename or
  re-describe without touching membership. Getting this wrong silently empties a
  group.
- `groups_delete` — removes the name and the membership only. The accounts stay
  connected, and posts already scheduled through the group are unaffected,
  because a post records accounts rather than the group.

**A post naming a group is refused outright if any member needs reconnecting.**
Check `groups_list` first — it reports the state of each member and how many need
attention. This is the single most common reason a well-formed post is rejected.

## Performance

`accounts_performance` gives followers, posts, total likes and following per
account, each with how far it moved over the period, ordered by followers.

Two honesty constraints worth respecting when reporting these numbers:

- **They are as of the last sweep, not live.** Every account carries the time it
  was measured. Quote that time rather than implying the number is current.
- **An unmeasured account has no metrics at all** — not zeroes. Do not render a
  missing measurement as "0 followers"; say it has not been measured yet.
