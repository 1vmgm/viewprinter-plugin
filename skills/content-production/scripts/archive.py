#!/usr/bin/env python3
"""Keep every original a production uses, once, with where it came from, so later
batches can find and reuse it instead of paying to make it again.

An original is the file as it arrived, before any edit: a generated take or still, a
device or screen capture, a recording, or licensed or sourced audio. Rejected
attempts are kept too, with the reason.

Python standard library only. No network calls; nothing is uploaded. The archive must
live outside the installed skill and by default lives in your home folder, not in a
project; a root inside a repository has to be ignored by git.

  root     --root, else $VIEWPRINTER_ARCHIVE_ROOT, else "archive.root" in the
           project memory's config.json, else ~/ViewPrinter/archive
  project  --project, else "archive.project" in config.json, else the memory's
           projectName as a slug. "shared" holds assets for several projects.

  <root>/<project>/catalog.jsonl                one line per event, never rewritten
  <root>/<project>/<format>/<kind>/<id><ext>    the original, never edited

Commands: add, note, find, show, checkout, verify, where.
"""

import argparse
import contextlib
from datetime import datetime, timezone
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
    import msvcrt

import memory as project_memory

ROOT_ENVIRONMENT = "VIEWPRINTER_ARCHIVE_ROOT"


def installed_roots(skill=Path(__file__).resolve().parents[1]):
    """This skill's folder and the install around it: a skills folder, a package carrying
    skills, a plugin. An update replaces them, and anything kept there with them."""
    roots = [skill]
    for folder in skill.parents:
        if not (folder.name == "skills" or (folder / "SKILL.md").is_file()
                or any((folder / marker).exists() for marker in (".claude-plugin", ".codex-plugin", "plugin.json"))):
            break
        roots.append(folder)
    return roots


INSTALLED = installed_roots()
CATALOG = "catalog.jsonl"
# A generation helper's ledger of paid jobs, kept beside the catalog so a job whose
# response was lost is resumed, not paid for twice.
JOBS = "jobs.jsonl"
INCOMING = ".incoming-"  # a verified copy on its way in; the source still exists
MOVING = ".moving-"  # a source moved in to restore an original, about to take its name
UNFILED = "unfiled"
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
STATUSES = ("candidate", "selected", "rejected")
COST_BASES = ("reported", "estimate", "unknown")
KINDS = {
    "video": {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"},
    "image": {".png", ".jpg", ".jpeg", ".webp", ".gif", ".heic", ".tif", ".tiff", ".bmp"},
    "audio": {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".aif", ".aiff", ".opus"},
}
# Set by the archive, or only ever part of an answer: never accepted in a record.
COMPUTED = ("event", "sha256", "bytes", "path", "archivedAt", "notedAt", "originalName", "restoredAt",
            "noteCount", "updatedAt", "file", "duplicate", "restored", "project", "events")
FIXED_AFTER_ADD = ("id", "kind", "format")
LOCK_WAIT_SECONDS = 600
# The errors a file system gives when it cannot lock a folder at all (some network disks).
NO_FOLDER_LOCKS = {getattr(errno, name) for name in ("ENOTSUP", "EOPNOTSUPP", "EBADF", "EINVAL", "ENOSYS", "ENOLCK")
                   if hasattr(errno, name)}


class ArchiveError(ValueError):
    """An unsafe path, a conflicting record or a missing original."""


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Location


def resolve(root=None, project=None, start=None):
    """The archive root and project ID, from the flags, the environment and the
    project memory's config.json, in that order."""
    config, memory, name, problem = {}, None, None, None
    if project is None or (root is None and not os.environ.get(ROOT_ENVIRONMENT)):
        try:
            found = project_memory.locate(start)
            settings = project_memory.read_object(found / "config.json")
        except project_memory.MemoryError as error:
            problem = error
        else:
            memory, name = found, settings.get("projectName")
            config = settings["archive"] if isinstance(settings.get("archive"), dict) else {}
    if project is None:
        project = config.get("project") or (slugify(name) if name else None)
        if not project:
            raise ArchiveError("Pass --project, or run inside a project with ViewPrinter memory ({})".format(
                problem or "its config.json has no archive.project or projectName"))
    check_id(project, "project")
    if root is None:
        root = os.environ.get(ROOT_ENVIRONMENT) or None
    if root is None and config.get("root"):
        root = Path(config["root"]).expanduser()
        root = root if root.is_absolute() else memory / root
    if root is None:
        root = Path.home() / "ViewPrinter" / "archive"
    root = Path(os.path.abspath(Path(root).expanduser())).resolve()
    if any(root == installed or installed in root.parents for installed in INSTALLED):
        raise ArchiveError("The archive must live outside the installed skills: {}".format(root))
    return root, project


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")


def memory_formats(project, start=None):
    """The format IDs and old-name aliases in the project memory that belongs to `project`,
    or None when there is no such memory to check against."""
    try:
        memory = project_memory.locate(start)
        settings = project_memory.read_object(memory / "config.json")
    except project_memory.MemoryError:
        return None
    archive_settings = settings.get("archive") if isinstance(settings.get("archive"), dict) else {}
    if (archive_settings.get("project") or slugify(settings.get("projectName") or "")) != project:
        return None
    folder = memory / "formats"
    ids = {path.name for path in folder.iterdir() if path.is_dir()} if folder.is_dir() else set()
    aliases = {}
    for path in sorted(folder.glob("*/v*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(record, dict) and isinstance(record.get("id"), str):
            ids.add(record["id"])
            ids.update(sub for sub in record.get("subFormats") or [] if isinstance(sub, str))
            aliases.update({alias: record["id"] for alias in record.get("aliases") or [] if isinstance(alias, str)})
    # An old name stays an alias even where its superseded records still sit in a folder.
    return ids - set(aliases), aliases


def canonical_format(project, format_id, start=None):
    """The project's current ID for a format: an old name becomes its current ID, and an
    unknown one is kept with a warning."""
    known = memory_formats(project, start)
    if known is None or format_id in (None, UNFILED):
        return format_id
    ids, aliases = known
    if format_id in aliases:
        print("archive: format {} is an old name; filing under {}".format(format_id, aliases[format_id]),
              file=sys.stderr)
        return aliases[format_id]
    if format_id not in ids:
        print("archive: format {} is not one of this project's formats (formats/<id>/ in project memory); "
              "check the ID".format(format_id), file=sys.stderr)
    return format_id


def check_id(value, what):
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise ArchiveError("{} must be 1-128 letters, digits, dots, dashes or underscores: {!r}".format(what, value))


def inside(base, relative):
    """A path under `base`, refusing a symlink at any component so nothing is redirected."""
    path = base
    for part in Path(relative).parts:
        if part in ("..", os.sep) or Path(part).is_absolute():
            raise ArchiveError("Path escapes the archive: {}".format(relative))
        path = path / part
        if path.is_symlink():
            raise ArchiveError("Symlinks are not allowed inside the archive: {}".format(path))
    return path


def project_directory(root, project, create=True):
    check_id(project, "project")
    path = inside(root, project)
    if create:
        path.mkdir(parents=True, exist_ok=True)
    elif not path.is_dir():
        raise ArchiveError("No archive for project {} under {}".format(project, root))
    return path


# ---------------------------------------------------------------------------
# The catalog: one append-only log per project
#
# One line per event instead of a file per asset: an archive holds tens of
# thousands of originals, and a sidecar each would bury them. Writers hold the
# project's lock, so agents working in parallel append safely.


def lock_file(directory):
    """The .lock file inside a project folder that cannot be locked itself."""
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    # 0o666 less the umask, so everyone who may write the folder can take its lock.
    return os.fdopen(os.open(directory / ".lock", flags, 0o666), "r+b")


def acquire(handle):
    if fcntl is not None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        return
    # LK_LOCK gives up after ten seconds; keep trying while another writer finishes.
    deadline = time.monotonic() + LOCK_WAIT_SECONDS
    while True:
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.05)


def release(handle):
    if fcntl is not None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    else:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


@contextlib.contextmanager
def locked(directory):
    """Hold the project's lock: on macOS and Linux the folder itself, so no lock file
    appears; where a folder cannot be locked, a .lock file inside it. Hold it briefly:
    copying and hashing happen before it is taken."""
    descriptor = None
    if fcntl is not None:
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
        except OSError as error:
            os.close(descriptor)
            descriptor = None
            if error.errno not in NO_FOLDER_LOCKS:  # anything else is a real failure
                raise
        except BaseException:
            os.close(descriptor)
            raise
    if descriptor is not None:
        try:
            yield
        finally:
            os.close(descriptor)  # closing releases the lock
        return
    with lock_file(directory) as handle:
        acquire(handle)
        try:
            yield
        finally:
            release(handle)


def log_line(record):
    try:
        text = json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ArchiveError("Record is not valid JSON: {}".format(error)) from error
    return (text + "\n").encode("utf-8")


def parse_record(line):
    try:
        record = json.loads(line)
    except ValueError:
        return None
    return record if isinstance(record, dict) else None


def complete_length(stream, size):
    """Bytes up to and including the last newline."""
    position = size
    while position > 0:
        start = max(0, position - 65536)
        stream.seek(start)
        index = stream.read(position - start).rfind(b"\n")
        if index >= 0:
            return start + index + 1
        position = start
    return 0


def append_line(path, line):
    """Append one line; call with the project's lock held. A last line without its
    newline is kept when it is a whole record (an edit dropped the newline). Otherwise
    it is the remains of a write a crash interrupted, whose writer never reported
    success: it moves to a .cut file beside the catalog."""
    with open(path, "a+b") as stream:
        size = stream.seek(0, os.SEEK_END)
        keep = complete_length(stream, size) if size else 0
        if keep < size:
            stream.seek(keep)
            tail = stream.read(size - keep)
            if parse_record(tail) is not None:
                line = b"\n" + line
            else:
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                side = path.with_name("{}.cut-{}".format(path.name, stamp))
                side.write_bytes(tail)
                stream.truncate(keep)
                print("archive: moved an unfinished last line of {} to {}".format(path, side), file=sys.stderr)
        stream.write(line)
        stream.flush()
        os.fsync(stream.fileno())


def read_log(path):
    """The events in a catalog. A last line without its newline counts when it is a
    whole record and is skipped when it is not: a write in progress, or a crash's."""
    if not path.exists():
        return []
    data = path.read_bytes()
    cut = data.rfind(b"\n") + 1
    events = []
    for number, line in enumerate(data[:cut].split(b"\n"), 1):
        if not line.strip():
            continue
        event = parse_record(line)
        if event is None:
            raise ArchiveError("{} line {} is not a JSON object".format(path, number))
        events.append(event)
    if data[cut:].strip():
        event = parse_record(data[cut:])
        if event is None:
            print("archive: skipping an unfinished last line in {}".format(path), file=sys.stderr)
        else:
            events.append(event)
    return events


def strings(value):
    return [v for v in (value if isinstance(value, list) else [value]) if isinstance(v, str)]


def apply_note(asset, event):
    for key, value in event.items():
        if key in COMPUTED or key in FIXED_AFTER_ADD:
            continue
        if key == "tags":
            asset["tags"] = sorted(set(strings(asset.get("tags"))) | set(strings(value)))
        elif key == "untag":
            asset["tags"] = sorted(set(strings(asset.get("tags"))) - set(strings(value)))
        elif key == "usedIn":
            used = asset.get("usedIn") if isinstance(asset.get("usedIn"), list) else []
            asset["usedIn"] = used + [use for use in (value if isinstance(value, list) else []) if use not in used]
        else:
            asset[key] = value
    if event.get("restoredAt"):
        asset["restoredAt"] = event["restoredAt"]
    count = asset.get("noteCount")
    asset["noteCount"] = (count if isinstance(count, int) else 0) + 1
    asset["updatedAt"] = event.get("notedAt")
    return asset


def catalog(project_dir):
    return inside(project_dir, CATALOG)


def assets(project_dir):
    """Every asset's current state: its add event with later notes applied in order."""
    state = {}
    for event in read_log(catalog(project_dir)):
        identifier = event.get("id")
        if event.get("event") == "add" and isinstance(identifier, str) and isinstance(event.get("path"), str):
            state.setdefault(identifier, dict(event))
        elif event.get("event") == "note" and isinstance(identifier, str) and identifier in state:
            apply_note(state[identifier], event)
    return state


# ---------------------------------------------------------------------------
# Records


def validate(record, note=False):
    if not isinstance(record, dict):
        raise ArchiveError("A record must be a JSON object")
    for key in COMPUTED + (FIXED_AFTER_ADD if note else ()):
        if key in record:
            raise ArchiveError("{} is set by the archive and cannot be given{}".format(
                key, " in a note" if note else ""))
    if "status" in record and record["status"] not in STATUSES:
        raise ArchiveError("status must be one of: {}".format(", ".join(STATUSES)))
    for key in ("tags", "untag", "inputs"):
        if key in record and not (isinstance(record[key], list) and all(isinstance(v, str) for v in record[key])):
            raise ArchiveError("{} must be a list of strings".format(key))
    identity = record.get("identity")
    if identity is not None and not (isinstance(identity, str) or (
            isinstance(identity, list) and all(isinstance(v, str) for v in identity))):
        raise ArchiveError("identity must be a string or a list of strings")
    rights = record.get("rights")
    if rights is not None and not (isinstance(rights, dict)
                                   and isinstance(rights.get("allowedUses", []), list)):
        raise ArchiveError("rights must be an object; its allowedUses a list")
    cost = record.get("cost")
    if cost is not None and not (isinstance(cost, dict) and cost.get("basis", "unknown") in COST_BASES):
        raise ArchiveError("cost must be an object with basis {}".format(", ".join(COST_BASES)))
    if "usedIn" in record and not (isinstance(record["usedIn"], list)
                                   and all(isinstance(v, dict) for v in record["usedIn"])):
        raise ArchiveError("usedIn must be a list of objects")
    return record


def kind_of(path):
    suffix = path.suffix.lower()
    for kind, suffixes in KINDS.items():
        if suffix in suffixes:
            return kind
    return "other"


def digest(path):
    hashed, size = hashlib.sha256(), 0
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            hashed.update(chunk)
            size += len(chunk)
    return hashed.hexdigest(), size


def same_file(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def clone(source, destination):
    """Copy, as a copy-on-write clone where the file system supports it (APFS, Btrfs,
    XFS): the copy then takes no extra space until one side changes."""
    flag = {"darwin": "-c"}.get(sys.platform, "--reflink=auto" if sys.platform.startswith("linux") else None)
    if flag and subprocess.run(["cp", flag, str(source), str(destination)], capture_output=True).returncode == 0:
        return
    shutil.copyfile(source, destination)


def signature(path):
    """What changes when a file is rewritten or replaced: size, modification time, inode."""
    info = os.stat(path)
    return (info.st_size, info.st_mtime_ns, info.st_ino, info.st_dev)


def intact(path, asset):
    """The original is in place: judged by size, or by hash when the record has no size."""
    if path.is_symlink() or not path.is_file():
        return False
    if isinstance(asset.get("bytes"), int):
        return path.stat().st_size == asset["bytes"]
    return digest(path)[0] == asset.get("sha256")


def case_variant(source, destination):
    """The same file under a name that differs only in case (a case-insensitive disk)."""
    return (not source.is_symlink() and source.name != destination.name
            and source.name.lower() == destination.name.lower()
            and source.parent.resolve() == destination.parent.resolve())


def check_case(project_dir, state, identifier, format_id):
    """Refuse an id or format that differs from an existing one only in case: most disks
    would put both in one file or folder, and a case-sensitive disk would not."""
    clash = next((other for other in state if other != identifier and other.lower() == identifier.lower()), None)
    if clash:
        raise ArchiveError("id {} differs only in case from {}; use another id".format(identifier, clash))
    folder = next((entry.name for entry in project_dir.iterdir() if entry.is_dir()
                   and entry.name != format_id and entry.name.lower() == format_id.lower()), None)
    if folder:
        raise ArchiveError("format {} differs only in case from the folder {}; use that spelling".format(
            format_id, folder))


def copy_in(source, project_dir, sha):
    """A verified copy of `source` in the project folder under a unique name, ready to be
    renamed into place. The source is untouched; a failed copy leaves nothing behind."""
    incoming = inside(project_dir, "{}{}{}".format(INCOMING, uuid.uuid4().hex, source.suffix.lower()))
    try:
        clone(source, incoming)
        if digest(incoming)[0] != sha:
            raise ArchiveError("The copy of {} did not match it; nothing was added".format(source))
    except BaseException:
        incoming.unlink(missing_ok=True)
        raise
    return incoming


def rename_checked(source, destination, before):
    """Move a file in by renaming it, then make sure it is still the file that was hashed;
    if it was being written meanwhile, put it back."""
    os.rename(source, destination)
    if signature(destination) != before:
        os.rename(destination, source)
        raise ArchiveError("{} changed while it was being added; add it once it is complete".format(source))


# ---------------------------------------------------------------------------
# Commands


def add(root, project, source, record=None, identifier=None, format_id=None, kind=None, move=False):
    """Archive one original. Content already archived is not stored twice: the existing
    asset comes back with duplicate=True and the source stays where it is, unless the
    archived original was missing or the wrong size, when this file restores it (moved in
    with `move` on the same disk, copied otherwise). With `move`, a new original is renamed
    into the archive when it is a plain file on the same disk, or copied and its path
    removed once catalogued."""
    source = Path(source).expanduser()
    if not source.is_file():
        raise ArchiveError("No file at {}".format(source))
    if source.name.startswith(INCOMING):
        raise ArchiveError("{} is an unfinished copy; add the original it was made from".format(source))
    record = dict(validate({} if record is None else record))
    identifier = identifier or record.pop("id", None)
    format_id = format_id or record.pop("format", None) or UNFILED
    kind = kind or record.pop("kind", None) or kind_of(source)
    check_id(format_id, "format")
    if kind not in (*KINDS, "other"):
        raise ArchiveError("kind must be one of: {}".format(", ".join((*KINDS, "other"))))
    before = signature(source)
    sha, size = digest(source)
    if signature(source) != before:
        raise ArchiveError("{} changed while it was being read; add it once it is complete".format(source))
    identifier = identifier or "{}-{}".format(kind, sha[:12])
    check_id(identifier, "id")
    project_dir = project_directory(root, project)
    relative = Path(format_id, kind, identifier + source.suffix.lower())
    destination = inside(project_dir, relative)
    in_place = same_file(source, destination)
    # Only a plain file on the same disk is renamed in. A symlink or a file with other
    # names is copied, so the archive never holds a link or shares a file with a path
    # outside it; with `move`, only that path is removed.
    plain = not source.is_symlink() and os.stat(source).st_nlink == 1
    rename = move and not in_place and plain and os.stat(source).st_dev == os.stat(project_dir).st_dev
    # Copy and verify before taking the lock, so no other writer waits on a large file.
    incoming = None if in_place or rename else copy_in(source, project_dir, sha)
    remove_source = False
    try:
        with locked(project_dir):
            state = assets(project_dir)
            match = next((asset for asset in state.values() if asset.get("sha256") == sha), None)
            if match is not None:
                return restore(project_dir, match, source, incoming, rename, before)
            if identifier in state:
                raise ArchiveError("id {} already names different content".format(identifier))
            check_case(project_dir, state, identifier, format_id)
            if destination.exists():
                if not in_place and digest(destination)[0] != sha:
                    raise ArchiveError("{} exists with different content; run verify".format(destination))
                if in_place and os.stat(destination).st_nlink > 1:
                    # Also reachable under another name: give the archive its own copy, so
                    # editing that path cannot change the original.
                    os.replace(copy_in(destination, project_dir, sha), destination)
                if in_place and case_variant(source, destination):
                    os.rename(source, destination)  # the recorded name resolves on any disk
                remove_source = move and not in_place  # the same content is already in place
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                if rename:
                    rename_checked(source, destination, before)
                else:
                    os.rename(incoming, destination)
                    incoming = None
                remove_source = move and not rename
            event = dict(record, event="add", id=identifier, sha256=sha, bytes=size, kind=kind, format=format_id,
                         path=relative.as_posix(), originalName=source.name, archivedAt=utc_now())
            event.setdefault("status", "candidate")
            append_line(catalog(project_dir), log_line(event))
        if remove_source:
            source.unlink()
        return dict(event, duplicate=False, file=str(destination))
    finally:
        if incoming is not None:
            incoming.unlink(missing_ok=True)


def restore(project_dir, asset, source, incoming, rename, before):
    """The answer for content already archived. If its original is missing or the wrong
    size, this file takes its place and the old one is set aside, never deleted."""
    original = inside(project_dir, asset["path"])
    answer = dict(asset, duplicate=True, file=str(original))
    if same_file(source, original) or intact(original, asset):
        return answer
    original.parent.mkdir(parents=True, exist_ok=True)
    # Stage and check the replacement first, so a refused restore leaves the old file alone.
    if rename:
        staged = original.with_name("{}{}{}".format(MOVING, uuid.uuid4().hex, original.suffix))
        rename_checked(source, staged, before)
    else:
        staged = incoming if incoming is not None else copy_in(source, project_dir, asset["sha256"])
    if original.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        os.rename(original, original.with_name("{}.changed-{}".format(original.name, stamp)))
    os.rename(staged, original)
    now = utc_now()
    event = {"event": "note", "id": asset["id"], "notedAt": now, "restoredAt": now}
    append_line(catalog(project_dir), log_line(event))
    return dict(apply_note(dict(asset), event), duplicate=True, restored=True, file=str(original))


def note(root, project, identifier, record):
    """Append a later fact about an asset: status and reason, tags, usage, rights."""
    record = dict(validate(record, note=True))
    if not record:
        raise ArchiveError("A note needs at least one field")
    project_dir = project_directory(root, project, create=False)
    with locked(project_dir):
        state = assets(project_dir)
        if identifier not in state:
            raise ArchiveError("No asset {} in project {}".format(identifier, project))
        event = dict(record, event="note", id=identifier, notedAt=utc_now())
        append_line(catalog(project_dir), log_line(event))
    return apply_note(state[identifier], event)


def projects_in(root):
    return sorted(path.name for path in root.iterdir() if (path / CATALOG).is_file()) if root.is_dir() else []


def find(root, projects, kind=None, format_id=None, status=None, tags=(), identity=None,
         allowed_use=None, text=None):
    found = []
    for project in projects:
        project_dir = inside(root, project)
        for asset in assets(project_dir).values():
            if ((kind and asset.get("kind") != kind)
                    or (format_id and asset.get("format") != format_id)
                    or (status and asset.get("status") != status)
                    or not set(tags) <= set(strings(asset.get("tags")))
                    or (identity and identity not in strings(asset.get("identity")))
                    or (allowed_use and allowed_use not in strings((asset.get("rights") or {}).get("allowedUses")))
                    or (text and text.lower() not in json.dumps(asset, ensure_ascii=False).lower())):
                continue
            found.append(dict(asset, project=project, file=str(project_dir / asset["path"])))
    return found


def show(root, project, identifier):
    project_dir = project_directory(root, project, create=False)
    state = assets(project_dir)
    if identifier not in state:
        raise ArchiveError("No asset {} in project {}".format(identifier, project))
    events = [event for event in read_log(catalog(project_dir)) if event.get("id") == identifier]
    return dict(state[identifier], project=project, file=str(project_dir / state[identifier]["path"]),
                events=events)


def checkout(root, project, identifier, target, usage=None):
    """A working copy for a batch (a clone where the disk allows it). The archive keeps
    the original; edit the copy."""
    project_dir = project_directory(root, project, create=False)
    asset = assets(project_dir).get(identifier)
    if asset is None:
        raise ArchiveError("No asset {} in project {}".format(identifier, project))
    original = inside(project_dir, asset["path"])
    if not original.is_file():
        raise ArchiveError("The original of {} is missing: {}".format(identifier, original))
    as_directory = str(target).endswith(("/", os.sep))
    target = Path(target).expanduser()
    folder = target if as_directory or target.is_dir() else None
    if folder is not None:
        target = folder / original.name
    resolved = Path(os.path.abspath(target)).resolve()
    if resolved == root or root in resolved.parents:
        raise ArchiveError("Check a copy out into a batch folder, not into the archive: {}".format(target))
    if folder is not None:
        folder.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if digest(target)[0] != asset["sha256"]:
            raise ArchiveError("{} already exists with different content".format(target))
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        clone(original, target)
    if usage:
        note(root, project, identifier, {"usedIn": [usage]})
    return target


def verify(root, project, rehash=False):
    """Missing or changed originals, files the catalog doesn't know, unfinished copies
    and catalog lines a crash cut off."""
    project_dir = project_directory(root, project, create=False)
    state = assets(project_dir)
    problems, known = [], set()
    for asset in state.values():
        path = project_dir / asset["path"]
        known.add(path)
        if not path.is_file():
            problems.append({"problem": "missing", "id": asset["id"], "file": str(path)})
        elif path.stat().st_size != asset.get("bytes") or (rehash and digest(path)[0] != asset.get("sha256")):
            problems.append({"problem": "changed", "id": asset["id"], "file": str(path)})
        elif path.stat().st_nlink > 1:
            problems.append({"problem": "shares its data with another path; editing that path changes the original",
                             "id": asset["id"], "file": str(path)})
    for path in sorted(project_dir.rglob("*")):
        if path.is_symlink():
            problems.append({"problem": "symlink inside the archive", "id": None, "file": str(path)})
            continue
        if not path.is_file() or path in known or path.name in (CATALOG, JOBS):
            continue
        if path.name.startswith(INCOMING):
            problems.append({"problem": "unfinished copy; the original was never moved, so this can be deleted",
                             "id": None, "file": str(path)})
        elif path.name.startswith(MOVING):
            problems.append({"problem": "an original moved in by an interrupted restore; add it again with --move "
                                        "to finish",
                             "id": None, "file": str(path)})
        elif path.name.startswith(CATALOG + ".cut-"):
            problems.append({"problem": "catalog line cut off by a crash", "id": None, "file": str(path)})
        elif not path.name.startswith("."):
            problems.append({"problem": "not in catalog", "id": None, "file": str(path)})
    return {"project": project, "assets": len(state), "rehashed": rehash, "problems": problems}


# ---------------------------------------------------------------------------
# Command line


def read_json(value):
    """A JSON file, or standard input for `-`."""
    try:
        if value == "-":
            return json.load(sys.stdin)
        return json.loads(Path(value).expanduser().read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ArchiveError("Cannot read JSON {}: {}".format(value, error)) from error


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    def command(name, help_text, all_projects=False):
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument("--root", help="Archive root (default: see above)")
        sub.add_argument("--project", help="Project ID (default: from project memory)")
        if all_projects:
            sub.add_argument("--all-projects", action="store_true", help="Every project under the root")
        return sub

    sub = command("add", "Archive one original as it arrived")
    sub.add_argument("--file", required=True)
    sub.add_argument("--format", help="The format it was made for (default: {})".format(UNFILED))
    sub.add_argument("--id", help="A stable ID (default: <kind>-<first 12 hex of its SHA-256>)")
    sub.add_argument("--kind", choices=(*KINDS, "other"))
    sub.add_argument("--record", help="JSON provenance (tool, model, requestId, prompt, inputs, cost, "
                     "rights, status, tags ...); - reads stdin")
    sub.add_argument("--move", action="store_true", help="Move the file in instead of copying it")

    sub = command("note", "Record a later fact about an asset")
    sub.add_argument("--id", required=True)
    sub.add_argument("--status", choices=STATUSES)
    sub.add_argument("--reason")
    sub.add_argument("--tag", action="append", default=[])
    sub.add_argument("--record", help="JSON fields to record; - reads stdin")

    sub = command("find", "Search the catalog", all_projects=True)
    sub.add_argument("--kind", choices=(*KINDS, "other"))
    sub.add_argument("--format")
    sub.add_argument("--status", choices=STATUSES)
    sub.add_argument("--tag", action="append", default=[])
    sub.add_argument("--identity")
    sub.add_argument("--allowed-use")
    sub.add_argument("--text", help="Case-insensitive text anywhere in the record, such as a prompt")
    sub.add_argument("--limit", type=int, default=50)
    sub.add_argument("--json", dest="as_json", action="store_true", help="One JSON object per line")

    sub = command("show", "One asset with all its events")
    sub.add_argument("--id", required=True)

    sub = command("checkout", "Copy an original into a batch for editing")
    sub.add_argument("--id", required=True)
    sub.add_argument("--to", required=True, help="A directory (existing, or ending in /) or a file path")
    for flag in ("batch", "item", "version"):
        sub.add_argument("--" + flag, help="Record this use of the asset")

    sub = command("verify", "Check originals against the catalog", all_projects=True)
    sub.add_argument("--rehash", action="store_true", help="Recompute every SHA-256, not just sizes")

    command("where", "Show the resolved root, project and catalog")

    arguments = parser.parse_args(argv)
    try:
        everything = getattr(arguments, "all_projects", False)
        if everything:
            root = resolve(arguments.root, arguments.project or "shared")[0]
            projects = projects_in(root)
        else:
            root, project = resolve(arguments.root, arguments.project)
            projects = [project]
        if arguments.command == "add":
            record = read_json(arguments.record) if arguments.record else {}
            if not isinstance(record, dict):
                raise ArchiveError("--record must be a JSON object")
            format_id = canonical_format(project, arguments.format or record.pop("format", None))
            result = add(root, project, arguments.file, record, arguments.id, format_id,
                         arguments.kind, arguments.move)
        elif arguments.command == "note":
            record = read_json(arguments.record) if arguments.record else {}
            if not isinstance(record, dict):
                raise ArchiveError("--record must be a JSON object")
            record.update({k: v for k, v in (("status", arguments.status), ("reason", arguments.reason)) if v})
            if arguments.tag:
                record["tags"] = arguments.tag
            result = note(root, project, arguments.id, record)
        elif arguments.command == "find":
            found = find(root, projects, arguments.kind, arguments.format, arguments.status, arguments.tag,
                         arguments.identity, arguments.allowed_use, arguments.text)
            for asset in found[:arguments.limit]:
                if arguments.as_json:
                    print(json.dumps(asset, ensure_ascii=False, sort_keys=True))
                else:
                    print("{project}/{id}  {kind}  {format}  {status}  {tags}  {file}".format(
                        tags=",".join(strings(asset.get("tags"))) or "-", **{k: asset.get(k) for k in (
                            "project", "id", "kind", "format", "status", "file")}))
            if len(found) > arguments.limit:
                print("archive: {} more; narrow the search or raise --limit".format(len(found) - arguments.limit),
                      file=sys.stderr)
            return 0
        elif arguments.command == "show":
            result = show(root, project, arguments.id)
        elif arguments.command == "checkout":
            usage = {k: v for k, v in (("batchId", arguments.batch), ("itemId", arguments.item),
                                       ("version", int(arguments.version) if (arguments.version or "").isdigit()
                                        else arguments.version)) if v is not None}
            result = {"file": str(checkout(root, project, arguments.id, arguments.to, usage or None))}
        elif arguments.command == "verify":
            reports = [verify(root, name, arguments.rehash) for name in projects]
            print(json.dumps(reports if everything else reports[0], indent=2, ensure_ascii=False))
            return 1 if any(report["problems"] for report in reports) else 0
        else:
            result = {"root": str(root), "project": project, "catalog": str(root / project / CATALOG)}
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    except (ArchiveError, project_memory.MemoryError, OSError, TypeError, KeyError) as error:
        print("archive: {}".format(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    # Agents read this through a pipe, which on Windows defaults to the system code page.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors=stream.errors)
    sys.exit(main())
