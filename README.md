# ViewPrinter for Claude Code

Schedule and publish social posts to **TikTok, Instagram, Facebook, YouTube and
X** from Claude — plan a week of content, upload media, queue posts, then check
what went out.

This plugin connects Claude to [ViewPrinter](https://viewprinter.tech) and adds
skills that teach it how the posting flow actually works: which platform accepts
what, how media upload is sequenced, and what can still be changed after a post
is queued.

## Install

```
/plugin marketplace add anthropics/claude-plugins-community
/plugin install viewprinter@claude-community
```

Then run any ViewPrinter command and Claude will prompt you to sign in. Access
is per-account via OAuth — no API keys to paste, and you approve exactly which
tools the client may use.

You need a ViewPrinter account and at least one connected social account. Sign
up at [viewprinter.tech](https://viewprinter.tech).

## What it can do

| Area | |
|---|---|
| **Accounts** | List connected accounts, start a connection, read follower performance |
| **Groups** | Name a set of accounts and post to all of them at once |
| **Media** | Upload images and video, describe them, list and delete |
| **Posts** | Schedule, draft, amend, cancel, and check delivery per destination |
| **Platforms** | Read each platform's media rules, caption limits and options |

## Skills

- **`/viewprinter:posting`** — scheduling, drafts, amending and cancelling, plus
  the platform constraints that decide where a post can go.
- **`/viewprinter:media`** — the reserve → PUT → confirm upload flow, and why
  skipping the last step loses the file.
- **`/viewprinter:accounts`** — connecting, reconnecting, and group membership
  semantics.

Claude loads these automatically when relevant; you don't have to invoke them.

## Using the server without the plugin

The plugin is a wrapper around a remote MCP server. To connect directly:

```
claude mcp add -t http viewprinter https://viewprinter.tech/api/mcp
```

It is also listed in the [Claude directory](https://claude.ai/directory/viewprinter)
and the [MCP registry](https://registry.modelcontextprotocol.io/?q=viewprinter)
as `tech.viewprinter/viewprinter`.

## Links

- [viewprinter.tech](https://viewprinter.tech)
- [Setup instructions for other clients](https://viewprinter.tech/mcp)

## License

MIT — see [LICENSE](LICENSE).
