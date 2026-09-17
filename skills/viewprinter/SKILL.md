---
name: viewprinter
description: Schedule and publish social posts to TikTok, Instagram, Facebook, YouTube and X through ViewPrinter — connecting accounts, uploading media, queueing and amending posts, and reading how they performed. Use when the user wants to post, schedule, draft, reschedule or cancel something, connect or reconnect a social account, organise accounts into groups, upload a video or image, or ask how a post or account is doing.
---

# ViewPrinter

ViewPrinter is a hosted MCP server that publishes to social platforms on the
user's behalf. You drive it by calling its tools; the user drives you by asking
for what they want posted.

The platform names above are in the description so this skill can be *found*.
They are not a list to reason from — `platforms_list` is the only source of
truth for what can publish and what each one accepts. See
`references/rules/platforms-first.md`.

## If the tools are not there yet

The nine rules below all assume `platforms_list`, `media_upload` and the rest are
callable. Installed as a plugin they are — the manifest brings the server. But a
skill can be installed on its own, and then none of them exist.

**Check before working.** If the ViewPrinter tools are not available, the server
is not connected, and nothing below applies. Say so and hand it back:

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

## The shape of the work

1. **See what exists** — `accounts_list`, `groups_list`, `media_list`
2. **Learn the rules** — `platforms_list`, before composing anything
3. **Get the media in** — `media_upload` → PUT → `media_confirm`
4. **Queue it** — `posts_schedule`
5. **Read what happened** — `posts_list`, `posts_performance`,
   `accounts_performance`

Nothing publishes until `posts_schedule` returns. Do not tell anyone a post is
scheduled before it does.

## Rules

Read the one that covers what you are about to do. Do not read all of them.

| Rule | Priority | Covers |
|---|---|---|
| `platforms-first` | CRITICAL | Never state platform limits from memory |
| `media-upload` | CRITICAL | Uploading is three steps, and step three is the one that counts |
| `destinations` | CRITICAL | Workspaces, and why a group is a snapshot |
| `scheduling` | CRITICAL | Approval, absolute times, and not posting twice |
| `drafts` | HIGH | The word means two unrelated things |
| `refusals` | HIGH | A refused post was never saved, and is not a sales opening |
| `amend-and-cancel` | HIGH | What can still be changed, and what cannot be recalled |
| `connecting` | MEDIUM | Only the user can finish it |
| `reading-results` | MEDIUM | Measured when it was measured, and missing is not zero |

## Honesty constraints that hold everywhere

- **Report what the tool returned**, not what you expected it to return.
- **A refusal is a fact to relay, not a problem to route around.** You are
  running inside somebody else's client.
- **Numbers carry the time they were measured.** Quote it.
