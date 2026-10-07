#!/usr/bin/env python3
"""Keep the media of finished reviews in ViewPrinter instead of on this disk.

A registered review keeps its own copy of every file it shows, in the project's
.viewprinter/content-memory/reviews/.media/<sha256>/<name>. Once the work using a file is
finished (scheduled, excluded, or in an archived format or batch) the file can live in
ViewPrinter instead:

    status   what the reviews keep here, what is finished, what ViewPrinter already keeps
    save     hand finished files ViewPrinter doesn't keep yet to the project's archive. The
             archive's upload flow (upload-list, media_upload, upload-steps, media_save,
             stored) then puts them in ViewPrinter as source material
    release  let go of the local copies a fresh media_list answer shows ViewPrinter keeps as
             source material, with the user's words. kept.json stays beside each, the hub
             streams the file from ViewPrinter, and the review labels it "Kept in ViewPrinter"
    restore  bring a file back from ViewPrinter, checked byte for byte

    review_media.py status  --project ROOT [--listed ANSWER]
    review_media.py save    --project ROOT [--dry-run]
    review_media.py release --project ROOT --listed ANSWER --approval "USER'S WORDS" [--dry-run]
    review_media.py restore --project ROOT (--sha SHA256 | --item ID --version N)

Work still in review keeps its local files. Space comes back only where nothing else shares
the bytes: a review's copy is usually a clone of a batch file, so releasing it frees space once
those batch files are cleaned up too. This script makes no ViewPrinter calls; restore downloads
from the link ViewPrinter gave.
"""
import argparse
import copy
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import sys
import urllib.error
import urllib.request
import uuid

from review_delivery import rows_for
from review_gallery import KEPT, SHA256, kept_in_viewprinter
from review_readiness import item_state
import review_workspace as ws

FINISHED = {"scheduled", "excluded", "archived"}
# What a file is to the item that shows it, by where it appears.
ROLES = (("final", "cover"), ("previous", "previous-cover"), ("input", "input-cover"))
ORDER = {"final": 0, "cover": 1, "previous": 2, "previous-cover": 3, "input": 4, "input-cover": 5}
MIME = {".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif",
        ".avif": "image/avif", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".aac": "audio/aac", ".wav": "audio/wav",
        ".ogg": "audio/ogg", ".flac": "audio/flac"}


class MediaError(ValueError):
    pass


def now():
    return ws.now().replace("+00:00", "Z")


def store_of(project):
    return Path(project) / ".viewprinter/content-memory/reviews/.media"


def project_root(value):
    project = Path(value).expanduser().resolve()
    if not (project / ".viewprinter/content-memory").is_dir():
        raise MediaError("Not a ViewPrinter project (no .viewprinter/content-memory): {}".format(project))
    return project


def private_size(path):
    """The bytes only this file holds (APFS), which deleting it would free; None where unknown."""
    if sys.platform != "darwin":
        return None
    try:
        libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
    except OSError:
        return None

    class AttrList(ctypes.Structure):
        _fields_ = [("bitmapcount", ctypes.c_ushort), ("reserved", ctypes.c_uint16), ("commonattr", ctypes.c_uint32),
                    ("volattr", ctypes.c_uint32), ("dirattr", ctypes.c_uint32), ("fileattr", ctypes.c_uint32),
                    ("forkattr", ctypes.c_uint32)]
    # ATTR_CMNEXT_PRIVATESIZE, asked with FSOPT_ATTR_CMN_EXTENDED | FSOPT_NOFOLLOW.
    request, answer = AttrList(5, 0, 0, 0, 0, 0, 0x8), ctypes.create_string_buffer(64)
    if libc.getattrlist(os.fsencode(str(path)), ctypes.byref(request), answer, 64, 0x20 | 0x1) != 0:
        return None
    return struct.unpack_from("<q", answer.raw, 4)[0]


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def files(project):
    """Every file the reviews keep or let go: one entry per sha256 folder and file name."""
    store, found = store_of(project), []
    if not store.is_dir():
        return found
    for folder in sorted(store.iterdir()):
        if not folder.is_dir() or not SHA256.fullmatch(folder.name):
            continue
        names = {f.name for f in folder.iterdir() if f.is_file() and not f.name.startswith(".") and f.name != KEPT}
        kept = kept_in_viewprinter(folder / str((ws.read(folder / KEPT) or {}).get("name") or "-"))
        for name in sorted(names):
            path = folder / name
            found.append({"sha": folder.name, "name": name, "path": path, "bytes": path.stat().st_size, "kept": None})
        if kept and kept["name"] not in names:
            found.append({"sha": folder.name, "name": kept["name"], "path": folder / kept["name"],
                          "bytes": kept.get("bytes") or 0, "kept": kept})
    return found


def uses(project):
    """Who shows each kept file: by sha256, every review item using it, its role there and
    whether that work is finished. Archived formats and batches are finished."""
    project, found = Path(project).resolve(), {}
    for record in ws.records():
        if (record.get("kind") not in ws.CONTENT_KINDS or record.get("lifecycle") not in ("active", "archived")
                or record.get("batchId") or Path(record.get("projectRoot", "/")).resolve() != project):
            continue
        manifest = ws.read(record.get("manifest"))
        if not isinstance(manifest, dict):
            continue
        rows = (ws.read(Path(record["manifest"]).with_name("delivery.json")) or {}).get("placements", [])
        archived = {b["id"] for b in manifest.get("batches", []) if b.get("lifecycle") == "archived"}
        for item in manifest.get("items", []):
            if record["lifecycle"] == "archived" or item.get("batch") in archived:
                state = "archived"
            else:
                state = item_state(item, rows_for(item, rows))["state"]
            places = [(ROLES[0], item, None), (ROLES[1], item.get("previous"), None),
                      *[(ROLES[2], source, source.get("label")) for source in item.get("inputs") or []]]
            for roles, media, label in places:
                if not isinstance(media, dict):
                    continue
                for role, key in zip(roles, ("src", "poster")):
                    path = media.get(key)
                    if not isinstance(path, str) or "/.media/" not in path:
                        continue
                    found.setdefault(Path(path).parent.name, []).append({
                        "entry": record["id"], "format": record.get("formatId") or record.get("influencerId"),
                        "batch": item.get("batch"), "item": item.get("id"), "version": item.get("version"),
                        "title": item.get("title"), "role": role, "label": label, "state": state,
                        "finished": state in FINISHED, "generation": item.get("generation") or []})
    return found


def group(entry, usage):
    used = usage.get(entry["sha"])
    if not used:
        return "notInAnyReview"
    return "finishedWork" if all(u["finished"] for u in used) else "activeWork"


def unwrap(answer):
    """A tool answer as an agent may have saved it: plain JSON, or the MCP text wrapper."""
    if (isinstance(answer, list) and answer and all(isinstance(a, dict) and a.get("type") == "text" for a in answer)):
        return [json.loads(a["text"]) for a in answer]
    return answer


def source_rows(answer):
    """The files a media_list answer shows ViewPrinter keeps as source material, by sha256.
    A library file can be deleted, so it never counts."""
    rows = {}

    def take(value):
        if isinstance(value, list):
            for entry in value:
                take(entry)
        elif isinstance(value, dict):
            if isinstance(value.get("id"), str) and isinstance(value.get("sha256"), str):
                if value.get("purpose") == "source":
                    rows[value["sha256"].lower()] = value
            else:
                for key in ("media", "saved", "items"):
                    take(value.get(key))
    take(unwrap(answer))
    return rows


def read_answer(value):
    text = sys.stdin.read() if value == "-" else Path(value).expanduser().read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except ValueError as error:
        raise MediaError("Not a JSON answer: {}".format(error))


def archive_module():
    """The content-production skill's archive, which this plugin ships beside this skill."""
    folder = Path(__file__).resolve().parents[2] / "content-production" / "scripts"
    if "archive" in sys.modules:
        return sys.modules["archive"]
    if not (folder / "archive.py").is_file():
        raise MediaError("The content-production skill's archive.py is not installed beside this skill")
    sys.path.insert(0, str(folder))
    spec = importlib.util.spec_from_file_location("archive", folder / "archive.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["archive"] = module
    spec.loader.exec_module(module)
    return module


def archived_media(archive, root):
    """Every original any archive project holds, by sha256, with where ViewPrinter keeps it."""
    found = {}
    for project in archive.projects_in(root):
        for asset in archive.assets(root / project).values():
            if isinstance(asset.get("sha256"), str):
                found[asset["sha256"]] = dict(asset, project=project)
    return found


def tally(entries):
    total = sum(e["bytes"] for e in entries)
    return {"files": len(entries), "bytes": total, "gb": round(total / 1e9, 2)}


def status(project, answer=None):
    project = project_root(project)
    usage, everything = uses(project), files(project)
    if answer is not None:
        keeps, basis = set(source_rows(answer)), "listing"
    else:
        try:
            archive = archive_module()
            root, _ = archive.resolve(start=project)
            keeps = {sha for sha, a in archived_media(archive, root).items()
                     if (a.get("viewprinterMedia") or {}).get("purpose") == "source"}
            basis = "archive catalog"
        except (ValueError, OSError) as error:
            keeps, basis = set(), "unknown ({})".format(error)
    local = [e for e in everything if not e["kept"]]
    groups = {name: [e for e in local if group(e, usage) == name] for name in ("finishedWork", "activeWork", "notInAnyReview")}
    finished = groups["finishedWork"]
    releasable = [e for e in finished if e["sha"] in keeps]
    frees = [private_size(e["path"]) for e in releasable]
    result = {"project": str(project), "store": str(store_of(project)), "viewprinterKeeps": basis,
              "local": tally(local),
              "finishedWork": dict(tally(finished),
                                   keptInViewPrinter=tally(releasable),
                                   notInViewPrinterYet=tally([e for e in finished if e["sha"] not in keeps])),
              "activeWork": tally(groups["activeWork"]),
              "notInAnyReview": tally(groups["notInAnyReview"]),
              "released": tally([e for e in everything if e["kept"]]),
              "releaseNow": dict(tally(releasable),
                                 freesNowBytes=None if None in frees else sum(frees),
                                 freesAfterBatchCleanupBytes=sum(e["bytes"] for e in releasable))}
    return result


def generation_of(entry):
    """An archive cost from a review's cost."""
    cost = entry.get("cost") if isinstance(entry.get("cost"), dict) else {}
    basis = {"reported": "reported", "estimated": "estimate"}.get(cost.get("status"), "unknown")
    archived = {"basis": basis}
    if basis != "unknown" and isinstance(cost.get("amount"), (int, float)) and not isinstance(cost.get("amount"), bool):
        archived.update(amount=cost["amount"], unit=str(cost.get("unit", "")).lower())
    return archived


def provenance(used):
    """What the archive should know about a review file: the review, the item, its role there
    and, for an input that names one of the item's generated assets, how it was made."""
    used = sorted(used, key=lambda u: (ORDER.get(u["role"], 9), str(u["entry"])))
    first, roles = used[0], sorted({u["role"] for u in used}, key=lambda r: ORDER.get(r, 9))
    record = {"title": first.get("title") or first["item"], "batchId": first.get("batch"),
              "itemId": "{}/v{}".format(first["item"], first["version"]),
              "status": "selected" if any(u["role"] in ("final", "cover") and u["state"] == "scheduled" for u in used)
              else "candidate",
              "tags": ["review-media", *("review-" + role for role in roles)],
              "usedIn": [{k: v for k, v in (("review", u["entry"]), ("format", u["format"]), ("batch", u["batch"]),
                                            ("item", u["item"]), ("version", u["version"]), ("role", u["role"]),
                                            ("label", u["label"])) if v not in (None, "")} for u in used][:20]}
    if all(role in ("final", "cover", "previous", "previous-cover") for role in roles):
        record["origin"] = "edited"
    if first["role"] in ("input", "input-cover") and first.get("label"):
        made = next((g for g in first["generation"] if isinstance(g, dict)
                     and str(g.get("asset", "")).casefold() == str(first["label"]).casefold()), None)
        if made:
            record.update({k: v for k, v in (("tool", made.get("platform")), ("model", made.get("model")),
                                              ("prompt", made.get("prompt")), ("requestId", made.get("jobId")))
                           if isinstance(v, str) and v.strip()})
            record["cost"] = generation_of(made)
    elif first["role"] == "final" and first["generation"]:
        # How its parts were made, for the record; the archive's own fields describe this file.
        record["generation"] = [{k: g[k] for k in ("asset", "platform", "model", "jobId") if isinstance(g.get(k), str)}
                                for g in first["generation"] if isinstance(g, dict)][:10]
    return {k: v for k, v in record.items() if v not in (None, "", [])}


def save(project, dry_run=False):
    project = project_root(project)
    archive = archive_module()
    root, archive_project = archive.resolve(start=project)
    known = archived_media(archive, root)
    usage = uses(project)
    plan, counts, formats = [], {"alreadyArchived": 0, "activeWork": 0, "notInAnyReview": 0, "notMedia": 0}, {}
    seen = set()
    for entry in files(project):
        if entry["kept"] or entry["sha"] in seen:
            continue
        where = group(entry, usage)
        if where != "finishedWork":
            counts[where] += 1
            continue
        if entry["sha"] in known:  # adding it again would bring back an original let go
            counts["alreadyArchived"] += 1
            continue
        kind = archive.kind_of(entry["path"])
        if kind not in ("video", "image", "audio"):
            counts["notMedia"] += 1
            continue
        seen.add(entry["sha"])
        plan.append((entry, kind, provenance(usage[entry["sha"]])))
    added, errors = [], []
    if not dry_run:
        for entry, kind, record in plan:
            fmt = record_format(archive, archive_project, usage[entry["sha"]], formats, project)
            try:
                result = archive.add(root, archive_project, entry["path"], record, format_id=fmt, kind=kind)
                added.append({"id": result["id"], "sha256": entry["sha"], "format": result["format"]})
            except (ValueError, OSError) as error:
                errors.append("{}: {}".format(entry["path"], error))
    total = sum(e["bytes"] for e, _, _ in plan)
    result = {"project": str(project), "archive": str(root), "archiveProject": archive_project,
              ("wouldAdd" if dry_run else "added"): len(plan) if dry_run else len(added),
              "bytes": total, "gb": round(total / 1e9, 2),
              "byKind": {k: sum(1 for _, kind, _ in plan if kind == k) for k in ("video", "image", "audio")},
              "skipped": counts, "errors": errors[:20]}
    if not dry_run and added:
        result["next"] = ("Upload them through the archive's flow: archive.py upload-list --project {} --tag review-media, "
                          "then media_upload, upload-steps, media_save and stored".format(archive_project))
    return result


def record_format(archive, archive_project, used, cache, project):
    """The archive format for a review file: the review's format ID, folded to the project's
    current one, or unfiled when it isn't a usable ID."""
    first = sorted(used, key=lambda u: ORDER.get(u["role"], 9))[0]
    value = first.get("format") or archive.UNFILED
    if value not in cache:
        try:
            archive.check_id(value, "format")
            cache[value] = archive.canonical_format(archive_project, value, project)
        except ValueError:
            cache[value] = archive.UNFILED
    return cache[value]


def republish(project, shas):
    """Rebuild the active reviews showing these files, so their labels match the store. Call
    under the workspace lock."""
    import review_formats as formats
    updated = []
    for record in ws.records():
        if (record.get("lifecycle") != "active" or record.get("batchId") or not record.get("sources")
                or Path(record.get("projectRoot", "/")).resolve() != Path(project).resolve()):
            continue
        manifest = ws.read(record.get("manifest")) or {}
        shown = {Path(m[k]).parent.name for i in manifest.get("items", []) for m in (i, i.get("previous"), *(i.get("inputs") or []))
                 if isinstance(m, dict) for k in ("src", "poster") if isinstance(m.get(k), str)}
        if not shown & shas:
            continue
        candidate = copy.deepcopy(record)
        candidate["revision"] += 1
        candidate = formats.publish(candidate)
        ws.atomic(ws.registry() / (candidate["id"] + ".json"), candidate)
        formats.shortcut(candidate)
        updated.append(candidate["id"])
    return updated


def release(project, answer, approval=None, dry_run=False):
    if not dry_run and not (isinstance(approval, str) and approval.strip()):
        raise MediaError("release removes local files: pass --approval with the user's words agreeing to it")
    project = project_root(project)
    rows = source_rows(answer)
    if not rows:
        raise MediaError("Pass a fresh media_list answer (purpose: source) as --listed, so ViewPrinter says what it keeps")
    usage, chosen, skipped = uses(project), [], {}

    def skip(reason):
        skipped[reason] = skipped.get(reason, 0) + 1

    for entry in files(project):
        if entry["kept"]:
            continue
        where = group(entry, usage)
        row = rows.get(entry["sha"])
        if where != "finishedWork":
            skip({"activeWork": "work still in review", "notInAnyReview": "not in a current review"}[where])
        elif row is None:
            skip("ViewPrinter doesn't keep it as source material")
        elif not kept_link(row.get("url")):
            skip("the listing has no link to it")
        else:
            chosen.append((entry, row))
    frees = [private_size(entry["path"]) for entry, _ in chosen]
    released, shas = [], set()
    if not dry_run:
        with ws.lock():
            for entry, row in chosen:
                path = entry["path"]
                if not path.is_file() or file_hash(path) != entry["sha"]:
                    skip("changed since it was kept")
                    continue
                note = {"mediaId": row["id"], "url": row["url"], "name": entry["name"], "bytes": entry["bytes"],
                        "mimeType": row.get("mimeType") or MIME.get(path.suffix.lower()), "purpose": "source",
                        "releasedAt": now(), "approval": approval.strip()}
                ws.atomic(path.parent / KEPT, note)
                path.unlink()
                released.append(entry)
                shas.add(entry["sha"])
            updated = republish(project, shas) if shas else []
    total = sum(e["bytes"] for e in (released if not dry_run else [e for e, _ in chosen]))
    result = {"project": str(project), ("wouldRelease" if dry_run else "released"): len(chosen) if dry_run else len(released),
              "bytes": total, "gb": round(total / 1e9, 2),
              "freesNowBytes": None if None in frees else sum(frees), "skipped": skipped}
    if not dry_run:
        result["reviewsUpdated"] = updated
    return result


def kept_link(value):
    """ViewPrinter's link to a file: a plain web address."""
    return isinstance(value, str) and len(value) <= 2000 and bool(re.match(r"https?://[^\s/]+/\S*\Z", value))


def download(url, destination, sha, size):
    """Fetch url to destination, checking its size and sha256; nothing is left on failure."""
    temp = destination.with_name("." + uuid.uuid4().hex + destination.suffix)
    digest, got = hashlib.sha256(), 0
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "viewprinter-review-media"})
        with urllib.request.urlopen(request, timeout=60) as response, open(temp, "wb") as out:
            for block in iter(lambda: response.read(1 << 20), b""):
                digest.update(block)
                out.write(block)
                got += len(block)
            out.flush()
            os.fsync(out.fileno())
        if digest.hexdigest() != sha or (size and got != size):
            raise MediaError("The download from ViewPrinter didn't match the kept file; nothing was changed")
        os.link(temp, destination)  # never replaces a file that appeared meanwhile
    finally:
        if temp.exists():
            temp.unlink()


def restore(project, sha=None, item=None, version=None):
    project = project_root(project)
    store = store_of(project)
    if sha:
        targets = [sha.lower()]
    else:
        targets = sorted({s for s, used in uses(project).items()
                          for u in used if u["item"] == item and str(u["version"]) == str(version)})
        if not targets:
            raise MediaError("No review shows item {} version {}".format(item, version))
    restored, skipped, updated = [], {}, []
    with ws.lock():
        try:
            for target in targets:
                folder = store / target
                note = ws.read(folder / KEPT)
                kept = kept_in_viewprinter(folder / str((note or {}).get("name") or "-"))
                if not kept:
                    skipped["not let go"] = skipped.get("not let go", 0) + 1
                    continue
                destination = folder / kept["name"]
                if not destination.exists():
                    try:
                        download(kept["url"], destination, target, kept.get("bytes"))
                    except (urllib.error.URLError, OSError) as error:
                        raise MediaError("Could not download {} from ViewPrinter: {}".format(kept["name"], error))
                (folder / KEPT).unlink()
                restored.append({"sha256": target, "file": str(destination)})
        finally:
            if restored:  # whatever came back shows as local again, even if a later file failed
                updated = republish(project, {r["sha256"] for r in restored})
    return {"project": str(project), "restored": restored, "skipped": skipped, "reviewsUpdated": updated}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "save", "release", "restore"):
        command = commands.add_parser(name)
        command.add_argument("--project", required=True, help="The ViewPrinter project's root folder")
        if name in ("status", "release"):
            command.add_argument("--listed", required=name == "release",
                                 help="A fresh media_list answer (purpose: source); - reads stdin")
        if name in ("save", "release"):
            command.add_argument("--dry-run", action="store_true")
        if name == "release":
            command.add_argument("--approval", help="The user's words agreeing to let the local copies go")
        if name == "restore":
            command.add_argument("--sha")
            command.add_argument("--item")
            command.add_argument("--version")
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            result = status(args.project, read_answer(args.listed) if args.listed else None)
        elif args.command == "save":
            result = save(args.project, args.dry_run)
        elif args.command == "release":
            result = release(args.project, read_answer(args.listed), args.approval, args.dry_run)
        else:
            if not args.sha and not (args.item and args.version):
                parser.error("restore takes --sha, or --item and --version")
            result = restore(args.project, args.sha, args.item, args.version)
    except (MediaError, ValueError, OSError) as error:
        print("review_media: {}".format(error), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    # Agents read this through a pipe, which on Windows defaults to the system code page.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors=stream.errors)
    sys.exit(main())
