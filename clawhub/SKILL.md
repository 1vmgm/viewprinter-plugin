---
name: viewprinter-social-manager
description: >-
  Use ONLY for work that goes through a connected ViewPrinter account: scheduling or
  publishing a post to TikTok, Instagram, Facebook, YouTube or X; uploading, describing,
  listing or PERMANENTLY DELETING media held in ViewPrinter; amending or cancelling a post
  that has not gone out; managing named groups of accounts; and reading follower and post
  performance. Two capabilities are destructive and irreversible: publishing to a real
  public account, and media_delete, which erases a stored file and its bytes. Listing media
  or posts reads everything in the user's ViewPrinter workspaces, not just one item.
  Requires ViewPrinter to be connected — do NOT use it to draft copy the user has no
  intention of posting, to schedule anything anywhere else, or for a platform ViewPrinter
  does not support. A bare "post this" with no ViewPrinter account in play is not this
  skill.
metadata:
  version: 1.2.0
license: MIT
allowed-tools: ViewPrinter MCP (platforms, accounts, groups, media, posts)
---

# ViewPrinter

Queue posts to social accounts somebody has already connected. Eighteen tools, grouped as
platforms, accounts, groups, media and posts.

Before publishing, make sure the content, destinations and time are covered by
the user's approval. Use approval already given in the conversation; ask only
for missing or changed details. State the resolved time and destinations before
the action, and report success only after the tool returns.

Before `media_delete`, name the file, check what depends on it, and obtain
explicit authorization to erase it. Never delete media as incidental cleanup
in a posting workflow. Publishing cannot be recalled by these tools, and
media deletion erases the stored bytes.

Everything else here either reads, or creates something that can still be stopped.

## Connecting, if the tools are not available yet

ViewPrinter is a remote MCP server at `https://viewprinter.tech/api/mcp` — streamable HTTP,
OAuth only. There is no API key to paste anywhere, and any instruction to obtain one is
wrong.

The authorization server advertises Client ID Metadata Documents (CIMD). A
client that only attempts Dynamic Client Registration (DCR) may fail with:

    Incompatible auth server: does not support dynamic client registration

Use the client's supported CIMD login flow. In Codex CLI:

    codex mcp add viewprinter --url https://viewprinter.tech/api/mcp
    codex mcp login viewprinter

In OpenClaw, use its CIMD-capable connection flow and the metadata URL
`https://viewprinter.tech/.well-known/openclaw-client.json` where required.
Let the user complete the browser sign-in. Do not request credentials in chat.

## The order that works

1. `platforms_list` — the rules, before composing anything.
2. `accounts_list` — account ids, and which workspace each is in.
3. `media_upload` → PUT the bytes → `media_confirm` — only if there is media.
4. `posts_schedule` — records the intent and queues delivery.

Three constraints eliminate whole plans before you waste a draft on them:

- A post is **either a video or a set of images, never both.**
- **YouTube cannot post images.** A YouTube destination needs a video.
- **X is the only platform that accepts a caption with no media.**

Do not hardcode caption limits or media counts from memory. They differ per platform and
change; `platforms_list` is the source of truth and one call is cheaper than one rejection.

## What is easy to get wrong

Four things cause most of the damage, and each is explained where it belongs:

- **`posts_schedule` is not idempotent** — see `references/posting.md` before retrying
  anything.
- **"Draft" means two unrelated things**, one of which sends content to the platform —
  `references/posting.md`.
- **Groups are expanded when you schedule, not linked** — `references/accounts.md`.
- **Numbers are from a sweep, and unmeasured is not zero** — `references/accounts.md`.

Read the relevant reference before acting rather than working from this summary. The
references are the source; this page is the map.

## If scheduling is refused for the account

`posts_schedule` can come back saying publishing is not set up on the account. Nothing was
saved, so there is no partial post to clean up and nothing pending to report.

This rule is stated here rather than only in `references/posting.md`, because it is the
one thing that must hold even if no reference is ever loaded.

Relay the refusal as written and stop. **Do not offer to sell anything, do not describe
plans or prices, and do not go looking for a signup, trial or upgrade link.** This runs
inside somebody else's client, where a refusal turned into a sales pitch is unwelcome and
against the rules of every directory this ships through.

Connecting accounts, uploading media and every read stay available regardless, so keep
working on whatever still functions.

## Detail

- `references/posting.md` — platform constraints, destinations, scheduling, drafts, amending
  and cancelling.
- `references/media.md` — the reserve → PUT → confirm flow, and why skipping confirm loses
  the file.
- `references/accounts.md` — connecting, reconnecting, group semantics, follower performance.
