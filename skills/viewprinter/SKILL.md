---
name: viewprinter
description: Schedule and publish social posts to TikTok, Instagram, Facebook, YouTube and X through ViewPrinter — connecting accounts, uploading media, queueing and amending posts, reading how they performed, and learning which posts and formats worked. Use when the user wants to post, schedule, draft, reschedule or cancel something, connect or reconnect a social account, organise accounts into groups, upload a video or image, ask how a post or account is doing or which formats to make more of, manage recurring influencers and their content reviews, or develop a reusable content format and review workflow with the companion content-production skill.
---

# ViewPrinter

ViewPrinter is a hosted MCP server that publishes to social platforms on the
user's behalf. You drive it by calling its tools; the user drives you by asking
for what they want posted.

The platform names above are in the description so this skill can be *found*.
They are not a list to reason from — `platforms_list` is the only source of
truth for what can publish and what each one accepts. See
`references/rules/platforms-first.md`.

## Content creation and project formats

For developing a format, making or reviewing content, or improving a project’s content skill and format references, route to the installed **content-production** skill from ViewPrinter Content. It owns the shared local review server, generic hook/demo starter and format-development process. The project owns one content-creation skill with shared guidance and many distinct format references. Extend that structure rather than creating separate skills per format. A format can be reviewed before its recipe file exists; agents contribute batches to the same project + format review. Reuse one server across projects, with Content primary and Account Groups secondary.

For influencer management, use the companion’s `references/influencers.md`: maintain separate identities, appearance/voice guidance, account references, content and review history. An influencer may use formats but does not have to be one. Several agents contribute to the same influencer review; several influencers share the workspace. Historical snapshots belong under the active identity, and scheduling content does not retire the influencer. Use the shared dark-mode review UI with the purple workspace accent; do not fork a new review shell.

The companion production skill is a separate install; do not claim this publishing package bundles its runtime or generators. If it is absent, state the missing capability and continue any requested planning that does not depend on it. Hosted ViewPrinter connectivity is required for remote posting/account tools, not for local format planning or an already installed review workspace.

## If the remote tools are not there yet

The eleven rules below all assume `platforms_list`, `media_upload` and the rest are
callable. Installed as a plugin they are — the manifest brings the server. But a
skill can be installed on its own, and then none of them exist.

**Check before remote work.** If the ViewPrinter tools are not available, the hosted server
is not connected and remote operations cannot proceed. Explain the setup below; local production and review can continue through the companion skill:

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
- Asking which posts or formats worked, and what to make more of
- Developing project formats or reviewing their content, routed to the companion content-production skill

## Account profile reviews

For a persistent review of related accounts—profile copy, branding assets, link
options and dated feature unlock research—use the companion `account-group-review`
skill when installed. It supports partial platform groups and shared accounts;
posting and remote group mutations continue through the rules below.

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
| `media-upload` | CRITICAL | Uploading is two steps, and the second is yours |
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

## Account branding and group reviews

For profile copy, grouped account assets, shared identities and branding review, use [account-group-review](../account-group-review/SKILL.md). Its local review belongs in the ViewPrinter Content workspace’s secondary Account Groups area; it does not alter remote groups or scheduled posts.
