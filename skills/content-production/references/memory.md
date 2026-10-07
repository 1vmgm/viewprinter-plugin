# Durable project memory

The installed skill is replaceable; project memory is not. Keep stable join keys, a separate carry-forward, append-only changes and findings, and project configuration outside the plugin.

## Locate and initialize

`memory.py locate --start <directory>` walks working-directory ancestors for `.viewprinter/content-memory`. The project is the directory holding `.viewprinter/`, so config stores no path: a moved or renamed project, a clone and a git worktree each use the memory inside them, and committed memory carries no home-directory path. An older config's absolute `projectRoot` is ignored and can be deleted.

`VIEWPRINTER_CONTENT_MEMORY` selects an explicit memory directory and wins over discovery; every project run with it set uses that memory. Resolve relative overrides from the working directory, never the skill location. A missing/invalid override is an error, not permission to create memory somewhere else.

`memory.py init --project <root> --name <name>` initializes the standard location or the explicit override. It preserves valid existing memory and refuses partial memory. Symlinks above the memory, such as macOS `/tmp`, are resolved; none are allowed from `.viewprinter` down, so writes cannot be redirected. Installation and release packaging never initialize, overwrite or include project memory. Shared artifacts may live elsewhere; store their actual references rather than copying huge media into memory. Originals live in the [source archive](archive.md), and memory refers to them by archive ID.

## Responsibilities

| Location | Contents | Update behavior |
|---|---|---|
| `config.json` | Schema version and project name; add defaults such as asset paths, relative to the memory directory, only as needed, and `archive.project` / `archive.root` for the [source archive](archive.md) | Targeted, deliberate edits |
| `project.md` | Current brand preferences, production conventions, review expectations and their scope | Update the affected rule; preserve provenance and exceptions |
| `assets/phone-mounts/<id>/v<revision>/` | Canonical frame, fitted screen geometry/mask, provenance and approved reference; `config.json` points to the default preset | Preserve existing revisions; copy exact assets rather than regenerate |
| `formats/<id>/v<revision>.json` | Concept, presentation structure, invariants, allowed variation, prototype references and decision source | New immutable revision |
| `batches/<id>/batch.json` | Active round, format revisions, item/version inventory, output paths and current statuses | One writer per batch; reread before editing |
| `batches/<id>/rounds/<round>/review.json` | Immutable manifest for that round's HTML | New file per round; don't rewrite an old review |
| `state/carry-forward.json` | Open questions, blocked dependencies, next actions, owner and due/recheck condition | Targeted status edits; never replace with a generated summary |
| `history/feedback/<event>.json` | Verbatim user feedback plus interpreted scope and item/version references | Immutable event |
| `history/changes/<event>.json` | What changed, from/to version, why, artifacts and originating feedback | Immutable event |
| `history/findings/<event>.json` | What was learned, evidence, confidence, applicability, supersedes and extracted rule/test | Immutable event |

Use JSON for identities and records you join/filter; Markdown for reasoning and preferences people read. Reference the original evidence rather than maintaining two competing copies of a long conclusion. Keep secrets and signed upload URLs in appropriate private credential/receipt storage, not in shared memory or the public plugin. Memory is local filesystem state, not a hosted ViewPrinter service.

## IDs and approvals

Use stable descriptive IDs such as `format-interview`, `batch-autumn-01`, `clip-007`. Renaming a title or moving a file does not change its ID. Every item version records source/format revision and path or hash. Approval record: item ID, version, user statement/source, time and scope. A global style change can revise an approved item; preserve its old approval while marking the new version for review. Format approval, creative approval, upload authorization and publishing authorization are separate facts. Session instructions can authorize several together.

Do not store an unresolved question only in a chat summary. Carry it forward with the exact dependency and next action. A renderer failure is not a rejection of the concept. Closing an investigation adds a finding; it does not erase the question's history.

## Safe event writing

Create a JSON event containing at least `id` and `createdAt`, then use:

```sh
python3 <skill-directory>/scripts/memory.py append --memory <memory-root> --collection feedback --file <event.json>
```

The event file may live anywhere, including a temporary directory. The helper writes one immutable file per event and rejects conflicting reuse of an ID. Identical retries are safe. Independent agents append different IDs without rewriting each other's history. It is not a general transaction engine: assign a single writer for a batch's mutable inventory and carry-forward edits. Before editing, reread the current file; if it changed since inspection, merge the specific change or stop the conflicting edit. Never restore a stale full snapshot over newer work.

Suggested feedback event fields: `id`, `createdAt`, `batchId`, `round`, `rawText`, `source`, `targets` (item ID/version), `actions`, `scope`, `exceptions`, `ambiguities`. Suggested finding fields: `question`, `method`, `evidence`, `verdict`, `confidence`, `scope`, `supersedes`, `ruleExtracted`, `recheckWhen`. The helper enforces safe storage, not the truth or completeness of those fields.

At session end, summarize the active round, accepted versions, unresolved work and next step. On resume, read those records before generating anything. Keep memory private by default; use the project's existing tracking policy for non-sensitive records. Never add the whole directory to a public repository as a convenience.
