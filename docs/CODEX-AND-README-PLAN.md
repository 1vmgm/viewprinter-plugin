# Codex support and README plan

Status: implementation completed locally on 2026-09-17; see docs/compatibility.md
for validation coverage and remaining client-specific checks.
The plan below records the original scope.
Repository: 1vmgm/viewprinter-plugin.

## Context and intended outcome

The user confirms that the OpenAI submission is pending review. Treat that as
the current status. Repository work and local Codex testing can proceed while
that review is pending. Changes here do not update the already-submitted archive.

"Portable" means that the same ViewPrinter skills and hosted MCP service can be
installed by different supported clients using the packaging each recognizes.
This is packaging, installation, and verification work; the current evidence
does not establish a need to rewrite the service.

Current repository:
- Three canonical skills live under skills/{posting,media,accounts}/SKILL.md.
- All three have descriptions but no explicit YAML name field.
- .claude-plugin/plugin.json and .mcp.json provide the Claude package.
- There is no portable root plugin.json, portable mcp.json, or Codex marketplace.
- The ClawHub builder already derives references from the canonical skills.
- README.md presents Claude installation first and has no Codex instructions.
- DISTRIBUTION.md contains a historical note about an older OpenAI submission;
  that note is not a live statement about the pending submission's contents.

## Plan 1: Make installation and use work in Codex / OpenAI

### 1. Make the shared skills valid across supported clients

Files: skills/viewprinter/SKILL.md and skills/viewprinter/rules/*.md.

- Add explicit name fields matching the existing skill directories.
- Keep names and paths stable so Claude's existing commands continue to work.
- Keep the three workflows as the canonical content used by every package.
- Check instructions for client-specific assumptions and reference paths.
- Preserve documented authorization, refusal, upload, retry, and data-loss
  behavior; compare the canonical skills with the ClawHub entry point so their
  behavior does not conflict.
- Add agents/openai.yaml only if needed for useful display metadata or tool
  dependencies; it is optional and is not an installation mechanism.

Acceptance: each skill validates with name and description, referenced files
exist, and Claude and Codex both discover the intended workflows.

### 2. Add the OpenAI-compatible plugin package

Files: new root plugin.json and mcp.json; existing Claude files remain.

- Use the portable Agent Plugins schemas described in current OpenAI docs.
- Keep plugin identity viewprinter and the existing hosted endpoint.
- Put portable identity at the root of plugin.json; put any OpenAI presentation
  fields in extensions.com.openai.
- Use the portable MCP transport spelling streamable-http in mcp.json.
  The existing Claude .mcp.json uses http and retains its client-specific format.
- Reuse skills/ and assets/ directly.
- Test compatibility with the installed Codex version before deciding whether
  a .codex-plugin/plugin.json compatibility manifest is necessary.
- Keep versions and service URLs consistent across all shipped manifests.
- Do not introduce a Node service or duplicate the hosted MCP implementation.

Acceptance: package schemas and paths validate; Codex loads the installed
package and its skill; existing Claude packaging still loads.

### 3. Provide an actual Codex installation path

Files: new .agents/plugins/marketplace.json; installation documentation.

- Add a repository marketplace exposing the root ViewPrinter plugin.
- Use the supported marketplace schema, explicit installation/authentication
  policy, and a source path inside the marketplace root.
- Test local marketplace installation before documenting a GitHub installation.
- After the package is released, verify the GitHub path from a clean environment.
- Document the full-plugin installation as the primary path.
- Document standalone skills plus MCP as a fallback, explaining that installing
  instructions alone does not connect the account or supply executable tools.
- Test in an isolated Codex configuration so an existing ViewPrinter connection
  cannot conceal a missing package dependency or create duplicate tools.

Acceptance: a new user can follow the documented commands, authenticate, discover
the skill and call ViewPrinter without editing internal files by hand.
The pending public-directory review is not a prerequisite for this local/Git path.

### 4. Verify behavior, not only file layout

Files: a concise validation script, focused workflow evaluation cases, and
a dated compatibility record.

- Validate JSON/YAML, required fields, packaged paths, and manifest consistency.
- Build the ClawHub output and verify it still contains the current shared skills.
- In a fresh Codex session, test skill discovery and representative natural
  language requests for accounts, uploads, and post management.
- Verify OAuth login and read-only accounts_list, platforms_list and posts_list.
- Verify an upload and an unqueued ViewPrinter draft using designated test data
  in an authorized test workspace. Exercise draft update/cancel and media cleanup
  only within that explicit test scope.
- Use fixtures/evaluations for refusal handling, retry idempotency, mixed target
  states, and cancellation limitations where live calls would be inappropriate.
- Do not use live public posting as the default installation smoke test.
- Test Claude discovery as a regression check.
- Test ChatGPT in its own supported environment when available; a Codex pass is
  not proof of ChatGPT behavior, especially for the file-upload PUT step.

Acceptance: record client versions and what was actually tested. Distinguish
validated files, authenticated workflows, and any untested surfaces.

### 5. Make releases repeatable

Files: scripts/ packaging/validation helpers, DISTRIBUTION.md, release artifacts.

- Generate any client-specific release archives from the same canonical content.
- Extend or reuse clawhub/build.mjs where appropriate instead of writing another
  independent version of the workflows.
- Record the release version, source commit and archive checksum so an uploaded
  package can be matched to its source.
- Update DISTRIBUTION.md to distinguish source changes, generated releases,
  installed copies, and pending/approved public listings.
- Preserve the current pending OpenAI submission. Prepare future artifacts
  locally; submitting or replacing the review is a separate release action.

Acceptance: a clean checkout can validate and build the same package contents,
and the release notes identify exactly what was shipped to each channel.

## Plan 2: Improve the README

### 1. Lead with the product and a concrete use case

- Use a neutral title such as "ViewPrinter for AI assistants".
- Describe the result: upload media, schedule across connected accounts, check
  delivery, and read account metrics.
- Explain in one short paragraph that the plugin bundles workflow instructions
  with access to the ViewPrinter service.
- State prerequisites and OAuth sign-in without implying an API key is required.

### 2. Put installation near the top, organized by client

- Add a compact client table with links to dedicated instructions.
- Give Codex and Claude equally prominent full-plugin installation sections.
- Label ChatGPT public-directory availability "Pending review" until confirmed.
- Include OpenClaw's existing path after verifying the current command syntax.
- Put raw MCP-only setup in an advanced/fallback section.
- Avoid claiming that a single JSON configuration works unchanged in every client.
- Show the next step after installation: sign in, open a fresh session when
  required, and verify the connection with a simple read-only request.
- Publish commands as working only after the corresponding installation test.

### 3. Demonstrate the workflows

Add a small set of useful prompts, for example:
- "Show my connected accounts and which need reconnecting."
- "Make a draft from this video for these accounts."
- "Schedule these approved posts across the next week."
- "Which posts failed, and on which destinations?"

Use ordinary language and explain automatic skill selection. Keep product-
specific invocation syntax in the relevant client section.

### 4. Describe capabilities and practical limits accurately

- Keep a concise capability table grounded in the tool schemas.
- Explain the difference between connecting MCP and installing the complete plugin.
- Explain ViewPrinter-held drafts versus drafts uploaded to a social platform.
- Describe pending-post update/cancel limits and metrics freshness briefly.
- Do not promise live metrics, support for every client, or successful publishing
  based solely on package installation.

### 5. Move detailed maintenance and troubleshooting out of the quickstart

- Move lengthy OAuth registration discussion into docs/troubleshooting.md.
- Replace blame-oriented wording with the observed error, affected/tested client
  versions, and the precise recovery steps.
- Keep release/distribution history in DISTRIBUTION.md.
- Add update/removal instructions per tested client.
- Keep links to troubleshooting, contribution information, service, and license.

Acceptance: a new reader can identify their installation path, understand what
they receive, and run one successful verification request without searching
through maintainer notes.

## Execution order

1. Skill metadata and package manifests.
2. Local Codex installation and focused workflow verification.
3. Release generation and distribution documentation.
4. README rewrite using verified commands and support claims.
5. Clean-install review of the README and Claude compatibility check.

Implementation: portable and compatibility manifests, a repository marketplace,
shared skill fixes, offline schema validation, reproducible release ZIPs, CI,
and the README/client guides are now present. Local Codex install, discovery,
and removal were verified. Fresh OAuth and live mutation workflows remain
unverified; the pending OpenAI submission has not been changed.

## References checked

- https://learn.chatgpt.com/docs/build-skills
- https://developers.openai.com/plugins/build/plugins
- https://developers.openai.com/plugins/guides/submit-claude-plugin
- Local codex-cli 0.154.0 help for plugin add and plugin marketplace add.
