# Distribution and releases

`skills/` is the shared source. Generate client packages from it. ViewPrinter's
MCP service remains hosted separately.

## Status — October 6, 2026

| Channel | Package / source | Status |
| --- | --- | --- |
| Codex | Portable package, compatibility manifest, repository marketplace | `codex plugin marketplace add 1vmgm/viewprinter-plugin`; see verification |
| Claude Code | Claude manifest, and `.claude-plugin/marketplace.json` making this repository a marketplace | `/plugin marketplace add 1vmgm/viewprinter-plugin`. Not listed in Claude's plugin directory |
| Claude directory | Connector: the hosted MCP server, tools only | Live since August 2026 at claude.ai/directory/viewprinter, tagged Community; carries no skills |
| ClawHub | Generated package: the content-publishing entry, the other five skills as guides | `@1vmgm/viewprinter-social-manager` 1.3.1 submitted 2026-09-29, pending security scan; new builds are not automatically published |
| OpenAI directory | Remote MCP submission with skills | 1.0.0 published; 1.3.1 (skill 1.3.1, widgets in the tool scan) replacing the 1.3.0 review, 2026-09-29 |
| Cursor Marketplace | `.cursor-plugin/plugin.json`, derived from `plugin.json` by `set_version.py`; remote server inline as a bare URL | Manifest added 2026-09-29; not yet submitted at cursor.com/marketplace/publish (manual review) |
| LobeHub | No release | Deferred; repository access was declined |

A version here is what the repository holds; a channel has it only once published
there. See [compatibility](docs/compatibility.md).

The old September 15 note described a previous submission artifact. It does not
establish the current pending submission's contents. Preserve the pending review;
repository edits and builds do not replace it.

## Files

- `plugin.json`: portable identity, version, OpenAI presentation.
- `mcp.json`: portable Streamable HTTP connection.
- `.codex-plugin/plugin.json`: Codex compatibility manifest.
- `.claude-plugin/plugin.json` and `.mcp.json`: Claude metadata.
- `.claude-plugin/marketplace.json`: makes this repository a Claude Code marketplace.
- `.agents/plugins/marketplace.json`: marketplace for the root package.
- `skills/`: the six skills. `content-publishing` is the entry point: its
  `SKILL.md` routes and `references/rules/` holds one file per mistake worth
  preventing. `content-production`, `content-review`, `content-learning`,
  `account-profiles` and `paid-growth` ship beside it and link to each other.
- `clawhub/frontmatter.md`: the ClawHub listing's frontmatter. `node clawhub/build.mjs`
  generates `clawhub/entry.md` and `clawhub/dist/` from it and `skills/`.
- `skills/<name>/evals/evals.json`: each skill's test prompts; definitions are
  not test results.

The portable OpenAI extension takes precedence over the compatibility overlay.
The validator checks that identity and presentation agree.

## Prepare a release

1. Edit canonical skills and any affected entry-point guidance.
2. Run `.venv/bin/python scripts/set_version.py <version>` to synchronize all
   manifests, ClawHub metadata, and evaluations; use a release version without
   a local `+codex.` suffix.
3. Run [validation and build](scripts/README.md).
4. Inspect `dist/release.json`: source commit, dirty-tree status, archive hashes,
   and hashes of every packaged file.
5. Test installation and affected workflows in the intended clients.
6. Publish the authorized channels and record the version/artifact sent to each.
7. Cut a GitHub release `v<version>` carrying the three ZIPs from `dist/`. The
   ViewPrinter site's `/.well-known/agent-skills/index.json`, which
   `npx skills add https://viewprinter.tech` reads, points at that release's
   `viewprinter-skill-<version>.zip`: update its version, `sha256` digest (from
   `dist/release.json`), skill name (`viewprinter-social-manager`, the name in the
   archive's SKILL.md) and description together, then deploy the site.

The build produces three ZIPs from the same shared source: the complete plugin,
the ClawHub package, and that package with `SKILL.md` at the archive root, which
`npx skills add https://viewprinter.tech` fetches. Generated `dist/` directories are ignored; never edit them.

## Channel updates

**Codex / Claude:** release repository changes, then refresh/reinstall the
package. Installed caches do not necessarily track source edits immediately.
The marketplace listing and installed package are separate distribution pieces.

**ClawHub:** after validating the generated package, publish an explicitly
versioned release with the supported CLI. The existing workflow is:

```bash
node clawhub/build.mjs
npx clawhub skill publish clawhub/dist/viewprinter-social-manager \
  --slug viewprinter-social-manager --owner 1vmgm --version <version> \
  --changelog "Codex packaging and shared workflow updates" --categories automation \
  --topics viewprinter,tiktok,instagram,scheduling
```

Every release is scanned. Keep descriptions aligned with capabilities, including
media deletion, workspace-wide listing and the review server on `127.0.0.1`. Avoid hidden instructions in generated
comments. A dry run is not proof of successful publication.

**OpenAI:** wait for the pending review. If feedback or a subsequent release
requires an archive, build from the canonical source and record its checksum.
The hosted endpoint and skills belong in the same **With MCP** submission.
Do not create another listing to work around pending review.

**LobeHub:** revisit only if its connection permissions fit the owner's needs.

## Workflow consistency

Publishing requires approval covering content, destinations, and time; use
approval already provided. Media deletion requires explicit authorization for
the affected file and dependencies. Report a scheduling refusal without a sales
pitch. Keep these behaviors consistent in shared skills and the entry point.
