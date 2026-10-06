#!/usr/bin/env python3
"""Tie published posts back to the content that made them, and compare them fairly.

Commands:

  link         Record which batch item, version and format a published destination
               came from: one immutable line per post and account in a monthly log,
               history/publications/<YYYY-MM>.jsonl in the project's
               .viewprinter/content-memory (created by the first link).
  checkpoint   Record one posting event (saved, verified, amended ...) for a batch
               placement: one line in history/posting/<batch>.jsonl.
  checkpoints  Show the latest state of each placement in a batch, to resume safely.
  compact      Fold per-post publication files from older versions into the logs.
  report       Join the links to saved ViewPrinter posts_list responses, compare each
               destination with its own account's other posts of a similar age and
               mode, and summarize each format with a suggested decision.

Standard library only. Python 3.11+.
"""

import argparse
import contextlib
from datetime import datetime, timezone
import errno
import json
import os
from pathlib import Path
import re
import statistics
import sys
import time

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
    import msvcrt

MEMORY_DIRECTORY = Path(".viewprinter") / "content-memory"
MEMORY_ENVIRONMENT = "VIEWPRINTER_CONTENT_MEMORY"
SAFE_PART = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")

# Age buckets in hours. A post is only compared with posts in the same bucket,
# because lifetime counters keep growing and a young post always looks worse.
AGE_BUCKETS = (
    ("under-1d", 0, 24),
    ("1-3d", 24, 72),
    ("3-7d", 72, 168),
    ("7-30d", 168, 720),
    ("30d-plus", 720, None),
)

DEFAULT_RULES = {
    "minPeers": 5,             # other measured posts needed to form a baseline
    "minPublications": 3,      # measured publications of a format before any decision
    "minAgeHours": 72,         # younger results are reported but never decided on
    "doubleDownIndex": 1.5,    # median relative views at or above this ...
    "doubleDownShare": 0.66,   # ... with at least this share of posts above baseline
    "retireIndex": 0.5,        # median relative views at or below this ...
    "retireEngagementIndex": 0.8,  # ... and median relative engagement at or below this
    "retireMinPublications": 5,
}


class LearnError(Exception):
    pass


# ---------------------------------------------------------------------------
# Memory


def locate_memory(explicit=None, start=None, create=False):
    """The nearest .viewprinter/content-memory at or above `start`. With `create`,
    a project that has none gets one in `start` (the first link starts it)."""
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        path = path.resolve()
        if not path.is_dir():
            if not create:
                raise LearnError("No memory directory at {}".format(path))
            path.mkdir(parents=True)
        return path
    override = os.environ.get(MEMORY_ENVIRONMENT)
    if override:
        return locate_memory(override, create=create)
    directory = Path(start or Path.cwd()).resolve()
    for candidate in (directory, *directory.parents):
        memory = candidate / MEMORY_DIRECTORY
        if memory.is_dir():
            return memory
    if create:
        memory = directory / MEMORY_DIRECTORY
        memory.mkdir(parents=True)
        print("learn: started memory at {}".format(memory), file=sys.stderr)
        return memory
    raise LearnError("No .viewprinter/content-memory found above {}; link a post first".format(directory))


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Append-only logs
#
# A record is one line in a log, never a file of its own: an account that posts
# every day would otherwise leave thousands of tiny files in the project. Writers
# hold the folder's lock, so agents working in parallel append safely, and nothing
# already written is rewritten.

LOCK_WAIT_SECONDS = 600
# The errors a file system gives when it cannot lock a folder at all (some network disks).
NO_FOLDER_LOCKS = {getattr(errno, name) for name in ("ENOTSUP", "EOPNOTSUPP", "EBADF", "EINVAL", "ENOSYS", "ENOLCK")
                   if hasattr(errno, name)}
MERGE_RULE = ("# Written by ViewPrinter's learn.py. These logs only ever gain lines, so a git merge\n"
              "# keeps the lines from both sides; a conflicting record is still refused when read.\n"
              "*.jsonl merge=union\n")
LOCK_IGNORE = ("# Written by ViewPrinter's learn.py: the lock file it uses where a folder cannot be\n"
               "# locked itself (Windows, some network disks).\n"
               ".lock\n")


def write_once(path, text):
    """Create a small helper file unless it exists; an existing one is left alone."""
    if not path.exists():
        try:
            with path.open("x", encoding="utf-8") as stream:
                stream.write(text)
        except FileExistsError:
            pass


def lock_file(directory):
    """The .lock file inside a folder that cannot be locked itself, kept out of git."""
    write_once(directory / ".gitignore", LOCK_IGNORE)
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
    """Hold the folder's lock. On macOS and Linux the folder itself is locked, so no lock
    file appears; where a folder cannot be locked, a .lock file inside it is used."""
    directory.mkdir(parents=True, exist_ok=True)
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


def merge_rule(directory):
    """Have git merge the logs line by line instead of reporting a conflict, for
    projects that commit them."""
    write_once(directory / ".gitattributes", MERGE_RULE)


def log_line(record):
    return (json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


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
    """Append one line; call with the folder's lock held. A last line without its
    newline is kept when it is a whole record (an edit or a merge dropped the newline).
    Otherwise it is the remains of a write a crash interrupted, whose writer never
    reported success: it moves to a .cut file beside the log."""
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
                print("learn: moved an unfinished last line of {} to {}".format(path, side), file=sys.stderr)
        stream.write(line)
        stream.flush()
        os.fsync(stream.fileno())


def read_log(path):
    """The records in a log. A last line without its newline counts when it is a whole
    record and is skipped when it is not: a write still in progress, or a crash's."""
    data = path.read_bytes()
    cut = data.rfind(b"\n") + 1
    records = []
    for number, line in enumerate(data[:cut].split(b"\n"), 1):
        if not line.strip():
            continue
        record = parse_record(line)
        if record is None:
            raise LearnError("{} line {} is not a JSON object".format(path, number))
        records.append(record)
    if data[cut:].strip():
        record = parse_record(data[cut:])
        if record is None:
            print("learn: skipping an unfinished last line in {}".format(path), file=sys.stderr)
        else:
            records.append(record)
    return records


def comparable(record):
    return {key: value for key, value in record.items() if key != "createdAt"}


# ---------------------------------------------------------------------------
# Publications

PUBLICATIONS = Path("history") / "publications"
MONTH = re.compile(r"\d{4}-\d{2}")


def publication_id(post_id, account_id):
    for part in (post_id, account_id):
        if not isinstance(part, str) or not SAFE_PART.fullmatch(part):
            raise LearnError("post_id and account_id must be filename-safe ids")
    return "{}--{}".format(post_id, account_id)


def publication_records(memory):
    """(where, record) for every publication: the monthly logs, then any per-post
    files written before the logs existed."""
    directory = memory / PUBLICATIONS
    if not directory.is_dir():
        return []
    found = []
    for path in sorted(directory.glob("*.jsonl")):
        found.extend((path, record) for record in read_log(path))
    for path in sorted(directory.glob("*.json")):
        if not path.name.startswith("."):  # an interrupted link's temporary file
            found.append((path, json.loads(path.read_text(encoding="utf-8"))))
    return found


def month_log(directory, created_at):
    month = created_at[:7] if isinstance(created_at, str) and MONTH.match(created_at) else utc_now()[:7]
    return directory / (month + ".jsonl")


def link(memory, record):
    """Append one immutable publication record to its month's log. An identical retry
    is accepted; a different record for the same post and account is refused."""
    required = ("postId", "accountId", "batchId", "itemId", "version")
    missing = [key for key in required if record.get(key) in (None, "")]
    if missing:
        raise LearnError("Missing field(s): {}".format(", ".join(missing)))
    record = dict(record)
    record["id"] = publication_id(record["postId"], record["accountId"])
    if not record.get("createdAt"):  # absent, empty or null
        record["createdAt"] = utc_now()
    directory = memory / PUBLICATIONS
    with locked(directory):
        merge_rule(directory)
        for path, existing in publication_records(memory):
            if (existing.get("postId"), existing.get("accountId")) == (record["postId"], record["accountId"]):
                if comparable(existing) != comparable(record):
                    raise LearnError("A different publication record already exists in {}".format(path))
                return path
        path = month_log(directory, record["createdAt"])
        append_line(path, log_line(record))
        return path


def load_publications(memory):
    publications = {}
    for path, record in publication_records(memory):
        key = (record["postId"], record["accountId"])
        if key in publications and comparable(publications[key]) != comparable(record):
            raise LearnError("Conflicting publication records for post {} on account {}; see {}".format(
                key[0], key[1], path))
        publications.setdefault(key, record)
    return publications


def compact(memory, remove=False):
    """Fold per-post publication files into the monthly logs. With `remove`, delete each
    file once its identical record is in a log; a conflicting file is never removed."""
    directory = memory / PUBLICATIONS
    if not directory.is_dir():
        return {"files": 0, "added": 0, "removed": 0}
    added = removed = 0
    with locked(directory):
        merge_rule(directory)
        files = sorted(path for path in directory.glob("*.json") if not path.name.startswith("."))
        logged = {}
        for path in sorted(directory.glob("*.jsonl")):
            for record in read_log(path):
                logged[(record["postId"], record["accountId"])] = record
        for path in files:
            record = json.loads(path.read_text(encoding="utf-8"))
            key = (record["postId"], record["accountId"])
            if key not in logged:
                append_line(month_log(directory, record.get("createdAt")), log_line(record))
                logged[key] = record
                added += 1
            elif comparable(logged[key]) != comparable(record):
                raise LearnError("{} conflicts with the logged record for post {} on account {}".format(path, *key))
            if remove:
                path.unlink()
                removed += 1
    return {"files": len(files), "added": added, "removed": removed}


# ---------------------------------------------------------------------------
# Posting checkpoints

POSTING = Path("history") / "posting"
STATUSES = ("held", "saved", "verified", "amended", "canceled", "failed")


def creative(event):
    version = event.get("version")
    return (event.get("itemId"), None if version is None else str(version), event.get("accountId"))


def same_creative(group, event):
    """The same account, and the same item version, except that an event naming no item
    (an amend or cancel recorded by post id) or no version matches any."""
    item, version, account = creative(event)
    group_item, group_version, group_account = group["creative"]
    if account != group_account:
        return False
    if item is None or group_item is None:
        return True
    return item == group_item and (version is None or group_version is None or version == group_version)


def placements_of(groups, event):
    """The placements an event belongs to, joined by idempotency key or post id: one for
    an event that names its item, or every matching one for an event that doesn't, such
    as a cancel of a post that carried several items."""
    found = [group for group in groups if same_creative(group, event) and (
        (event.get("key") and event.get("key") == group["key"])
        or (event.get("postId") and event.get("postId") == group["postId"]))]
    return found if event.get("itemId") is None else found[:1]


def event_time(event):
    """Sort key: timed events in time order, then any without a time in file order."""
    stamp = event.get("createdAt")
    return (0, stamp) if isinstance(stamp, str) and stamp else (1, "")


def group_events(events):
    """Events grouped by placement, in the order they happened. A merged log can hold
    them out of order, so they are sorted by time first."""
    groups = []
    for event in sorted(events, key=event_time):
        matched = placements_of(groups, event)
        if not matched:
            matched = [{"creative": creative(event), "key": None, "postId": None, "events": []}]
            groups.append(matched[0])
        for group in matched:
            if group["creative"][0] is None and event.get("itemId") is not None:
                group["creative"] = creative(event)
            group["key"] = group["key"] or event.get("key")
            group["postId"] = group["postId"] or event.get("postId")
            group["events"].append(event)
    return groups


def checkpoint(memory, record):
    """Append one posting event to the batch's log, history/posting/<batch>.jsonl. A
    retry identical to its placement's latest event adds nothing. For a post that came
    from a campaign rather than a batch, the campaign id is the batch, and item and
    version may be left out."""
    required = ("batchId", "accountId", "status")
    missing = [key for key in required if record.get(key) in (None, "")]
    if missing:
        raise LearnError("Missing field(s): {}".format(", ".join(missing)))
    if record["status"] not in STATUSES:
        raise LearnError("status must be one of: {}".format(", ".join(STATUSES)))
    if record["status"] != "failed" and not record.get("postId"):
        raise LearnError("A {} checkpoint needs the post id posts_save returned".format(record["status"]))
    if not record.get("key") and not record.get("postId"):
        raise LearnError("A failed checkpoint needs the idempotency key that was sent, so a resume can match it")
    if not isinstance(record["batchId"], str) or not SAFE_PART.fullmatch(record["batchId"]):
        raise LearnError("batchId must be a filename-safe id")
    for field in ("accepted", "readback"):
        if field in record and not isinstance(record[field], dict):
            raise LearnError("{} must be a JSON object".format(field))
    record = dict(record)
    if not record.get("createdAt"):  # absent, empty or null
        record["createdAt"] = utc_now()
    directory = memory / POSTING
    path = directory / (record["batchId"] + ".jsonl")
    with locked(directory):
        merge_rule(directory)
        matched = placements_of(group_events(read_log(path)) if path.exists() else [], record)
        if matched and all(comparable(group["events"][-1]) == comparable(record) for group in matched):
            return path
        append_line(path, log_line(record))
    return path


def placements(memory, batch):
    """The latest state of each placement in a batch, for resuming or reconciling."""
    if not isinstance(batch, str) or not SAFE_PART.fullmatch(batch):
        raise LearnError("batch must be a filename-safe id")
    path = memory / POSTING / (batch + ".jsonl")
    return [{"itemId": g["creative"][0],
             "version": next((e["version"] for e in reversed(g["events"]) if e.get("version") is not None), None),
             "accountId": g["creative"][2], "key": g["key"], "postId": g["postId"],
             "status": g["events"][-1]["status"], "at": g["events"][-1].get("createdAt"),
             "events": len(g["events"])} for g in group_events(read_log(path) if path.exists() else [])]


# ---------------------------------------------------------------------------
# ViewPrinter posts_list responses


def parse_time(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def counter(metrics, name):
    value = (metrics or {}).get(name)
    if isinstance(value, dict):
        value = value.get("value")
    return value if isinstance(value, (int, float)) else None


def destinations(responses):
    """Flatten saved posts_list responses into one row per destination.

    The same destination can appear in several saved pages or sweeps; the newest
    observation wins and observations are never summed.
    """
    rows = {}
    for response in responses:
        posts = response.get("posts", []) if isinstance(response, dict) else response
        for entry in posts:
            post = entry.get("post", {})
            for target in entry.get("targets", []):
                account = target.get("account") or {}
                metrics = target.get("metrics")
                insights = target.get("insights") or {}
                row = {
                    "postId": post.get("id"),
                    "targetId": target.get("id"),
                    "accountId": target.get("socialAccountId") or account.get("id"),
                    "handle": account.get("handle"),
                    "platform": account.get("platform"),
                    "status": target.get("status"),
                    "publishedAt": target.get("publishedAt") or target.get("postedAt"),
                    "capturedAt": (metrics or {}).get("capturedAt"),
                    "mode": "trial" if target.get("trial") else "regular",
                    "views": counter(metrics, "views"),
                    "likes": counter(metrics, "likes"),
                    "comments": counter(metrics, "comments"),
                    "shares": counter(metrics, "shares"),
                    "saves": counter(metrics, "saves"),
                    "reach": insights.get("reach"),
                    "totalWatchMs": insights.get("totalWatchMs"),
                    "replays": insights.get("replays"),
                    "follows": insights.get("follows"),
                    "retentionAt3s": insights.get("retentionAt3s"),
                    "url": target.get("externalUrl"),
                }
                key = (row["postId"], row["accountId"])
                previous = rows.get(key)
                if previous is None or (row["capturedAt"] or "") >= (previous["capturedAt"] or ""):
                    rows[key] = row
    return rows


def eligible(row):
    return (row["status"] == "published" and row["capturedAt"] is not None
            and row["publishedAt"] is not None and row["views"] is not None)


def age_hours(row, as_of=None):
    observed = parse_time(row["capturedAt"])
    if as_of is not None and observed > as_of:
        observed = as_of
    return (observed - parse_time(row["publishedAt"])).total_seconds() / 3600


def age_bucket(hours):
    for name, low, high in AGE_BUCKETS:
        if hours >= low and (high is None or hours < high):
            return name
    return AGE_BUCKETS[0][0]


def engagement_rate(row):
    """Interactions per view, counting only the counters this platform reports."""
    parts = [row[name] for name in ("likes", "comments", "shares", "saves") if row[name] is not None]
    if not parts or not row["views"]:
        return None
    return sum(parts) / row["views"]


def watch_per_view(row):
    if row["totalWatchMs"] is None or not row["views"]:
        return None
    return row["totalWatchMs"] / row["views"] / 1000


def cohort_key(row, hours):
    return (row["platform"], row["accountId"], row["mode"], age_bucket(hours))


def median(values):
    values = [value for value in values if value is not None]
    return statistics.median(values) if values else None


def ratio(value, base):
    if value is None or base in (None, 0):
        return None
    return value / base


# ---------------------------------------------------------------------------
# Report


def format_aliases(memory):
    """Old format names, from the project's format records: alias -> current ID. A
    renamed format keeps its earlier publication links under its current name."""
    aliases = {}
    for path in sorted((memory / "formats").glob("*/v*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(record, dict) and isinstance(record.get("id"), str):
            for alias in record.get("aliases") or []:
                if isinstance(alias, str):
                    aliases[alias] = record["id"]
    return aliases


def build_report(memory, responses, as_of=None, rules=None, promoted=()):
    """`promoted` names posts known to have run as ads, linked or not: post IDs, or
    (post ID, account ID) pairs. They leave baselines as well as the comparison."""
    rules = {**DEFAULT_RULES, **(rules or {})}
    publications = load_publications(memory)
    rows = destinations(responses)
    promoted = {tuple(p) if isinstance(p, (list, tuple)) else p for p in promoted}

    def is_paid(key):
        return (key in promoted or key[0] in promoted
                or bool(publications.get(key, {}).get("paidSupport")))

    measured = {key: row for key, row in rows.items() if eligible(row)}
    cohorts = {}
    for key, row in measured.items():
        if not is_paid(key):
            cohorts.setdefault(cohort_key(row, age_hours(row, as_of)), []).append(key)

    linked, unmeasured, paid = [], [], []
    for key, publication in sorted(publications.items()):
        row = rows.get(key)
        entry = {"publication": publication, "row": row}
        if row is None or key not in measured:
            if row is None:
                entry["reason"] = "not in the saved posts"
            elif row["status"] == "published":
                entry["reason"] = "published, not measured yet"
            else:
                entry["reason"] = "status {}".format(row["status"])
            unmeasured.append(entry)
            continue
        if is_paid(key):
            paid.append(entry)
            continue
        hours = age_hours(row, as_of)
        peers = [measured[other] for other in cohorts[cohort_key(row, hours)] if other != key]
        entry.update({
            "ageHours": round(hours, 1),
            "bucket": age_bucket(hours),
            "peers": len(peers),
            "engagementRate": engagement_rate(row),
            "watchPerView": watch_per_view(row),
        })
        if len(peers) >= rules["minPeers"]:
            entry["baselineViews"] = median(p["views"] for p in peers)
            entry["viewsIndex"] = ratio(row["views"], entry["baselineViews"])
            entry["engagementIndex"] = ratio(entry["engagementRate"],
                                             median(engagement_rate(p) for p in peers))
            entry["watchIndex"] = ratio(entry["watchPerView"], median(watch_per_view(p) for p in peers))
        else:
            entry["viewsIndex"] = entry["engagementIndex"] = entry["watchIndex"] = None
        linked.append(entry)

    aliases = format_aliases(memory)
    formats = {}
    for entry in linked:
        publication = entry["publication"]
        name = publication.get("formatId")
        if name in aliases:  # show the current ID everywhere in the report, keeping the old one
            entry["publication"] = dict(publication, formatId=aliases[name], formerFormatId=name)
        name = aliases.get(name, name) or "batch:" + publication["batchId"]
        formats.setdefault(name, []).append(entry)

    summaries = []
    for name, entries in sorted(formats.items()):
        comparable = [e for e in entries if e["viewsIndex"] is not None]
        mature = [e for e in comparable if e["ageHours"] >= rules["minAgeHours"]]
        views = [e["viewsIndex"] for e in mature]
        engagement = [e["engagementIndex"] for e in mature if e["engagementIndex"] is not None]
        summary = {
            "format": name,
            "publications": len(entries),
            "comparable": len(comparable),
            "mature": len(mature),
            "medianViewsIndex": median(views),
            "medianEngagementIndex": median(engagement),
            "shareAboveBaseline": (sum(1 for v in views if v > 1) / len(views)) if views else None,
        }
        summary["suggestion"], summary["why"] = suggest(summary, rules)
        summaries.append(summary)

    return {
        "asOf": (as_of or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z"),
        "rules": rules,
        "counts": {
            "linkedPublications": len(publications),
            "measuredDestinationsInSaves": len(measured),
            "compared": len(linked),
            "unmeasured": len(unmeasured),
            "paidSupportExcluded": len(paid),
            "promotedLeftOutOfBaselines": sum(1 for key in measured if is_paid(key)),
        },
        "formats": summaries,
        "publications": linked,
        "unmeasured": unmeasured,
        "paidSupport": paid,
    }


def suggest(summary, rules):
    mature = summary["mature"]
    if mature < rules["minPublications"]:
        return ("keep testing", "{} mature comparable publication(s); {} needed at {}h or older".format(
            mature, rules["minPublications"], rules["minAgeHours"]))
    views, share = summary["medianViewsIndex"], summary["shareAboveBaseline"]
    engagement = summary["medianEngagementIndex"]
    if views >= rules["doubleDownIndex"] and share >= rules["doubleDownShare"]:
        why = "median {:.2f}x its accounts' baseline, {:.0%} above baseline".format(views, share)
        if engagement is not None and engagement < 1:
            why += "; engagement {:.2f}x, so it earns reach more than response".format(engagement)
        return ("double down", why)
    if (mature >= rules["retireMinPublications"] and views <= rules["retireIndex"]
            and engagement is not None and engagement <= rules["retireEngagementIndex"]):
        return ("retire", "median {:.2f}x views and {:.2f}x engagement versus baseline".format(views, engagement))
    if engagement is not None and engagement >= rules["doubleDownIndex"] and views < 1.2:
        return ("vary", "engagement {:.2f}x but views {:.2f}x: it holds the people it reaches and "
                        "doesn't earn reach; vary the hook, keep the body".format(engagement, views))
    return ("vary", "median {:.2f}x baseline with {:.0%} above it; mixed or middling".format(views, share or 0))


def fmt(value, style="x"):
    if value is None:
        return "–"
    if style == "x":
        return "{:.2f}x".format(value)
    if style == "%":
        return "{:.1%}".format(value)
    if style == "s":
        return "{:.1f}s".format(value)
    return "{:,}".format(value) if isinstance(value, int) else str(value)


def render_markdown(report):
    counts = report["counts"]
    lines = [
        "# Content learning report",
        "",
        "As of {}. Each post is compared only with the same account's other measured posts",
        "on the same platform, in the same age bucket and mode (trial or regular).",
        "Suggestions are inputs to a decision, not decisions.",
        "",
        "| Linked | Compared | Not yet measured | Paid support, excluded | Promoted posts kept out of baselines |",
        "|---:|---:|---:|---:|---:|",
        "| {linkedPublications} | {compared} | {unmeasured} | {paidSupportExcluded} | {promotedLeftOutOfBaselines} |".format(**counts),
        "",
        "## Formats",
        "",
        "| Format | Publications | Mature and comparable | Median views vs baseline | Median engagement vs baseline | Above baseline | Suggestion | Why |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    lines[2] = lines[2].format(report["asOf"])
    for s in report["formats"]:
        lines.append("| {} | {} | {} | {} | {} | {} | {} | {} |".format(
            s["format"], s["publications"], s["mature"], fmt(s["medianViewsIndex"]),
            fmt(s["medianEngagementIndex"]), fmt(s["shareAboveBaseline"], "%"),
            s["suggestion"], s["why"]))
    lines += ["", "## Publications", "",
              "| Format | Item | Platform | Account | Mode | Age | Views | vs baseline | Engagement | vs baseline | Watch per view | Peers |",
              "|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for e in sorted(report["publications"], key=lambda e: (e["publication"].get("formatId") or "", -(e["viewsIndex"] or 0))):
        p, r = e["publication"], e["row"]
        versus = "zero baseline" if e.get("baselineViews") == 0 else fmt(e["viewsIndex"])
        lines.append("| {} | {} v{} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            p.get("formatId") or "–", p["itemId"], p["version"], r["platform"], r["handle"] or r["accountId"],
            r["mode"], e["bucket"], fmt(r["views"], "n"), versus, fmt(e["engagementRate"], "%"),
            fmt(e["engagementIndex"]), fmt(e["watchPerView"], "s"), e["peers"]))
    if report["unmeasured"]:
        lines += ["", "## Not yet measured", ""]
        for e in report["unmeasured"]:
            lines.append("- {}: {}".format(describe(e), e["reason"]))
    if report["paidSupport"]:
        lines += ["", "## Paid support, excluded from organic comparison", ""]
        for e in report["paidSupport"]:
            lines.append("- {}".format(describe(e)))
    return "\n".join(lines) + "\n"


def describe(entry):
    p, r = entry["publication"], entry["row"]
    where = (r["platform"] + " " + (r["handle"] or r["accountId"])) if r else p["accountId"]
    return "{} v{} on {}".format(p["itemId"], p["version"], where)


# ---------------------------------------------------------------------------
# Command line


def read_json(path):
    """A JSON file, or standard input for `-`."""
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def numeric_version(record):
    if isinstance(record.get("version"), str) and record["version"].isdigit():
        record["version"] = int(record["version"])
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    link_parser = commands.add_parser("link", help="Record where one published destination came from")
    link_parser.add_argument("--memory", help="Content memory directory (default: discover)")
    link_parser.add_argument("--file", help="A JSON record instead of the flags below (- reads stdin)")
    for flag in ("post-id", "account-id", "batch", "item", "version", "format", "format-revision",
                 "platform", "published-at", "note"):
        link_parser.add_argument("--" + flag)
    link_parser.add_argument("--paid-support", action="store_true",
                             help="The post was promoted, so its views include paid impressions")

    checkpoint_parser = commands.add_parser("checkpoint", help="Record one posting event for a batch placement")
    checkpoint_parser.add_argument("--memory", help="Content memory directory (default: discover)")
    checkpoint_parser.add_argument("--file", help="A JSON record instead of the flags below (- reads stdin)")
    for flag in ("batch", "item", "version", "account-id", "platform", "post-id", "key", "note"):
        checkpoint_parser.add_argument("--" + flag)
    checkpoint_parser.add_argument("--status", choices=STATUSES)
    checkpoint_parser.add_argument("--details", help="JSON object added to the record, such as accepted "
                                   "settings or read-back fields (- reads stdin)")

    placements_parser = commands.add_parser("checkpoints", help="Latest state of each placement in a batch")
    placements_parser.add_argument("--memory", help="Content memory directory (default: discover)")
    placements_parser.add_argument("--batch", required=True)
    placements_parser.add_argument("--json", dest="as_json", action="store_true", help="One JSON object per line")

    compact_parser = commands.add_parser("compact", help="Fold per-post publication files into the monthly logs")
    compact_parser.add_argument("--memory", help="Content memory directory (default: discover)")
    compact_parser.add_argument("--remove-originals", action="store_true",
                                help="Delete each per-post file once its identical record is in a log")

    report_parser = commands.add_parser("report", help="Compare linked publications with their accounts' baselines")
    report_parser.add_argument("--memory", help="Content memory directory (default: discover)")
    report_parser.add_argument("--posts", required=True, action="append",
                               help="A saved posts_list response (repeat for more pages)")
    report_parser.add_argument("--as-of", help="ISO time to cap observation ages at")
    report_parser.add_argument("--rules", help="JSON file overriding the default decision rules")
    report_parser.add_argument("--promoted", help="JSON list of posts that ran as ads, linked or not: "
                               "post IDs or {postId, accountId} objects")
    report_parser.add_argument("--json", dest="json_out", help="Write the full report as JSON")
    report_parser.add_argument("--markdown", help="Write the report as Markdown (default: stdout)")

    arguments = parser.parse_args(argv)
    try:
        memory = locate_memory(arguments.memory, create=arguments.command in ("link", "checkpoint"))
        if arguments.command == "link":
            if arguments.file:
                record = read_json(arguments.file)
            else:
                record = {
                    "postId": arguments.post_id, "accountId": arguments.account_id,
                    "batchId": arguments.batch, "itemId": arguments.item, "version": arguments.version,
                    "formatId": arguments.format, "formatRevision": arguments.format_revision,
                    "platform": arguments.platform, "publishedAt": arguments.published_at,
                    "note": arguments.note, "paidSupport": arguments.paid_support or None,
                }
                record = {k: v for k, v in record.items() if v is not None}
            print(link(memory, numeric_version(record)))
            return 0
        if arguments.command == "checkpoint":
            record = read_json(arguments.file) if arguments.file else {}
            if arguments.details:
                details = read_json(arguments.details)
                if not isinstance(details, dict):
                    raise LearnError("--details must be a JSON object")
                record.update(details)
            flags = {
                "batchId": arguments.batch, "itemId": arguments.item, "version": arguments.version,
                "accountId": arguments.account_id, "platform": arguments.platform,
                "postId": arguments.post_id, "key": arguments.key, "status": arguments.status,
                "note": arguments.note,
            }
            record.update({k: v for k, v in flags.items() if v is not None})
            print(checkpoint(memory, numeric_version(record)))
            return 0
        if arguments.command == "checkpoints":
            for placement in placements(memory, arguments.batch):
                if arguments.as_json:
                    print(json.dumps(placement, sort_keys=True))
                else:
                    what = ("{itemId} v{version}" if placement["itemId"] else "post {postId}").format(**placement)
                    print("{} on {accountId}: {status} (post {postId}, key {key}, {events} event(s), "
                          "last {at})".format(what, **placement))
            return 0
        if arguments.command == "compact":
            print(json.dumps(compact(memory, arguments.remove_originals), sort_keys=True))
            return 0
        responses = [read_json(path) for path in arguments.posts]
        rules = read_json(arguments.rules) if arguments.rules else None
        as_of = parse_time(arguments.as_of) if arguments.as_of else None
        promoted = []
        for entry in read_json(arguments.promoted) if arguments.promoted else []:
            promoted.append((entry["postId"], entry["accountId"]) if isinstance(entry, dict) else entry)
        report = build_report(memory, responses, as_of, rules, promoted)
        if arguments.json_out:
            Path(arguments.json_out).write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
        text = render_markdown(report)
        if arguments.markdown:
            Path(arguments.markdown).write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        return 0
    except (LearnError, OSError, ValueError, KeyError) as error:
        print("learn: {}".format(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
