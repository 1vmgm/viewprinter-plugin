# ViewPrinter for AI assistants

Develop content formats, produce and review batches, schedule them to **TikTok,
Instagram, Facebook, YouTube and X**, and learn which ones worked.

### Install

```bash
npx skills add 1vmgm/viewprinter-plugin    # the five skills, from this repo — any agent
npx skills add https://viewprinter.tech    # the same, as one combined skill
```

The scheme is required on the second one: a bare hostname is treated as a git
repository. The domain serves the latest published release as one combined skill.
Neither installs the MCP server, because the skills CLI has no MCP handling. For both together, install the
plugin in Claude Code or Codex (below).

This plugin connects your assistant to [ViewPrinter](https://viewprinter.tech)
and carries everything for making social content with it, as five skills that
work together. The hosted MCP service provides the tools.

| Skill | Use it for |
| --- | --- |
| `content-publishing` | Connecting accounts, uploading media, scheduling and amending posts, checking delivery and reading performance |
| `content-production` | Developing formats and your project's own content skill, then producing batches from them |
| `content-review` | One review per project and format, in one local workspace, up to verified scheduling |
| `content-learning` | Which posts and formats worked, and what to make next |
| `account-profiles` | Profile copy, images, links and feature eligibility across a group of accounts |

Your brand and formats live in a content skill inside your own project, which
`content-production` helps you set up; account briefs are files in your project
too. This plugin stays general.

The skills' local helpers need **Python 3.9 or newer** (`python3`; on Windows often
`python` or `py -3`). Checking a review page uses Chrome, Chromium or Edge.

You need a ViewPrinter account. Sign in with **OAuth**, then connect the social
accounts you want to use. There is no ViewPrinter API key to copy into a config.

### What runs where

- **The hosted server.** The ViewPrinter tools run at `https://viewprinter.tech/api/mcp`.
  Your posts, media and account details go there, because publishing them is what the
  service does. You sign in with OAuth.
- **Local helpers.** The skills' Python scripts run on your machine and call no outside
  service. They read and write your project's files, including
  `.viewprinter/content-memory`, and a `ViewPrinter` folder in your home folder: the
  review registry, the source archive and your answers about tools. content-production's
  `tools.py` finds the tools you have by running each one's `--version` (never a browser).
- **The review page.** content-review serves review pages on `127.0.0.1:8765`
  (`VIEWPRINTER_REVIEW_PORT` changes the port), opens one tab in your browser, and checks
  pages in a headless Chrome, Chromium or Edge that, for a local review, resolves no
  other host.
- **Preflight checks.** Each skill's `scripts/preflight.sh` checks Python and that its
  helpers start. content-publishing's also asks the ViewPrinter server for its tool list
  and sign-in metadata, without credentials.

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
The plugin's connection uses the connector's address, so with both you see one set
of tools.

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
| Production | Produce batches from a format, with project memory and an archive of originals that ViewPrinter can keep too |
| Review | One review per project and format in one local workspace: versions, native captions, scheduling receipts |
| Accounts | List and connect accounts, identify reconnection needs, read account metrics |
| Groups | Manage named sets of accounts for posting |
| Account profiles | Compare current/proposed profiles, prepare assets and copy, preserve dated platform research |
| Media | Upload, list, describe and delete stored images, videos and audio; keep raw material to reuse, never posted as it is |
| Posts | Hold drafts, schedule, amend pending posts, cancel, check each destination |
| Platforms | Read media requirements, caption limits, and posting options |
| Learning | Tie each post to the format that made it; double down on, vary or retire formats |

In Claude and ChatGPT, `media_upload` shows an upload box for the person's files;
elsewhere it gives an `upload_page` link, or an agent that holds the file PUTs it to a
short-lived URL. There is no confirm step: the file is recorded once it arrives. See
the [media upload rule](skills/content-publishing/references/rules/media-upload.md).

A draft **held in ViewPrinter** stays out of the queue. A platform draft can
upload content to the social platform for you to finish there. Name the kind you
want. A post's caption and destinations can change only while every destination is
pending, though its time can still move; cancellation cannot recall a delivery
already in progress. Account metrics include their
measurement time and are not live counters.

## Tools for making content

Publishing needs only this plugin. Making the media needs a tool for each task. The
production skill recommends one when your work needs it, tells you how to install it, and
remembers when you say "not now":

| Task | Tool |
| --- | --- |
| Video editing, motion graphics, sound design | [Tesseract](https://github.com/mirage-hq/Tesseract) by Mirage (`npx skills add mirage-hq/Tesseract`) |
| Media conversion, covers, frames | ffmpeg |
| App demos and screen recordings | [Argent](https://github.com/software-mansion/argent) (`npx @swmansion/argent@latest init -y`) |
| Video and image generation | Higgsfield or fal, with your own account |
| Voiceover and captions from speech | ElevenLabs |
| Breaking down a video | Gemini API |
| Research: creators, posts, transcripts | Scrape Creators; ViewPrinter's own research is coming soon |
| Meme templates | Memelord |
| App and UI design references | Mobbin |

It also keeps you informed on spending: the expected cost before each paid step, what it
cost and the running total after, and a batch total at handoff. Ask your assistant which
of these tools you have; [tools](skills/content-production/references/tools.md) has every
setup step.

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
