# Keep originals in the source archive

Every original a production uses goes into one archive, once, with where it came from:
generated takes and stills, device or screen captures, recordings, and licensed or
sourced audio, as they arrived and before any edit. Provider download links expire,
batch folders get cleaned up, and an original nobody can find gets paid for twice.
The archive is local files plus one catalog per project; `scripts/archive.py` makes no
network calls and uploads nothing.

## Save on arrival

Add each original as soon as it downloads or a capture finishes, before trimming,
grading or conversion. Rejected and unused attempts go in too: they show what failed,
and a take wrong for one story can be right for another.

```sh
python3 <skill-directory>/scripts/archive.py add --file <original> --format <format-id> --record - <<'JSON'
{"origin": "generated", "tool": "<provider>", "model": "<model>", "requestId": "<job id>",
 "prompt": "<exact prompt>", "inputs": ["<archive id of a reference>"], "identity": "<identity id>",
 "settings": {"seconds": 4, "resolution": "1080p"},
 "cost": {"amount": 4.55, "unit": "usd", "basis": "estimate"},
 "batchId": "<batch>", "itemId": "<item>", "tags": ["couch", "night"]}
JSON
```

| Field | Meaning |
|---|---|
| `origin` | `generated`, `captured`, `recorded`, `licensed`, `sourced` or `edited` |
| `tool`, `model`, `requestId` | What made it and the job ID, so a lost response can be checked instead of paid for again |
| `prompt`, `inputs`, `settings` | The exact prompt, the archive IDs of reference inputs, and the settings that matter for a remake |
| `identity` | The recurring person, character or voice it shows, as an ID |
| `cost` | `amount`, `unit` and `basis` (`reported`, `estimate` or `unknown`); never a guessed credit figure |
| `rights` | `source`, `license` and `allowedUses` (for example `["organic"]`) |
| `status`, `reason` | `candidate` until judged, then `selected` or `rejected` with the reason |
| `tags`, `batchId`, `itemId` | What it shows, and the batch item it was made for |

Fill what is known and leave out the rest; the helper checks types, not truth. Never put
credentials, tokens or signed download URLs in a record. The same content is stored once:
adding it again returns the existing ID with `duplicate: true`. The format folder is the
format it was made for; reuse elsewhere is recorded, not moved. IDs and format names that
differ from existing ones only in case are refused, because most disks treat them as one.

## Reuse before generating

Search before paying for a new generation, and reuse an original when it still tells the
intended story. Say which assets in a batch are reused and which are new.

```sh
python3 <skill-directory>/scripts/archive.py find --format <format-id> --text "<words from the prompt>"
python3 <skill-directory>/scripts/archive.py checkout --id <id> --to <batch folder> --batch <batch> --item <item> --version <n>
python3 <skill-directory>/scripts/archive.py note --id <id> --status rejected --reason "<what was wrong>"
```

`find` also filters by `--kind`, `--status`, `--tag`, `--identity` and `--allowed-use`, and
`--all-projects` searches every project. `checkout` puts a working copy in the batch (a
copy-on-write clone where the disk supports it, so it costs no space) and records the use.
Edit the copy; the original is never changed. `note` records later facts without
rewriting the catalog.

Identities are IDs, not files: archive an identity's approved reference images with its
`identity` and list them in the `inputs` of every generation that used them. Who an
identity is, and where it may appear, belongs to project memory or the project's own skill.

## Source and terms

Record where everything came from, and any license or usage terms the user gives, as
provenance on the asset (`allowedUses` included). Whether an asset is used, in a post, an
ad or anywhere else, is the user's decision: record it, don't enforce it.

## What stays out

Edit intermediates, renders that can be rebuilt, previews, contact sheets and galleries
stay with the batch. Finals stay with the batch and its uploads; a derived piece made for
reuse, such as a cleaned audio loop, may go in with `origin: edited` and its `inputs`. Keep
receipts in the catalog record, not as a JSON file per asset or per job.

The ViewPrinter media library is a different place: campaigns pick from it automatically.
Nothing in the archive is uploaded on its own; adding an asset there is a separate,
authorized step through the content-publishing skill.

## Location

The root is `--root`, else `VIEWPRINTER_ARCHIVE_ROOT`, else `archive.root` in the project
memory's `config.json` (relative to the memory directory), else `~/ViewPrinter/archive`.
The project ID is `--project`, else `archive.project` in that config, else the project
name as a slug; the project `shared` holds assets used across projects, such as music
beds and sound effects. `archive.py where` shows what resolves.

```
<root>/<project>/catalog.jsonl                one line per event, never rewritten
<root>/<project>/<format>/<kind>/<id><ext>    the original
```

Paths in the catalog are relative, so the archive can move: copy the root to an external
drive or any folder a backup or sync tool copies, point `VIEWPRINTER_ARCHIVE_ROOT` at it,
then run `archive.py verify --all-projects --rehash`. Only one machine at a time should
write to it; the lock does not reach across machines. The root itself may be a symlink;
nothing inside it may be. A root inside a repository must be ignored by git.

`verify` reports:
- originals that are missing or changed;
- originals that share their data with another path, so that editing the path would change
  the original;
- files the catalog doesn't list, and any symlink inside the archive;
- unfinished copies (`.incoming-…`): the source was never moved, so they can be deleted;
- originals an interrupted restore moved in (`.moving-…`): add them again to finish;
- catalog lines a crash cut off (`catalog.jsonl.cut-…`).

Adding the same content again restores a missing or wrong-size original, and the
wrong-size file is set aside as `….changed-…`, not deleted. With `--move`, a plain file
on the same disk is renamed in; a symlink or a file with other names is copied, and only
the path given is removed. A file catalogued where it already sits in the archive gets
its own copy if another path shares it. There is no delete command: removing an original
needs the user's explicit approval, recorded with a `note`.
