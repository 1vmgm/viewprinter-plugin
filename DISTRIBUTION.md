# Distribution and releases

`skills/` is the shared source. Generate client packages from it. ViewPrinter's
MCP service remains hosted separately.

## Status — September 17, 2026

| Channel | Package / source | Status |
| --- | --- | --- |
| Codex | Portable package, compatibility manifest, repository marketplace | Local installation support; see verification |
| Claude Code | Claude manifest and shared skills | Existing community marketplace path retained |
| ClawHub | Generated single-skill bundle | Existing listing `@1vmgm/viewprinter-social-manager`; new builds are not automatically published |
| OpenAI directory | Remote MCP submission with skills | **Pending review**, confirmed by the owner |
| LobeHub | No release | Deferred; repository access was declined |

Version 1.2.0 is the local package version for this work, not a claim that it is
published. See [compatibility](docs/compatibility.md).

The old September 15 note described a previous submission artifact. It does not
establish the current pending submission's contents. Preserve the pending review;
repository edits and builds do not replace it.

## Files

- `plugin.json`: portable identity, version, OpenAI presentation.
- `mcp.json`: portable Streamable HTTP connection.
- `.codex-plugin/plugin.json`: Codex compatibility manifest.
- `.claude-plugin/plugin.json` and `.mcp.json`: Claude metadata.
- `.agents/plugins/marketplace.json`: marketplace for the root package.
- `skills/viewprinter/`: the canonical skill. `SKILL.md` routes; `rules/` holds
  one file per mistake worth preventing.
- `clawhub/SKILL.md`: the ClawHub-facing entry point; `build.mjs` copies the
  rules in as `references/`.
- `evals/workflows.json`: behavior scenarios; definitions are not test results.

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

The build produces a complete plugin ZIP and a single-skill ZIP from the same
shared source. Generated `dist/` directories are ignored; never edit them.

## Channel updates

**Codex / Claude:** release repository changes, then refresh/reinstall the
package. Installed caches do not necessarily track source edits immediately.
The marketplace listing and installed package are separate distribution pieces.

**ClawHub:** after validating the generated package, publish an explicitly
versioned release with the supported CLI. The existing workflow is:

```bash
node clawhub/build.mjs
npx clawhub skill publish clawhub/dist/viewprinter-social-manager \
  --slug viewprinter-social-manager --owner 1vmgm --version 1.2.0 \
  --changelog "Codex packaging and shared workflow updates" --categories automation \
  --topics viewprinter,tiktok,instagram,scheduling
```

Every release is scanned. Keep descriptions aligned with capabilities, including
media deletion and workspace-wide listing. Avoid hidden instructions in generated
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
