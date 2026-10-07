---
name: viewprinter-social-manager
description: >-
  Use for work through a connected ViewPrinter account and the content around it:
  scheduling or publishing a post to TikTok, Instagram, Facebook, YouTube or X; uploading,
  describing, listing or PERMANENTLY DELETING media held in ViewPrinter; amending or
  cancelling a post that has not gone out; managing account groups and account profiles;
  reading follower and post performance and linking each post to the format that made it;
  and making content before it is posted — developing formats, producing batches and
  presenting them for review in a local workspace. Two capabilities are destructive and
  irreversible: publishing to a real public account, and media_delete, which erases a
  stored file and its bytes. Listing media or posts reads everything in the user's
  ViewPrinter workspaces. Publishing and account tools require ViewPrinter to be connected
  — do NOT use them to schedule anything anywhere else, or for a platform ViewPrinter does
  not support.
metadata:
  version: "2.0.0"
license: MIT
allowed-tools: >-
  ViewPrinter MCP (platforms, accounts, groups, media, posts), and local Python helpers
  that read and write the project's files and a ~/ViewPrinter folder (the review registry,
  the source archive and the user's answers about tools) and call no outside service:
  scripts/learn.py (publication links and posting checkpoints); content-production's
  memory.py and archive.py (project memory, an archive of originals) and tools.py (finds
  local tools by running each one's --version, never a browser); content-review's review scripts, which serve review pages on
  127.0.0.1 only, open them in the user's browser and check them in a headless Chrome with
  its background networking off; account-profiles' build_review.py; and paid-growth's
  arena.py (ad decisions from exported numbers)
---

# Content publishing

ViewPrinter is a hosted MCP server that publishes to social platforms on the
user's behalf. You drive it by calling its tools; the user drives you by asking
for what they want posted.

The platform names above are in the description so this skill can be *found*.
They are not a list to reason from — `platforms_list` is the only source of
truth for what can publish and what each one accepts. See
`references/rules/platforms-first.md`.

## The rest of this plugin

This skill publishes. The plugin's other skills cover the work around it, and
ship with it:

| Skill | Use it for |
|---|---|
| [content-production](content-production/GUIDE.md) | Developing formats and the project's own content skill, making batches, recurring influencers, the source archive |
| [content-review](content-review/GUIDE.md) | The local review workspace: one review per project and format, up to verified scheduling |
| [content-learning](content-learning/GUIDE.md) | Which posts and formats worked, and what to make next |
| [account-profiles](account-profiles/GUIDE.md) | Profile copy, images, links and feature eligibility across a group of accounts, including partial groups and shared accounts |
| [paid-growth](paid-growth/GUIDE.md) | Testing and scaling winning posts as TikTok ads (early access) |

A project keeps one content skill of its own — shared guidance plus one
reference per format — and content-production helps build and extend it rather
than creating a skill per format. Local review of content or account groups
never changes remote groups or scheduled posts; those go through the rules
below. The hosted connection is needed for remote posting and account tools,
not for local production, review or planning.

## If the remote tools are not there yet

The eleven rules below all assume `platforms_list`, `media_upload` and the rest are
callable. Installed as a plugin they are — the manifest brings the server. But a
skill can be installed on its own, and then none of them exist.

**Check before remote work.** If the ViewPrinter tools are not available, the hosted server
is not connected and remote operations cannot proceed. Explain the setup below; local production and review can continue through content-production and content-review:

- It is a remote MCP server at `https://viewprinter.tech/api/mcp` — streamable
  HTTP, OAuth only. There is no API key to paste anywhere, and any instruction
  to obtain one is wrong.
- The authorization server advertises Client ID Metadata Documents. A client
  that only attempts Dynamic Client Registration may fail with *"Incompatible
  auth server: does not support dynamic client registration"* — use the client's
  CIMD flow instead.
- Let the user complete the browser sign-in. Do not ask for credentials in chat.

## When to use this

- Posting, scheduling, drafting, rescheduling or cancelling anything
- Connecting a social account, or fixing one that needs reconnecting
- Grouping accounts so a post can name the set instead of listing ids
- Uploading an image or video to attach to a post
- Asking how a post did, or how an account is growing
- Linking each post to the format that made it, when it is scheduled

## The shape of the work

1. **See what exists** — `accounts_list`, `groups_list`, `media_list`
2. **Learn the rules** — `platforms_list`, before composing anything
3. **Get the media in** — `media_upload`, then PUT the bytes; that is all
4. **Confirm label choices, then queue it** — ask about promotional-content and
   AI labels before `posts_save` creates a post or releases a draft; see
   `references/rules/scheduling.md`
5. **Read what happened** — `posts_list` (filters, one post, numbers per
   destination) and `accounts_list` with `metrics: true`; to learn which formats
   work, link each post when it is scheduled and compare fairly (`learning`)

Nothing publishes until `posts_save` returns. Do not tell anyone a post is
scheduled before it does.

## Rules

Read the one that covers what you are about to do. Do not read all of them.

| Rule | Priority | Covers |
|---|---|---|
| `platforms-first` | CRITICAL | Live platform rules and connection-specific schema mismatches |
| `media-upload` | CRITICAL | Uploading is two steps, and the second is yours; deleting is permanent |
| `destinations` | CRITICAL | Workspaces, and why a group is a snapshot |
| `scheduling` | CRITICAL | Approval, opt-in labels, trial audiences, absolute times, and safe retries |
| `drafts` | HIGH | The word means two unrelated things |
| `refusals` | HIGH | A refused post was never saved, and is not a sales opening |
| `amend-and-cancel` | HIGH | What can still be changed, and what cannot be recalled |
| `captions` | MEDIUM | Native descriptions per platform, and editing words without touching delivery |
| `connecting` | MEDIUM | Only the user can finish it |
| `reading-results` | MEDIUM | Measured when it was measured, and missing is not zero |
| `learning` | MEDIUM | Link each post to what made it, compare with its own account's normal, decide what to make more of |

## Honesty constraints that hold everywhere

- **Report what the tool returned**, not what you expected it to return.
- **A refusal is a fact to relay, not a problem to route around.** You are
  running inside somebody else's client.
- **Numbers carry the time they were measured.** Quote it.
