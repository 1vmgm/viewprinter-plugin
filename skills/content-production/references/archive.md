# Keep originals in the source archive

Every original a production uses goes into one archive, once, with where it came from:
generated takes and stills, device or screen captures, recordings, and licensed or
sourced audio, as they arrived and before any edit. Provider download links expire,
batch folders get cleaned up, and an original nobody can find gets paid for twice.
The archive is local files plus one catalog per project; `scripts/archive.py` makes no
network calls and uploads nothing. ViewPrinter can keep the originals too; see
[keep originals in ViewPrinter](#keep-originals-in-viewprinter-too).

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

Archive presence is not creative approval or performance evidence: rejected and unused
originals are kept too. Check the asset's latest status, rejection reason and the project's
feedback before selecting it. When a brief asks for proven footage, link the exact original
to its published post and dated result; a similar creator, an approved still or an unposted
take does not establish that link. Preserve the successful hook, performance and demo
sequence in the evidence, then state what the new edit changes. Follow the project's reuse
constraints; do not choose a rejected take merely to avoid generation cost.

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

## Keep originals in ViewPrinter too

ViewPrinter can hold every original as **source material**: kept with a summary, tags and
how it was made, listed only when asked for (`media_list` with `purpose: source`), never
posted or picked up by a campaign as it is, and not removable with `media_delete`. It is a
second copy that every computer signed in to the workspace can find, and it lets this one
let go of large files.

Ask once per project whether to keep originals there, and record the answer as
`archive.keepInViewPrinter` (true or false) in the project memory's `config.json`. With
true, store a batch's originals when they arrive or at its handoff, after
[describing them](#describe-originals-before-saving) when Gemini is set up. Files go up
through your ViewPrinter connector; the archive only says what to send and records what
ViewPrinter answers:

1. `archive.py upload-list --out list.json` gives up to 50 originals not stored yet
   (`--format`, `--batch`, `--status` and `--tag` narrow it), and brings along any
   original they were made from that isn't stored either. Pass their `upload` entries,
   unchanged and in order, as the `items` of one `media_upload` call, and save its answer
   as JSON. Save files with `--out` or your own file tool rather than a shell `>`, which
   in Windows PowerShell writes another encoding.
2. `archive.py upload-steps --list list.json --answers answer.json` pairs each answer with
   its original. It gives `put`: each file to PUT to its `url` with exactly its `headers`
   ([media upload](../../content-publishing/references/rules/media-upload.md)), within
   fifteen minutes. `save` holds what to describe once they land, `landed` the files
   ViewPrinter already had, and `unlinked` any input that wasn't in this call.
3. Record `landed` straight away: `archive.py stored --listed -` with it. Those files are
   never described again: one may be a library file someone wrote a description for.
4. After the PUTs, call `media_save` with `save` as its `items`. A drafted description is
   the original's summary when it has one; improve any other draft where you know what the
   file shows. Record its answer the same way:
   `stored` takes the `saved` files, matched to originals by the sha256 ViewPrinter read
   from the bytes. A file in `not_found` hasn't landed: check its PUT, save it again
   shortly, and record it then. Only what ViewPrinter's answers show is ever recorded.

Repeat until `upload-list` offers nothing you can upload. A file whose PUT failed or whose
link expired comes back on the next pass, for a fresh `media_upload`. Before generating,
search ViewPrinter too: `media_list` with `purpose: source` and `tags` or `search` finds
what any computer stored.

A generated file still at the provider's link can go from there instead of from this
computer. Archive it first, as always, and take its `describe` from `upload-list`; then
`media_upload` with `from_url`, `purpose: source` and that description, tags and
metadata. Record it with `stored` once `media_list` shows it.

Tags make source material findable: the project, the format, how it came to be
(`generated`, `captured`, `sourced`), a verdict (`selected`, `rejected`), the identity it
shows, then what it is (`creator-take`, `b-roll`, `screen-recording`, `sound-effect`,
`meme-template`). `upload-list` drafts them from the record.

### Describe originals before saving

A description is how anyone finds an original later, in ViewPrinter or with
`archive.py find --text`. The draft `upload-list` makes from a record says how a file was
made, not what it shows, and for a meme template, a music track or a capture it says almost
nothing. When Gemini is set up (`tools.py check` reports it ready), describe the originals
first:

```sh
python3 <skill-directory>/scripts/describe.py estimate --price-in <usd> --price-out <usd> [filters]
python3 <skill-directory>/scripts/describe.py run --model <model> --price-in <usd> --price-out <usd> --cap <usd> [filters]
```

1. **Estimate and ask.**
   - Read the model's current price per million input and output tokens from Google's
     pricing page and pass it. Nothing here assumes a price.
   - `estimate` counts the originals, how much of each Gemini would see, and what that
     should cost.
   - Tell the user that cost before running, as with any
     [paid step](tools.md#keep-the-user-informed-on-spending).
   - Ask before sending their files to Google.
2. **Run.**
   - `run` sends Gemini a small copy of each original: the first two minutes of a video or
     audio file, or an image shrunk when it is large.
   - It records what comes back in the catalog: the `summary`, the tags Gemini suggests and
     any on-screen text, with a receipt of the model, tokens and cost.
   - `find --text` then searches the summaries, and `upload-list` drafts each description
     from one.
   - `--cap` stops new requests once the run has spent that much. At the end, `run` reports
     what the run cost and what describing has cost this project so far.
3. **Repeats.**
   - A failed reply is still paid for. It is recorded with its cost and no summary, and the
     original is offered again next time.
   - `--again` describes an original anew. `--stored` includes originals ViewPrinter already
     keeps, whose descriptions there change only when you save them again.

The prompt keeps a description to what is in the file:
- No one is identified from their face or appearance. A name appears only when the file
  shows or says it, or the record gives it.
- Ages are ranges, and ethnicity is never guessed.

Read a sample before saving: Gemini can miss a sound or misjudge timing.

Tags are lower-case words joined by hyphens: `r-and-b`, not `R&B`. ViewPrinter refuses a
whole `media_save` call for one tag in another shape, so the archive reshapes every tag it
drafts.

### Free space on this computer

Once an original is stored, its local copy can go, but only with the user's agreement in
their words, and only on ViewPrinter's fresh word. List what ViewPrinter keeps with
`media_list` and `purpose: source`, following `nextCursor` to the last page. Save the pages'
answers together as one JSON list, and pass it to `release`:

```sh
python3 <skill-directory>/scripts/archive.py release --format <format-id> --listed listed.json --dry-run
python3 <skill-directory>/scripts/archive.py release --format <format-id> --listed listed.json --approval "<the user's words>"
```

`release` takes `--id`, `--format` or `--all-stored`. An original goes only when the
listing shows its media as source material with the original's sha256, and when the
local file still hashes to it. A file kept to post never stands in, since `media_delete`
can remove it. A dry run shows what would go, how many bytes, and why anything stays.
Space comes back only when no other copy shares the data: a batch folder's working copy
or a review's copy keeps it.

`find` marks released originals, and `checkout` of one says how to bring it back: get its
`url` from `media_list` with its `media_id`, download it, and run `archive.py restore --id
<id> --file <download> --move`. `restore` refuses a file that isn't that original, byte
for byte. A review keeps its own copies of what it shows, so releasing an original never
changes one.

Finished reviews can keep their copies in ViewPrinter too. The content review skill's
`review_media.py save` adds a finished review's files to this archive, tagged `review-media`,
for this same upload flow; see its [workspace](../../content-review/references/workspace.md#media-kept-in-viewprinter).

## Source and terms

Record where everything came from, and any license or usage terms the user gives, as
provenance on the asset (`allowedUses` included). Whether an asset is used, in a post, an
ad or anywhere else, is the user's decision: record it, don't enforce it.

## What stays out

Edit intermediates, renders that can be rebuilt, previews, contact sheets and galleries
stay with the batch. Finals stay with the batch and its uploads; a derived piece made for
reuse, such as a cleaned audio loop, may go in with `origin: edited` and its `inputs`. Keep
receipts in the catalog record, not as a JSON file per asset or per job.

ViewPrinter's media library, the files to post, is a different place: campaigns pick from
it automatically. Originals go to ViewPrinter only as source material, as above; putting
one in the library to post is a separate, authorized step through the content-publishing
skill.

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
its own copy if another path shares it. Nothing deletes an original outright: `release`
lets a local copy go only once ViewPrinter keeps it, with the user's approval recorded.
