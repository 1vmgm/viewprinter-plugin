# destinations: One workspace, and a group is a snapshot

## Priority: CRITICAL

## What goes wrong

Three separate refusals arrive after the post is composed:

- Destinations spanning two workspaces. **A post must stay in one.**
- A group named when a member needs reconnecting. The post is refused
  **outright**, not partially — and this is the single most common reason a
  well-formed post is rejected.
- A group assumed to be a live link, so the user believes adding an account
  later will add it to a post already scheduled. It will not.

## What to do instead

Get ids from `accounts_list`, or name a group from `groups_list`. The two
combine, and duplicates across them collapse to one delivery.

**Check `groups_list` before naming a group.** It reports the state of each
member and how many need attention. Reading it costs one call; skipping it costs
the whole composition.

**A group is expanded at the moment you schedule.** It is shorthand for "these
members, now". If the user's intent is "always everyone in this group", say so
plainly rather than letting them assume it updates.

## Respect confirmed account roles

Before assigning existing creative to an account, check the user's current account-role
mapping and project routing memory. A similar handle, product name, active connection,
or an older proposed plan does not override a confirmed role such as UGC or memes.
Keep confirmed routes distinct from proposals and preserve the stable account IDs.
Use authorization already given; ask for a replacement handle only when it is missing.
When a named format is a subset of a mixed batch, state the exact format and count
being moved so the remaining formats are not silently reassigned.
If the user explicitly groups several formats into one account lane, carry all of
those formats together. An account called “UGC” can include adjacent formats; do
not narrow the user’s grouping to a technical `ugc-hook-demo` format identifier.

## Changing a group

`groups_save` finds the group by name. Its `account_ids` is the **full
membership afterwards, not a list to add.** Whatever you send replaces what was there. To add one account, send
the existing members plus the new one. Omit `account_ids` entirely to rename
(`new_name`) or re-describe without touching membership.

**Getting this wrong silently empties a group.** There is no error; the group
simply has fewer members than the user thinks.

## Context

- `groups_save` with a name that does not exist creates the group, and then
  needs `account_ids`. Names are unique per workspace, matched without regard
  to case, and all members must share a workspace.
- `groups_delete` removes the name and membership only. The accounts stay
  connected, and posts already scheduled through the group are unaffected,
  because a post records accounts rather than the group.
