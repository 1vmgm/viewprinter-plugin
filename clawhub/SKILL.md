---
name: viewprinter-social-manager
description: >-
  Use to schedule or publish a social post to TikTok, Instagram, Facebook, YouTube or X
  through ViewPrinter, to upload media for one, to amend or cancel a post that has not gone
  out, or to read how published posts and connected accounts are performing. Run when the
  user says "post this", "schedule this", "queue it for Tuesday", "cancel that post",
  "connect my TikTok", or asks how a post or account did. It publishes to real public
  accounts, so it checks platform rules before composing and never reports a post as sent
  until the server has said so. It does NOT write the content strategy, and it does not
  cover platforms ViewPrinter cannot connect to.
metadata:
  version: 1.1.0
license: MIT
allowed-tools: ViewPrinter MCP (platforms, accounts, groups, media, posts)
---

# ViewPrinter

Queue posts to social accounts somebody has already connected. Eighteen tools, grouped as
platforms, accounts, groups, media and posts.

One rule outranks the rest:

> **Publishing is real, public and irreversible.** Once a platform has published, nothing in
> this skill takes it back. Say what will go out, to which accounts, at what exact time,
> before it goes — and never claim a post is scheduled until the tool has returned.

## Connecting, if the tools are not available yet

ViewPrinter is a remote MCP server at `https://viewprinter.tech/api/mcp` — streamable HTTP,
OAuth only. There is no API key to paste anywhere, and any instruction to obtain one is
wrong.

Its authorization server uses Client ID Metadata Documents rather than Dynamic Client
Registration, because MCP 2026-07-28 deprecates DCR. A client that only implements DCR
refuses before reaching a sign-in page:

    Incompatible auth server: does not support dynamic client registration

That is the client being behind the spec, not the server being broken. In OpenClaw, pass a
metadata URL and it skips DCR entirely:

    openclaw mcp add viewprinter \
      --url https://viewprinter.tech/api/mcp \
      --transport streamable-http --auth oauth \
      --oauth-scope "mcp:tools offline_access" \
      --oauth-client-metadata-url https://viewprinter.tech/.well-known/openclaw-client.json
    openclaw mcp login viewprinter

Signing in happens in a browser and cannot happen inside a conversation.

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
