# Troubleshooting

## Tools appear, but skills do not

An MCP-only connection does not install skills. Install the full plugin or the
three standalone skill folders. Start a new session after plugin installation.
In Codex, check `codex plugin list --marketplace viewprinter` and look for the
three `viewprinter:` skills in the selector. Reinstall after updating a cached
package.

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

## An uploaded file is missing

The workflow is reserve → PUT bytes → confirm. Reserving a URL alone does not
create a usable media record. If the PUT succeeded, retry confirm with the same
ID. If the client cannot send file bytes, upload through ViewPrinter or use an
already uploaded file.

## A post cannot be changed or fully cancelled

Check each destination. Updates require all destinations to remain pending.
Cancellation may return `still_going` deliveries that have already begun. Queue
acceptance does not prove that every destination published successfully.

## A client is not listed as tested

Consult [compatibility](compatibility.md). Valid package files do not establish
that OAuth, uploads, and other workflows work in every client.
