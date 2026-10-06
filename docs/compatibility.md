# Compatibility and verification

## October 6, 2026 — six skills, local package version 1.4.0

The plugin now carries six skills. This table records what was checked for that
change; the September 17 table below describes the single-skill layout and is
kept as the record of that release.

| Check | Result |
| --- | --- |
| Skill set | Validator passes: exactly six skills, each name matching its folder and its evals `skill_name`; 11 publishing rules routed to and covered; 59 evaluation case definitions |
| New validator checks | Each fails on a planted violation: unlisted skill file, broken or escaping cross-skill link, drifted `learn.py` copy, stray SKILL.md, extra skill folder, name/folder mismatch, Codex prompt not naming its skill, wrong evals `skill_name`, invalid frontmatter YAML |
| Skill helpers | 232 unit tests across the six skills pass |
| Release regression suite | 13 tests pass, including a build from the extracted ZIP |
| Preflights | All six exit 0; content-publishing's reached the live endpoint: 15 tools over unauthenticated `tools/list`, OAuth metadata 200 |
| Layout, portability, privacy | All three lints pass |
| ClawHub package | One SKILL.md (content-publishing) and five `<skill>/GUIDE.md` folders; every relative link resolves inside the package; no tests or preflights |
| Claude Code 2.1.286 | `claude plugin validate` passes with one expected warning (the contributor CLAUDE.md at the root is not plugin context). Fresh sessions loading the repository and the built ZIP each list exactly the six skills as `viewprinter:<skill>` |
| Codex | Not re-run for six skills |
| Live upload / scheduling | Not exercised |

## September 17, 2026 — local package version 1.2.0

| Check | Result |
| --- | --- |
| Portable plugin and MCP schemas | Passed against pinned official 1.0.0 schemas |
| Release file boundaries | Regression tests exclude unlisted local files and reject symlinked release inputs, parents, and outputs |
| Version update command | Release and repeated development updates synchronize all five sources; malformed inputs leave versions untouched |
| Release reproducibility | Identical checksums across repeated builds and a build from the extracted ZIP |
| Skill metadata and generated references | Passed; one skill, nine references, every reference routed to from SKILL.md and every route resolves |
| Codex CLI 0.154.0 discovery | Re-run 2026-09-17 on the consolidated tree: one namespaced skill (`viewprinter`) and one MCP server, taken from the portable `mcp.json` (`streamable-http`) |
| Codex fresh installation / removal | Passed with local marketplace; cache exposed `skills/viewprinter/SKILL.md` with no load errors; plugin and marketplace both removed afterwards |
| Claude Code 2.1.274 manifest | Passed; `mcpServers` now declared explicitly rather than relying on root `.mcp.json` auto-detection |
| Generated files | `.codex-plugin/plugin.json` and `clawhub/SKILL.md` are derived; the validator fails on a hand-edit and names the regeneration command |
| Skill layout | `scripts/lint-shape.sh`, byte-identical to the one in `vmgm/agent-skills`, passes |
| Portability | `scripts/lint-portability.sh` passes; no home paths, long numeric ids or stray root copies |
| Live MCP reachability | `skills/viewprinter/scripts/preflight.sh`: 18 tools over unauthenticated `tools/list`, OAuth metadata 200 |
| Existing authenticated ViewPrinter connection | accounts_list, platforms_list, posts_list succeeded |
| Fresh plugin OAuth sign-in | Not exercised; existing authentication does not prove fresh login |
| Live upload / draft / deletion cycle | Not exercised in a designated disposable test workspace |
| Model behavior scenarios | Definitions in evals/workflows.json; no automated model run claimed |
| ChatGPT | Directory submission pending; this package not tested in ChatGPT |
| OpenClaw | CLI unavailable; flags not re-tested |

The local marketplace was registered for this check and **removed afterwards**, along
with the test installation — `codex plugin marketplace list` shows no `viewprinter`
entry. An earlier revision of this file claimed the marketplace remained available;
it did not. Re-register with `codex plugin marketplace add .` from the repository root.

Codex installation was verified in the existing CLI configuration, not a new
authenticated user profile.

For a `source: local` marketplace Codex copies the whole working tree into its
cache, including `.git/`, `dist/` and `__pycache__/`. That is a property of local
installs, not of the published package; a marketplace sourced from GitHub clones
the repository instead.

Live checks used an existing authenticated connection. No public posts or
schedule changes were made for package validation.

Reproduce static checks with [scripts/README.md](../scripts/README.md).
Follow [Codex setup](codex.md) for installation. Test the GitHub marketplace route
after publication before marking it verified.
