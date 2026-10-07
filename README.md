<img src="assets/logo.png" alt="" width="76" align="left" hspace="14" vspace="4">

# ViewPrinter for AI assistants

Develop content formats, produce and review batches, schedule them to **TikTok,
Instagram, Facebook, YouTube and X**, and learn which ones worked.

### Install

```bash
npx skills add https://viewprinter.tech    # the skills, from our domain — any agent
npx skills add 1vmgm/viewprinter-plugin    # the skills, from this repo
```

The scheme is required on the first one: a bare hostname is treated as a git
repository. Either installs the skills only — neither installs the MCP server,
because the skills CLI has no MCP handling. For both together, install the
plugin in Claude Code or Codex (below).

This plugin connects your assistant to [ViewPrinter](https://viewprinter.tech)
and carries everything for making social content with it, as six skills that
work together. The hosted MCP service provides the tools.

| Skill | Use it for |
| --- | --- |
| `content-publishing` | Connecting accounts, uploading media, scheduling and amending posts, checking delivery and reading performance |
| `content-production` | Developing formats and your project's own content skill, then producing batches from them |
| `content-review` | One review per project and format, in one local workspace, up to verified scheduling |
| `content-learning` | Which posts and formats worked, and what to make next |
| `account-profiles` | Profile copy, images, links and feature eligibility across a group of accounts |
| `paid-growth` | Testing and scaling winning posts as TikTok ads — early access, still being refined |

Your brand and formats live in a content skill inside your own project, which
`content-production` helps you set up; account briefs are files in your project
too. This plugin stays general.

The skills' local helpers need **Python 3.9 or newer** (`python3`, or `python` on
Windows). Checking a review page uses Chrome, Chromium or Edge.

You need a ViewPrinter account. Sign in with **OAuth**, then connect the social
accounts you want to use. There is no ViewPrinter API key to copy into a config.

## Install

| Client | Installation |
| --- | --- |
| **Codex** | [This repository's marketplace](#codex) |
| **Claude Code** | [This repository's marketplace](#claude-code) |
| **Claude apps** | [Connector in the Claude directory](#claude-apps) (tools only) |
| **ChatGPT** | [ChatGPT plugin](#chatgpt) |
| **OpenClaw** | [ClawHub skill and MCP connection](docs/openclaw.md) |
| **Other MCP clients** | [Hosted server connection](#mcp-only-setup) |

### Codex

```bash
codex plugin marketplace add 1vmgm/viewprinter-plugin
codex plugin add viewprinter@viewprinter
```

From a checkout of this repository, `codex plugin marketplace add .` works the
same way.

Start a new Codex session and ask:

> Use ViewPrinter to show my connected accounts and which need reconnecting.

Complete browser sign-in if prompted. The plugin includes the skills and
the MCP connection; you do not need a second standalone MCP configuration.

For updates, removal, and standalone skills, see [Codex setup](docs/codex.md).
See [compatibility](docs/compatibility.md) for what has actually been tested.

### Claude Code

Run these commands inside Claude Code:

```text
/plugin marketplace add 1vmgm/viewprinter-plugin
/plugin install viewprinter@viewprinter
```

Start a new session, ask to use ViewPrinter, and complete browser sign-in when
prompted. `/plugin marketplace update viewprinter` picks up a new release.

### Claude apps

ViewPrinter is in the [Claude directory](https://claude.ai/directory/viewprinter)
as a connector: one click adds the tools in Claude on the web and desktop, and in
Claude Code when you sign in with the same Claude account. A connector carries the
tools, not these skills; for the skills in Claude Code, install the plugin above.
The plugin brings its own connection, so with both you may see each tool twice:
keep one.

### ChatGPT

ViewPrinter is a [ChatGPT plugin](https://chatgpt.com/plugins/plugin_asdk_app_6a974ded9ba88191a1e60a18c0c985a3).
The listing serves the version OpenAI last approved; changes here reach it with
the next approved submission.

## Try it

- “Show my connected accounts and which need reconnecting.”
- “Prepare this video as a draft held in ViewPrinter for my TikTok account.”
- “Schedule these approved posts across next week at 9am Chicago time.”
- “Which posts failed, and on which destinations?”
- “How have my accounts grown since last week?”
- “Review this group of accounts and prepare profile copy, branding and a link-unlock checklist.”
- “Help me develop a format for my brand and set up our content skill for it.”
- “Make this week's batch from that format and open it for review.”
- “Which formats worked last month, and what should we make next?”

The assistant selects the skill from your request. In Claude Code you can also
invoke one directly, such as `/viewprinter:content-publishing`, and Codex lists
the same namespaced skills in its selector.

## What you can do

| Area | Capabilities |
| --- | --- |
| Formats | Develop repeatable formats and keep them in your project's own content skill |
| Production | Produce batches from a format, with project memory and an archive of originals |
| Review | One review per project and format in one local workspace: versions, native captions, scheduling receipts |
| Accounts | List and connect accounts, identify reconnection needs, read account metrics |
| Groups | Manage named sets of accounts for posting |
| Account profiles | Compare current/proposed profiles, prepare assets and copy, preserve dated platform research |
| Media | Upload, list, describe, and delete stored images or videos |
| Posts | Hold drafts, schedule, amend pending posts, cancel, check each destination |
| Platforms | Read media requirements, caption limits, and posting options |
| Learning | Tie each post to the format that made it; double down on, vary or retire formats |
| Paid growth | Choose which posts get ad spend, cut losers and scale winners (early access) |

Uploads require a client that can read the file and send an HTTP PUT. Where that
is unavailable, use media already uploaded to ViewPrinter or upload through the
ViewPrinter site. The [media upload rule](skills/content-publishing/references/rules/media-upload.md)
covers reserve → PUT → confirm.

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
