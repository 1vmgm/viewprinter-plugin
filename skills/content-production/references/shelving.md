# Shelve finished Tesseract projects

A Tesseract project keeps a full copy of every clip, image, sound and font it uses inside
the `.tsrct` file. Every variant, draft and test copy stores the same footage again, so a
busy production can fill a disk within days. Shelving keeps each of those files once and
puts a small manifest where the project was. Unshelving rebuilds the exact original.

```sh
python3 <skill-directory>/scripts/shelf.py shelve <batch or project folder> --dry-run
python3 <skill-directory>/scripts/shelf.py shelve <batch or project folder>
python3 <skill-directory>/scripts/shelf.py unshelve <folder>/Project.tsrct
python3 <skill-directory>/scripts/shelf.py verify <folder>
```

It works on this computer only and uploads nothing.

## When to shelve

Shelve a batch's projects once its videos are approved or scheduled, or when the disk runs
low. Start with a dry run, which says how many projects would be shelved and how much space
it frees.

Projects changed in the last three days are skipped, and so are projects another program
has open. When the user says recent work is finished, `--min-age-days 0` includes it.

## Before working on a shelved project

A shelved project is `Project.tsrct.shelf.json`, in the place where `Project.tsrct` was.
Before editing, rendering or inspecting it, unshelve it:

```sh
python3 <skill-directory>/scripts/shelf.py unshelve <folder>/Project.tsrct
```

This rebuilds the exact file and checks it against the original's SHA-256 before it
appears. It never replaces an existing file. For a one-off render, `--to <file>` rebuilds a
copy and leaves the project shelved.

## How it stays safe

- **It checks before replacing.** A project is replaced only after its pieces, read back from the store, rebuild it exactly.
- **It never edits a project.** Tesseract only ever sees its own original bytes.
- **It refuses rather than guesses.** A damaged or missing piece makes unshelve fail; it never produces a different project.
- **It never deletes stored pieces.** The store is `~/ViewPrinter/shelf` (`VIEWPRINTER_SHELF` overrides). Deleting from it loses every project that uses those pieces.
- **The format is documented.** The store's README explains it, so a project can be rebuilt by joining its listed pieces in order.

## Habits that keep projects small

- Once a video's MP4 is approved, delete the full-quality master (a ProRes or other `.mov`)
  exported for it. The project can render it again.
- Don't keep test copies of a project after a change is committed. Save a checkpoint only
  before a substantial revision.
- Shelve the drafts and variants that the approved final superseded.
