# Troubleshooting

## Tools appear, but skills do not

An MCP-only connection does not install skills. Install the full plugin, or the
skills themselves from `skills/` — `content-publishing` at minimum. Account
connection and inventory guidance is in its `references/rules/connecting.md`;
grouping guidance is in `references/rules/destinations.md`. The skill formerly
called `viewprinter` is now `content-publishing`, and `account-group-review` is
now `account-profiles`; the older `accounts`, `posting` and `media` folders are
gone.
Start a new session after plugin installation. In Codex, check
`codex plugin list --marketplace viewprinter` and look for the ViewPrinter skills
in the selector. Reinstall after updating a cached package.

## A helper does not start

The skills' helpers need Python 3.9 or newer. Each skill's `scripts/preflight.sh`
tries `python3`, then `python`, then `py -3`; Windows installs often have only the
last two. On Windows, keep projects on a drive letter (a mapped drive works): review
pages are not served from network paths such as `\\server\share`. Checking a
review page uses Chrome, Chromium or Edge; if none is found, set `VIEWPRINTER_CHROME` to
its executable. Review pages are served on `127.0.0.1:8765`; set
`VIEWPRINTER_REVIEW_PORT` when another program uses that port.

## OAuth fails before the sign-in page

One possible error is:

```text
Incompatible auth server: does not support dynamic client registration
```

ViewPrinter advertises Client ID Metadata Documents (CIMD). A client that only
tries Dynamic Client Registration (DCR) cannot complete that flow. Check the
client's CIMD support and configuration. There is no ViewPrinter API key.

Codex CLI 0.154.0 exposes an explicit registration option for standalone MCP:

```bash
codex mcp login viewprinter --oauth-client-registration cimd
```

This applies to a connection added with `codex mcp add`. Plugin-managed connections
use the client's plugin sign-in flow. OpenClaw may require the metadata URL in
[its setup guide](openclaw.md).

Complete browser sign-in; do not paste passwords or tokens into the conversation.
If a social account needs reconnecting after login, ask for an
`accounts_connect` link for that account.

## A trial option works in another agent but is rejected here

Compare the exact connection and tool declaration with `platforms_list`. A
client's cached schema may lack `platform_options.instagram.trialReel` even
though the live service exposes `MANUAL` and `SS_PERFORMANCE`. An
`additionalProperties` rejection is a failed request, not a queued post.

Refresh the authorized connection and rediscover its schema. If the updated
connection exposes the option, confirm account access, check for an existing
post, and retry the approved intent as a held draft with the same idempotency
key. Release it only with approval, and verify the destination's delivery.
Do not route around workspace permissions, drop the trial option, or publish
an ordinary Reel as a fallback. Report a persistent mismatch as a connector
issue, not as evidence that Instagram trials are unavailable.

## An uploaded file is missing

In chat apps the file arrives through the upload box `media_upload` shows, or its
`upload_page` link. An agent that holds the file calls `media_upload` and PUTs the
bytes to the URL it returns, with a matching `Content-Type`. There is no confirm
step: the file is recorded once the PUT lands. If the PUT succeeded, use the id you
already have; if the URL expired first, start a new upload.

## A post cannot be changed or fully cancelled

Check each destination. The caption and destinations can change only while every
destination is pending; the time can still move after one has started.
Cancellation may return `still_going` deliveries that have already begun. Queue
acceptance does not prove that every destination published successfully.

## A client is not listed as tested

Consult [compatibility](compatibility.md). Valid package files do not establish
that OAuth, uploads, and other workflows work in every client.
