# Compatibility and verification

September 17, 2026 — local package version 1.2.0.

| Check | Result |
| --- | --- |
| Portable plugin and MCP schemas | Passed against pinned official 1.0.0 schemas |
| Release file boundaries | Regression tests exclude unlisted local files and reject symlinked release inputs, parents, and outputs |
| Version update command | Release and repeated development updates synchronize all five sources; malformed inputs leave versions untouched |
| Release reproducibility | Identical checksums across repeated builds and a build from the extracted ZIP |
| Skill metadata and generated references | Passed; three skills, shared references match their sources |
| Codex CLI 0.154.0 discovery | Three namespaced skills and one MCP server discovered |
| Codex fresh installation / removal | Passed with local marketplace; installed cache exposed all three skills with no load errors; test install removed |
| Claude Code 2.1.274 manifest | Passed |
| Existing authenticated ViewPrinter connection | accounts_list, platforms_list, posts_list succeeded |
| Fresh plugin OAuth sign-in | Not exercised; existing authentication does not prove fresh login |
| Live upload / draft / deletion cycle | Not exercised in a designated disposable test workspace |
| Model behavior scenarios | Definitions in evals/workflows.json; no automated model run claimed |
| ChatGPT | Directory submission pending; this package not tested in ChatGPT |
| OpenClaw | CLI unavailable; flags not re-tested |

The local marketplace was newly registered and the package was previously uninstalled.
Codex installation was verified in the existing CLI configuration using a separate
short-lived app-server process, not a new authenticated user profile. The test
installation was removed afterward; the local marketplace remains available for review.

Live checks used an existing authenticated connection. No public posts or
schedule changes were made for package validation.

Reproduce static checks with [scripts/README.md](../scripts/README.md).
Follow [Codex setup](codex.md) for installation. Test the GitHub marketplace route
after publication before marking it verified.
