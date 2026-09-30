#!/usr/bin/env python3
"""Tie published posts back to the content that made them, and compare them fairly.

Two commands:

  link    Record which batch item, version and format a published destination came
          from. One immutable JSON event per post and account, written under the
          project's .viewprinter/content-memory/history/publications/ (created by
          the first link).
  report  Join those links to saved ViewPrinter posts_list responses, compare each
          destination with its own account's other posts of a similar age and mode,
          and summarize each format with a suggested decision.

Standard library only. Python 3.11+.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import statistics
import sys
import tempfile

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


def canonical_json(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def publication_id(post_id, account_id):
    for part in (post_id, account_id):
        if not isinstance(part, str) or not SAFE_PART.fullmatch(part):
            raise LearnError("post_id and account_id must be filename-safe ids")
    return "{}--{}".format(post_id, account_id)


def link(memory, record):
    """Write one immutable publication event. An identical retry is accepted."""
    required = ("postId", "accountId", "batchId", "itemId", "version")
    missing = [key for key in required if record.get(key) in (None, "")]
    if missing:
        raise LearnError("Missing field(s): {}".format(", ".join(missing)))
    record = dict(record)
    record["id"] = publication_id(record["postId"], record["accountId"])
    record.setdefault("createdAt", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    directory = memory / "history" / "publications"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / (record["id"] + ".json")
    if destination.exists():
        existing = json.loads(destination.read_text(encoding="utf-8"))
        comparable = {k: v for k, v in record.items() if k != "createdAt"}
        if {k: v for k, v in existing.items() if k != "createdAt"} != comparable:
            raise LearnError("A different publication record already exists: {}".format(destination))
        return destination
    descriptor, temporary = tempfile.mkstemp(prefix=".pending-", suffix=".json", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(canonical_json(record))
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            return link(memory, record)
        return destination
    finally:
        os.unlink(temporary)


def load_publications(memory):
    directory = memory / "history" / "publications"
    if not directory.is_dir():
        return {}
    publications = {}
    for path in sorted(directory.glob("*.json")):
        if path.name.startswith("."):  # an interrupted link's temporary file
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        publications[(record["postId"], record["accountId"])] = record
    return publications


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

    formats = {}
    for entry in linked:
        publication = entry["publication"]
        name = publication.get("formatId") or "batch:" + publication["batchId"]
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
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    link_parser = commands.add_parser("link", help="Record where one published destination came from")
    link_parser.add_argument("--memory", help="Content memory directory (default: discover)")
    link_parser.add_argument("--file", help="A JSON record instead of the flags below")
    for flag in ("post-id", "account-id", "batch", "item", "version", "format", "format-revision",
                 "platform", "published-at", "note"):
        link_parser.add_argument("--" + flag)
    link_parser.add_argument("--paid-support", action="store_true",
                             help="The post was promoted, so its views include paid impressions")

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
        memory = locate_memory(arguments.memory, create=arguments.command == "link")
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
                if isinstance(record.get("version"), str) and record["version"].isdigit():
                    record["version"] = int(record["version"])
            print(link(memory, record))
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
