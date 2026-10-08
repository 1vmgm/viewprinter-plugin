#!/usr/bin/env python3
"""Shelve Tesseract projects (.tsrct) nobody is working on, and bring them back exactly.

A Tesseract project is a ZIP holding the edit plus a full copy of every clip, image, sound
and font it uses, so the same footage sits inside every variant, draft and test copy.
Shelving splits a project's file into pieces: each large member's bytes, and the bytes
between them (ZIP headers, the edit, small files). Every piece is stored once, named by its
SHA-256, in the object store, and the project file is replaced by a small manifest beside it,
Project.tsrct.shelf.json, listing the pieces in order. Joining them recreates the original
byte for byte, which the manifest's sha256 proves. Nothing inside a project is edited:
Tesseract only ever sees its own original file.

    shelf.py shelve PATH... [--min-age-days 3] [--dry-run] [--limit N]
    shelf.py unshelve PATH... [--to FILE]
    shelf.py verify PATH...
    shelf.py status PATH...

PATH is a .tsrct file, a .shelf.json manifest or a folder to search. The store is
~/ViewPrinter/shelf (VIEWPRINTER_SHELF overrides). A project is shelved only after its
pieces, read back from the store, reproduce it exactly; it is skipped while open or
recently changed. Nothing here uploads anything or deletes a stored piece.
"""
import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import time
import uuid
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
    import msvcrt

FORMAT = "viewprinter-shelf/1"
SUFFIX = ".shelf.json"
MIN_MEMBER = 64 * 1024   # a member at least this big becomes its own piece
CHUNK = 1 << 20
LOCK_WAIT_SECONDS = 600
SKIP_DIRS = {"node_modules", ".git", "Pods", "DerivedData"}
README = """# Shelved Tesseract projects

Each file in `objects/` is one piece of one or more shelved Tesseract projects, named by its
SHA-256. A shelved project is a `Project.tsrct.shelf.json` manifest beside where the project
was. Its `pieces` list `[sha256, length]` in order: joined in that order, they rebuild the
original file exactly, whose length and SHA-256 the manifest's `bytes` and `sha256` give.

Rebuild a project with the ViewPrinter plugin's content-production `scripts/shelf.py
unshelve <manifest>`, or by joining the pieces yourself and checking the result. Pieces are
never deleted automatically; deleting one loses every project that uses it.
"""


class ShelfError(Exception):
    pass


def store():
    return Path(os.environ.get("VIEWPRINTER_SHELF") or Path.home() / "ViewPrinter" / "shelf").expanduser()


def object_path(sha):
    return store() / "objects" / sha[:2] / sha


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@contextmanager
def locked():
    """One shelve or unshelve at a time per store."""
    store().mkdir(parents=True, exist_ok=True)
    with open(store() / ".lock", "a+b") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        else:
            deadline = time.monotonic() + LOCK_WAIT_SECONDS
            while True:
                try:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise
                    time.sleep(0.05)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            else:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def log(event):
    with open(store() / "shelved.jsonl", "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def link_new(temp, target):
    """Move temp to target only if target does not exist yet; never replaces a file."""
    try:
        os.link(temp, target)
    except FileExistsError:
        raise
    except OSError:
        # No hard links here. Windows' rename refuses an existing target; elsewhere, check first.
        if os.name != "nt" and target.exists():
            raise FileExistsError(str(target))
        os.rename(temp, target)
        return
    os.unlink(temp)


def member_ranges(path, size):
    """Where each large member's bytes sit, in file order. None when the file is not a ZIP whose
    members can be located exactly; such a file is left alone."""
    try:
        with zipfile.ZipFile(path) as archive, open(path, "rb") as handle:
            ranges = []
            for info in archive.infolist():
                if info.compress_size < MIN_MEMBER:
                    continue
                handle.seek(info.header_offset)
                head = handle.read(30)
                if len(head) != 30 or head[:4] != b"PK\x03\x04":
                    return None
                name_length, extra_length = struct.unpack("<HH", head[26:30])
                start = info.header_offset + 30 + name_length + extra_length
                end = start + info.compress_size
                if end > size:
                    return None
                ranges.append((start, end))
    except (zipfile.BadZipFile, OSError, ValueError, struct.error):
        return None
    ranges.sort()
    for (_, end), (start, _) in zip(ranges, ranges[1:]):
        if end > start:
            return None
    return ranges


def pieces_of(size, ranges):
    pieces, position = [], 0
    for start, end in ranges:
        if start > position:
            pieces.append((position, start))
        pieces.append((start, end))
        position = end
    if position < size:
        pieces.append((position, size))
    return pieces


def read_range(handle, start, end):
    handle.seek(start)
    left = end - start
    while left:
        block = handle.read(min(CHUNK, left))
        if not block:
            raise ShelfError("file ended early")
        left -= len(block)
        yield block


def put_object(handle, start, end, sha):
    """Copy handle[start:end] into the store as sha, checking the copy as it is written."""
    target = object_path(sha)
    if target.exists():
        if target.stat().st_size != end - start:
            raise ShelfError("store object has the wrong size: " + sha)
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.parent / ("." + uuid.uuid4().hex)
    digest = hashlib.sha256()
    try:
        with open(temp, "wb") as out:
            for block in read_range(handle, start, end):
                digest.update(block)
                out.write(block)
            out.flush()
            os.fsync(out.fileno())
        if digest.hexdigest() != sha:
            raise ShelfError("project changed while it was being shelved")
        try:
            link_new(temp, target)
            os.chmod(target, 0o444)   # stored pieces never change
        except FileExistsError:   # another run stored the same bytes first
            pass
    finally:
        if temp.exists():
            temp.unlink()
    return end - start


def rebuild(manifest, out=None):
    """Join the manifest's pieces from the store, checking them against the original's size and
    sha256. With out, also writes them there."""
    digest, total = hashlib.sha256(), 0
    for sha, length in manifest["pieces"]:
        try:
            handle = open(object_path(sha), "rb")
        except FileNotFoundError:
            raise ShelfError("missing store object " + sha)
        with handle:
            got = 0
            for block in iter(lambda: handle.read(CHUNK), b""):
                digest.update(block)
                got += len(block)
                if out is not None:
                    out.write(block)
        if got != length:
            raise ShelfError("store object has the wrong size: " + sha)
        total += got
    if total != manifest["bytes"] or digest.hexdigest() != manifest["sha256"]:
        raise ShelfError("pieces do not rebuild the original")


def open_projects():
    """Every .tsrct some program has open right now, and whether that could be checked. Without
    lsof (or on Windows, where an open file can't be deleted anyway) the age rule decides."""
    if os.name == "nt" or not shutil.which("lsof"):
        return set(), False
    result = subprocess.run(["lsof", "-Fn"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                            timeout=300)
    if result.returncode not in (0, 1) and not result.stdout:
        raise ShelfError("could not list open files: " + result.stderr.strip())
    return {line[1:] for line in result.stdout.splitlines() if line.startswith("n") and ".tsrct" in line}, True


def write_readme():
    readme = store() / "README.md"
    if not readme.exists():
        readme.write_text(README, encoding="utf-8")


def shelve_one(path, min_age_days, busy, dry_run, planned):
    info = path.lstat()
    if path.is_symlink() or not path.is_file():
        return "skipped", "not a regular file", 0, 0
    if info.st_nlink > 1:
        return "skipped", "has other hard links", 0, 0
    if time.time() - info.st_mtime < min_age_days * 86400:
        return "skipped", "changed in the last %g days" % min_age_days, 0, 0
    if str(path) in busy or str(path.resolve()) in busy:
        return "skipped", "open in another program", 0, 0
    manifest_path = path.with_name(path.name + SUFFIX)
    if manifest_path.exists():
        return "skipped", "a shelf manifest already exists beside it", 0, 0
    ranges = member_ranges(path, info.st_size)
    if ranges is None:
        return "skipped", "not a ZIP this tool can split exactly", 0, 0
    if not ranges:
        return "skipped", "no large files inside to share", 0, 0
    whole, pieces, stored = hashlib.sha256(), [], 0
    with open(path, "rb") as handle:
        for start, end in pieces_of(info.st_size, ranges):
            digest = hashlib.sha256()
            for block in read_range(handle, start, end):
                digest.update(block)
                whole.update(block)
            sha = digest.hexdigest()
            pieces.append([sha, end - start])
            if dry_run:
                if sha not in planned and not object_path(sha).exists():
                    planned.add(sha)
                    stored += end - start
            else:
                stored += put_object(handle, start, end, sha)
    if dry_run:
        return "would shelve", "", info.st_size, stored
    manifest = {
        "format": FORMAT, "project": path.name, "bytes": info.st_size, "sha256": whole.hexdigest(),
        "mtime": info.st_mtime, "mode": info.st_mode & 0o7777, "shelvedAt": now_iso(),
        "members": len(ranges), "pieces": pieces, "store": str(store()),
        "restore": "Run the content-production skill's scripts/shelf.py unshelve on this file.",
    }
    rebuild(manifest)   # read back from the store: must reproduce the original exactly
    after = path.stat()
    if (after.st_size, after.st_mtime_ns) != (info.st_size, info.st_mtime_ns):
        raise ShelfError("project changed while it was being shelved")
    temp = manifest_path.with_name("." + manifest_path.name + "." + uuid.uuid4().hex)
    try:
        with open(temp, "w", encoding="utf-8") as out:
            json.dump(manifest, out, indent=1)
            out.flush()
            os.fsync(out.fileno())
        link_new(temp, manifest_path)
    finally:
        if temp.exists():
            temp.unlink()
    try:
        os.unlink(path)
    except OSError:
        manifest_path.unlink()   # still in use: leave the project as it was
        return "skipped", "in use; it could not be removed", 0, 0
    log({"event": "shelved", "path": str(path), "bytes": info.st_size, "sha256": manifest["sha256"],
         "storedBytes": stored, "at": manifest["shelvedAt"]})
    return "shelved", "", info.st_size, stored


def unshelve_one(manifest_path, to=None):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != FORMAT:
        raise ShelfError("not a shelf manifest: " + str(manifest_path))
    target = Path(to) if to else manifest_path.with_name(manifest_path.name[: -len(SUFFIX)])
    if target.exists():
        raise ShelfError("a file already exists at {}; left both as they are".format(target))
    temp = target.with_name("." + target.name + "." + uuid.uuid4().hex)
    try:
        with open(temp, "wb") as out:
            rebuild(manifest, out)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temp, manifest.get("mode", 0o644))
        link_new(temp, target)
    finally:
        if temp.exists():
            temp.unlink()
    if not to:
        # Back in use: its time is now, so a later shelve run leaves it alone for a while.
        manifest_path.unlink()
        log({"event": "unshelved", "path": str(target), "sha256": manifest["sha256"], "at": now_iso()})
    return target


def find(paths, want):
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if path.is_file() or path.is_symlink():
            if want(path):
                yield path
            continue
        for folder, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and Path(folder, d) != store()]
            for name in sorted(files):
                candidate = Path(folder, name)
                if want(candidate):
                    yield candidate


def manifests_for(paths):
    """The manifests the user means: a folder's manifests, a manifest itself, or the manifest of a
    shelved project named by its original .tsrct path."""
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_dir():
            yield from find([path], is_manifest)
        elif path.name.endswith(SUFFIX):
            yield path.resolve()
        else:
            yield path.resolve().with_name(path.name + SUFFIX)


def is_project(path):
    return path.name.endswith(".tsrct") and not path.name.startswith(".")


def is_manifest(path):
    return path.name.endswith(".tsrct" + SUFFIX) and not path.name.startswith(".")


def gb(n):
    return "{:.2f} GB".format(n / 1e9)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    shelve = sub.add_parser("shelve", help="store large files once and replace projects with manifests")
    shelve.add_argument("paths", nargs="+")
    shelve.add_argument("--min-age-days", type=float, default=3, help="skip projects changed more recently (default 3)")
    shelve.add_argument("--dry-run", action="store_true", help="say what would be shelved and freed, change nothing")
    shelve.add_argument("--limit", type=int, help="shelve at most this many projects")
    unshelve = sub.add_parser("unshelve", help="rebuild projects exactly from their manifests")
    unshelve.add_argument("paths", nargs="+")
    unshelve.add_argument("--to", help="rebuild one project to this file and keep it shelved")
    sub.add_parser("verify", help="rebuild each shelved project in memory and check it").add_argument("paths", nargs="+")
    sub.add_parser("status", help="shelved projects and the store's size").add_argument("paths", nargs="+")
    args = parser.parse_args(argv)

    if args.command == "shelve":
        counts, reasons, freed, stored, failures = {}, {}, 0, 0, []
        with locked():
            write_readme()
            busy, checked = open_projects()
            planned = set()
            for path in find(args.paths, is_project):
                if args.limit is not None and counts.get("shelved", 0) + counts.get("would shelve", 0) >= args.limit:
                    break
                try:
                    outcome, reason, size, new = shelve_one(path, args.min_age_days, busy, args.dry_run, planned)
                except (ShelfError, OSError) as exc:
                    outcome, reason, size, new = "failed", str(exc), 0, 0
                    failures.append("{}: {}".format(path, exc))
                counts[outcome] = counts.get(outcome, 0) + 1
                if reason:
                    reasons[reason] = reasons.get(reason, 0) + 1
                freed += size
                stored += new
        report = {"outcomes": counts, "skipReasons": reasons, "projectBytes": gb(freed),
                  "newStoreBytes": gb(stored), "diskFreed": gb(freed - stored), "failures": failures[:20]}
        if not checked:
            report["note"] = "Open files could not be checked here; projects changed recently were skipped."
        print(json.dumps(report, indent=1))
        return 1 if failures else 0

    if args.command == "unshelve":
        manifests = list(manifests_for(args.paths))
        if args.to and len(manifests) != 1:
            parser.error("--to rebuilds exactly one project")
        failed = 0
        with locked():
            for manifest in manifests:
                try:
                    print("restored", unshelve_one(manifest, args.to))
                except (ShelfError, OSError, ValueError) as exc:
                    failed += 1
                    print("failed", manifest, exc, file=sys.stderr)
        return 1 if failed else 0

    manifests = list(find(args.paths, is_manifest))
    if args.command == "verify":
        bad = 0
        for manifest_path in manifests:
            try:
                rebuild(json.loads(manifest_path.read_text(encoding="utf-8")))
            except (ShelfError, OSError, ValueError) as exc:
                bad += 1
                print("FAILED", manifest_path, exc)
        print(json.dumps({"verified": len(manifests) - bad, "failed": bad}))
        return 1 if bad else 0

    total = sum(json.loads(m.read_text(encoding="utf-8"))["bytes"] for m in manifests)
    objects = [o for o in (store() / "objects").glob("*/*") if not o.name.startswith(".")]
    print(json.dumps({"shelvedProjects": len(manifests), "shelvedProjectBytes": gb(total),
                      "storeObjects": len(objects), "storeBytes": gb(sum(o.stat().st_size for o in objects))}, indent=1))
    return 0


if __name__ == "__main__":
    # Agents read this through a pipe, which on Windows defaults to the system code page.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
