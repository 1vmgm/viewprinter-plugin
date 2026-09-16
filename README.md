<img src="assets/logo.png" alt="" width="76" align="left" hspace="14" vspace="4">

# ViewPrinter for Claude Code

Schedule and publish social posts to **TikTok, Instagram, Facebook, YouTube and
X** from Claude — plan a week of content, upload media, queue posts, check what
went out, and track how each account is growing.

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
- **`/viewprinter:accounts`** — connecting, reconnecting, group membership
  semantics, and reading follower performance.

Claude loads these automatically when relevant; you don't have to invoke them.

## Using the server without the plugin

The plugin is a wrapper around a remote MCP server at
`https://viewprinter.tech/api/mcp` — streamable HTTP, OAuth only. There is no
API key to paste anywhere.

**Claude Code**

```
claude mcp add -t http viewprinter https://viewprinter.tech/api/mcp
```

**Anything that reads `.mcp.json`** (Cursor, VS Code, and others)

```json
{
  "mcpServers": {
    "viewprinter": { "type": "http", "url": "https://viewprinter.tech/api/mcp" }
  }
}
```

**OpenClaw** needs one extra flag, explained below:

```
openclaw mcp add viewprinter \
  --url https://viewprinter.tech/api/mcp \
  --transport streamable-http --auth oauth \
  --oauth-scope "mcp:tools offline_access" \
  --oauth-client-metadata-url https://viewprinter.tech/.well-known/openclaw-client.json
openclaw mcp login viewprinter
```

### If a client says the auth server is incompatible

```
Incompatible auth server: does not support dynamic client registration
```

That is the client being behind the spec rather than the server being broken.
MCP 2026-07-28 deprecates Dynamic Client Registration in favour of Client ID
Metadata Documents, and this server follows it: it advertises
`client_id_metadata_document_supported` and exposes no registration endpoint.

A client that supports CIMD needs a metadata URL to identify itself with. If it
publishes its own, use that. If it does not — as OpenClaw currently does not —
one is served at
`https://viewprinter.tech/.well-known/openclaw-client.json`.

It is also listed in the [Claude directory](https://claude.ai/directory/viewprinter)
and the [MCP registry](https://registry.modelcontextprotocol.io/?q=viewprinter)
as `tech.viewprinter/viewprinter`.

## Links

- [viewprinter.tech](https://viewprinter.tech)
- [Setup instructions for other clients](https://viewprinter.tech/mcp)

## License

MIT — see [LICENSE](LICENSE).
