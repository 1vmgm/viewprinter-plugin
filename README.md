<img src="assets/logo.png" alt="" width="76" align="left" hspace="14" vspace="4">

# ViewPrinter for AI assistants

Upload your media, prepare a week of posts, schedule them to **TikTok, Instagram,
Facebook, YouTube and X**, and check what actually went out.

This plugin connects your assistant to [ViewPrinter](https://viewprinter.tech)
and includes three skills for posting, media, and account management. The skills
teach the workflow; the hosted MCP service provides the tools.

You need a ViewPrinter account. Sign in with **OAuth**, then connect the social
accounts you want to use. There is no ViewPrinter API key to copy into a config.

## Install

| Client | Installation |
| --- | --- |
| **Codex** | [Install from this checkout](#codex) |
| **Claude Code** | [Claude community marketplace](#claude-code) |
| **ChatGPT** | [Public directory submission pending review](#chatgpt) |
| **OpenClaw** | [ClawHub skill and MCP connection](docs/openclaw.md) |
| **Other MCP clients** | [Hosted server connection](#mcp-only-setup) |

### Codex

From the root of this repository:

```bash
codex plugin marketplace add .
codex plugin add viewprinter@viewprinter
```

Start a new Codex session and ask:

> Use ViewPrinter to show my connected accounts and which need reconnecting.

Complete browser sign-in if prompted. The plugin includes all three skills and
the MCP connection; you do not need a second standalone MCP configuration.

For updates, removal, and standalone skills, see [Codex setup](docs/codex.md).
See [compatibility](docs/compatibility.md) for what has actually been tested.

### Claude Code

Run these commands inside Claude Code:

```text
/plugin marketplace add anthropics/claude-plugins-community
/plugin install viewprinter@claude-community
```

Start a new session, ask to use ViewPrinter, and complete browser sign-in when
prompted. The marketplace installs its published version; changes in this
checkout reach users after release and update.

### ChatGPT

The OpenAI public-directory submission is **pending review** as of September 17,
2026. A public installation link will be added after approval. Repository edits
do not replace the package already submitted for review.

## Try it

- “Show my connected accounts and which need reconnecting.”
- “Prepare this video as a draft held in ViewPrinter for my TikTok account.”
- “Schedule these approved posts across next week at 9am Chicago time.”
- “Which posts failed, and on which destinations?”
- “How have my accounts grown since last week?”

The assistant can select the relevant skill from your request. In Claude Code,
you can also invoke `/viewprinter:posting`, `/viewprinter:media`, or
`/viewprinter:accounts`. Codex exposes the same namespaced skills in its selector.

## What you can do

| Area | Capabilities |
| --- | --- |
| Accounts | List and connect accounts, identify reconnection needs, read account metrics |
| Groups | Manage named sets of accounts for posting |
| Media | Upload, list, describe, and delete stored images or videos |
| Posts | Hold drafts, schedule, amend pending posts, cancel, check each destination |
| Platforms | Read media requirements, caption limits, and posting options |

Uploads require a client that can read the file and send an HTTP PUT. Where that
is unavailable, use media already uploaded to ViewPrinter or upload through the
ViewPrinter site. The media skill covers reserve → PUT → confirm.

A draft **held in ViewPrinter** stays out of the queue. A platform draft can
upload content to the social platform for you to finish there. Name the kind you
want. Posts can only be amended while every destination is pending; cancellation
cannot recall a delivery already in progress. Account metrics include their
measurement time and are not live counters.

## MCP-only setup

Connecting only the MCP service gives your assistant the tools. It does not
install the workflow skills. Use this if your client has no plugin support or
you already manage skills separately.

Endpoint: `https://viewprinter.tech/api/mcp`

Transport: Streamable HTTP · Authentication: OAuth

For a standalone Codex connection:

```bash
codex mcp add viewprinter --url https://viewprinter.tech/api/mcp
codex mcp login viewprinter
```

For a standalone Claude Code connection:

```bash
claude mcp add -t http viewprinter https://viewprinter.tech/api/mcp
```

Other clients have their own configuration formats. See their MCP instructions
and [ViewPrinter connection help](https://viewprinter.tech/mcp).

## Development and help

- [Troubleshooting](docs/troubleshooting.md)
- [Compatibility and verification](docs/compatibility.md)
- [Package validation and release builds](scripts/README.md)
- [Distribution and submission status](DISTRIBUTION.md)

`skills/` is the shared source for all clients. Client manifests configure
installation; generated archives come from that source. Changes should pass
package checks and affected client setup checks before release.

MIT — see [LICENSE](LICENSE).
