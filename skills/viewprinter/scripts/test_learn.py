#!/usr/bin/env python3
"""Run with: python3 -m unittest discover -s scripts -p 'test_learn.py'."""

import contextlib
import errno
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import learn


def target(post_id, account, views, published, captured, platform="instagram", handle=None,
           trial=None, status="published", likes=10, comments=1, shares=2, saves=3, watch_ms=None):
    metrics = None
    if captured is not None:
        metrics = {"capturedAt": captured, "views": {"value": views, "change": 0},
                   "likes": {"value": likes}, "comments": {"value": comments},
                   "shares": {"value": shares}, "saves": {"value": saves}}
    return {"post": {"id": post_id}, "targets": [{
        "id": "t-" + post_id, "socialAccountId": account, "status": status,
        "publishedAt": published, "trial": trial, "metrics": metrics,
        "insights": {"totalWatchMs": watch_ms} if watch_ms is not None else {},
        "account": {"id": account, "platform": platform, "handle": handle or account}}]}


class LearnTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name).resolve()
        self.memory = self.project / ".viewprinter" / "content-memory"
        self.memory.mkdir(parents=True)
        (self.memory / "config.json").write_text("{}", encoding="utf-8")
        self.environment = patch.dict(os.environ)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        os.environ.pop(learn.MEMORY_ENVIRONMENT, None)

    def record(self, post_id, account="acct", item="clip-001", version=1, fmt="format-a", **extra):
        return {"postId": post_id, "accountId": account, "batchId": "batch-1",
                "itemId": item, "version": version, "formatId": fmt, **extra}

    def peers(self, account, count, views, published="2026-09-01T12:00:00Z",
              captured="2026-09-08T12:00:00Z", prefix="peer", **options):
        return [target("{}-{}-{}".format(prefix, account, i), account, views, published, captured, **options)
                for i in range(count)]

    def legacy(self, record):
        """A per-post file, as versions before the monthly logs wrote each link."""
        directory = self.memory / "history" / "publications"
        directory.mkdir(parents=True, exist_ok=True)
        record = dict(record, id="{}--{}".format(record["postId"], record["accountId"]))
        record.setdefault("createdAt", "2026-09-15T10:00:00Z")
        path = directory / (record["id"] + ".json")
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    # -- link ---------------------------------------------------------------

    def test_link_appends_one_line_per_destination_and_accepts_identical_retry(self):
        first = learn.link(self.memory, self.record("p1", createdAt="2026-09-30T23:00:00Z"))
        again = learn.link(self.memory, self.record("p1"))
        self.assertEqual(first, again)
        self.assertEqual(first.name, "2026-09.jsonl")
        learn.link(self.memory, self.record("p2", createdAt="2026-10-01T00:00:00Z"))
        directory = self.memory / "history" / "publications"
        self.assertEqual(sorted(p.name for p in directory.glob("*.jsonl")), ["2026-09.jsonl", "2026-10.jsonl"])
        self.assertEqual(len(learn.read_log(first)), 1)
        with self.assertRaises(learn.LearnError):
            learn.link(self.memory, self.record("p1", version=2))

    def test_per_post_files_from_older_versions_are_still_read_and_respected(self):
        self.legacy(self.record("old"))
        self.assertEqual(learn.link(self.memory, self.record("old")).name, "old--acct.json")
        with self.assertRaises(learn.LearnError):
            learn.link(self.memory, self.record("old", version=3))
        learn.link(self.memory, self.record("new"))
        self.assertEqual(sorted(learn.load_publications(self.memory)), [("new", "acct"), ("old", "acct")])

    def test_compact_folds_per_post_files_into_logs_and_removes_them_only_when_asked(self):
        for name in ("a", "b"):
            self.legacy(self.record(name))
        learn.link(self.memory, self.record("c"))
        before = learn.load_publications(self.memory)
        self.assertEqual(learn.compact(self.memory), {"files": 2, "added": 2, "removed": 0})
        self.assertEqual(learn.compact(self.memory), {"files": 2, "added": 0, "removed": 0})
        self.assertEqual(learn.compact(self.memory, remove=True), {"files": 2, "added": 0, "removed": 2})
        self.assertEqual(list((self.memory / "history" / "publications").glob("*.json")), [])
        self.assertEqual(learn.load_publications(self.memory), before)

    def test_compact_never_removes_a_conflicting_file(self):
        learn.link(self.memory, self.record("a"))
        conflicting = self.legacy(self.record("a", version=9))
        with self.assertRaises(learn.LearnError):
            learn.load_publications(self.memory)
        with self.assertRaises(learn.LearnError):
            learn.compact(self.memory, remove=True)
        self.assertTrue(conflicting.exists())

    def test_an_unfinished_last_line_is_skipped_then_moved_aside_before_the_next_append(self):
        path = learn.link(self.memory, self.record("p1", createdAt="2026-10-01T00:00:00Z"))
        with path.open("ab") as stream:
            stream.write(b'{"postId":"p2","acc')
        warnings = io.StringIO()
        with contextlib.redirect_stderr(warnings):
            self.assertEqual(list(learn.load_publications(self.memory)), [("p1", "acct")])
            learn.link(self.memory, self.record("p3", createdAt="2026-10-02T00:00:00Z"))
        self.assertIn("unfinished last line", warnings.getvalue())
        self.assertEqual(sorted(learn.load_publications(self.memory)), [("p1", "acct"), ("p3", "acct")])
        self.assertTrue(path.read_bytes().endswith(b"\n"))
        [side] = path.parent.glob(path.name + ".cut-*")
        self.assertEqual(side.read_bytes(), b'{"postId":"p2","acc')

    def test_a_whole_last_record_missing_its_newline_is_kept_and_still_enforced(self):
        path = learn.link(self.memory, self.record("p1", createdAt="2026-10-01T00:00:00Z"))
        path.write_bytes(path.read_bytes().rstrip(b"\n"))  # as a hand-resolved merge can leave it
        self.assertEqual(list(learn.load_publications(self.memory)), [("p1", "acct")])
        with self.assertRaises(learn.LearnError):
            learn.link(self.memory, self.record("p1", version=7))
        learn.link(self.memory, self.record("p2", createdAt="2026-10-02T00:00:00Z"))
        self.assertEqual([r["postId"] for r in learn.read_log(path)], ["p1", "p2"])
        self.assertEqual(list(path.parent.glob("*.cut-*")), [])

    def test_logs_leave_no_lock_file_and_merge_line_by_line_in_git(self):
        learn.link(self.memory, self.record("p1", createdAt="2026-10-01T00:00:00Z"))
        directory = self.memory / "history" / "publications"
        self.assertEqual(sorted(p.name for p in directory.iterdir()), [".gitattributes", "2026-10.jsonl"])
        self.assertIn("*.jsonl merge=union", (directory / ".gitattributes").read_text())

    def test_a_real_lock_failure_is_reported_instead_of_falling_back(self):
        def failing(descriptor, operation):
            raise OSError(errno.EIO, "input/output error")
        with patch.object(learn.fcntl, "flock", failing):
            with self.assertRaises(OSError):
                learn.link(self.memory, self.record("p1"))
        self.assertFalse((self.memory / "history" / "publications" / ".lock").exists())

    def test_a_null_time_is_replaced_with_now(self):
        path = learn.link(self.memory, self.record("p1", createdAt=None))
        self.assertTrue(learn.read_log(path)[0]["createdAt"])

    def test_a_folder_that_cannot_be_locked_uses_a_lock_file_kept_out_of_git(self):
        flock = learn.fcntl.flock

        def files_only(descriptor, operation):
            if stat.S_ISDIR(os.fstat(descriptor).st_mode):
                raise OSError(errno.ENOTSUP, "folder locks are not supported here")
            return flock(descriptor, operation)
        with patch.object(learn.fcntl, "flock", files_only):
            learn.link(self.memory, self.record("p1"))
            learn.link(self.memory, self.record("p2"))
        self.assertEqual(sorted(learn.load_publications(self.memory)), [("p1", "acct"), ("p2", "acct")])
        directory = self.memory / "history" / "publications"
        self.assertTrue((directory / ".lock").is_file())
        self.assertIn(".lock", (directory / ".gitignore").read_text().splitlines())

    def test_parallel_links_from_separate_processes_are_all_kept(self):
        script = Path(learn.__file__).resolve()
        processes = [subprocess.Popen(
            [sys.executable, str(script), "link", "--memory", str(self.memory), "--post-id", "p{}".format(i),
             "--account-id", "acct", "--batch", "b", "--item", "clip-{}".format(i), "--version", "1"],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE) for i in range(12)]
        for process in processes:
            _, errors = process.communicate(timeout=60)
            self.assertEqual(process.returncode, 0, errors)
        self.assertEqual(len(learn.load_publications(self.memory)), 12)
        self.assertEqual(len(list((self.memory / "history" / "publications").glob("*.jsonl"))), 1)

    def test_link_requires_the_join_fields_and_safe_ids(self):
        with self.assertRaises(learn.LearnError):
            learn.link(self.memory, {"postId": "p1", "accountId": "acct"})
        with self.assertRaises(learn.LearnError):
            learn.link(self.memory, self.record("../escape"))

    def test_an_interrupted_links_temporary_file_is_ignored(self):
        learn.link(self.memory, self.record("p1"))
        leftover = self.memory / "history" / "publications" / ".pending-abc.json"
        leftover.write_text('{"postId": "p2", "acc', encoding="utf-8")
        self.assertEqual(list(learn.load_publications(self.memory)), [("p1", "acct")])

    def test_the_first_link_starts_memory_and_a_report_needs_one(self):
        elsewhere = tempfile.TemporaryDirectory()
        self.addCleanup(elsewhere.cleanup)
        fresh = Path(elsewhere.name).resolve()
        with self.assertRaises(learn.LearnError):
            learn.locate_memory(start=fresh)
        created = learn.locate_memory(start=fresh, create=True)
        self.assertEqual(created, fresh / ".viewprinter" / "content-memory")
        self.assertTrue(created.is_dir())

    def test_memory_is_discovered_from_a_nested_directory(self):
        nested = self.project / "a" / "b"
        nested.mkdir(parents=True)
        self.assertEqual(learn.locate_memory(start=nested), self.memory)

    # -- posting checkpoints ----------------------------------------------------

    def test_checkpoints_share_one_log_per_batch_and_resume_from_the_latest_state(self):
        base = {"batchId": "batch-1", "itemId": "clip-001", "version": 2, "accountId": "acct", "key": "k-1"}
        saved = dict(base, status="saved", postId="p1", accepted={"cover": "cover.jpg", "aiLabel": True})
        path = learn.checkpoint(self.memory, saved)
        self.assertEqual(path.name, "batch-1.jsonl")
        learn.checkpoint(self.memory, dict(saved))  # an identical retry adds nothing
        learn.checkpoint(self.memory, dict(base, status="verified", postId="p1", readback={"caption": "matches"}))
        learn.checkpoint(self.memory, dict(base, accountId="other", key="k-2", status="failed", note="rate limited"))
        self.assertEqual(len(learn.read_log(path)), 3)
        self.assertEqual({(p["accountId"], p["status"]) for p in learn.placements(self.memory, "batch-1")},
                         {("acct", "verified"), ("other", "failed")})
        self.assertEqual(list((self.memory / "history" / "posting").glob("*.jsonl")), [path])

    def test_events_without_a_key_join_their_placement_by_post_id(self):
        base = {"batchId": "b", "itemId": "clip-001", "version": 1, "accountId": "acct"}
        learn.checkpoint(self.memory, dict(base, status="saved", postId="p1", key="k-1"))
        learn.checkpoint(self.memory, dict(base, status="verified", postId="p1"))
        learn.checkpoint(self.memory, dict(base, status="saved", postId="p2", key="k-2"))  # a second placement
        self.assertEqual([(p["postId"], p["status"], p["events"]) for p in learn.placements(self.memory, "b")],
                         [("p1", "verified", 2), ("p2", "saved", 1)])

    def test_a_status_that_returns_after_another_is_recorded_again(self):
        base = {"batchId": "b", "itemId": "clip-001", "version": 1, "accountId": "acct", "key": "k-1",
                "postId": "p1"}
        for status in ("saved", "verified", "amended", "verified"):
            learn.checkpoint(self.memory, dict(base, status=status))
        for status in ("held", "saved", "held"):
            learn.checkpoint(self.memory, dict(base, key="k-2", postId="p2", status=status))
        learn.checkpoint(self.memory, dict(base, key="k-2", postId="p2", status="held"))  # a retry
        self.assertEqual([(p["postId"], p["status"], p["events"]) for p in learn.placements(self.memory, "b")],
                         [("p1", "verified", 4), ("p2", "held", 3)])

    def test_a_failed_save_needs_its_key_and_joins_the_retry_that_succeeds(self):
        base = {"batchId": "b", "itemId": "clip-001", "version": 1, "accountId": "acct"}
        with self.assertRaises(learn.LearnError):
            learn.checkpoint(self.memory, dict(base, status="failed"))
        learn.checkpoint(self.memory, dict(base, status="failed", key="k-9", note="rate limited"))
        learn.checkpoint(self.memory, dict(base, status="saved", key="k-9", postId="p9"))
        self.assertEqual([(p["status"], p["events"]) for p in learn.placements(self.memory, "b")], [("saved", 2)])

    def test_an_amend_recorded_by_post_id_alone_joins_its_batch_placement(self):
        base = {"batchId": "b", "accountId": "acct", "postId": "p1"}
        learn.checkpoint(self.memory, dict(base, itemId="clip-001", version=1, key="k-1", status="saved"))
        learn.checkpoint(self.memory, dict(base, status="canceled"))
        self.assertEqual([(p["itemId"], p["status"], p["events"]) for p in learn.placements(self.memory, "b")],
                         [("clip-001", "canceled", 2)])

    def test_events_merged_out_of_order_are_read_in_time_order(self):
        path = self.memory / "history" / "posting" / "b.jsonl"
        path.parent.mkdir(parents=True)
        base = {"batchId": "b", "itemId": "clip-001", "version": 1, "accountId": "acct", "key": "k-1",
                "postId": "p1"}
        path.write_bytes(learn.log_line(dict(base, status="verified", createdAt="2026-10-02T10:05:00Z"))
                         + learn.log_line(dict(base, status="saved", createdAt="2026-10-02T10:00:00Z")))
        self.assertEqual(learn.placements(self.memory, "b")[0]["status"], "verified")

    def test_a_cancel_by_post_id_reaches_every_item_the_post_carried(self):
        base = {"batchId": "b", "accountId": "acct", "postId": "p1", "version": 1}
        learn.checkpoint(self.memory, dict(base, itemId="slide-a", key="k-a", status="saved"))
        learn.checkpoint(self.memory, dict(base, itemId="slide-b", key="k-b", status="saved"))
        learn.checkpoint(self.memory, {"batchId": "b", "accountId": "acct", "postId": "p1", "status": "canceled"})
        self.assertEqual([(p["itemId"], p["version"], p["status"]) for p in learn.placements(self.memory, "b")],
                         [("slide-a", 1, "canceled"), ("slide-b", 1, "canceled")])

    def test_an_item_without_a_version_and_a_null_time_still_join_in_order(self):
        base = {"batchId": "b", "accountId": "acct", "postId": "p1", "itemId": "clip-001"}
        learn.checkpoint(self.memory, dict(base, version=2, key="k-1", status="saved"))
        learn.checkpoint(self.memory, dict(base, status="amended", createdAt=None))
        self.assertEqual([(p["version"], p["status"], p["events"]) for p in learn.placements(self.memory, "b")],
                         [(2, "amended", 2)])

    def test_a_campaign_post_is_checkpointed_under_its_campaign_without_an_item(self):
        learn.checkpoint(self.memory, {"batchId": "campaign-7", "accountId": "removed", "postId": "p1",
                                       "status": "canceled"})
        learn.checkpoint(self.memory, {"batchId": "campaign-7", "accountId": "kept", "postId": "p1",
                                       "status": "amended", "accepted": {"accounts": ["kept"]}})
        self.assertEqual({(p["accountId"], p["status"]) for p in learn.placements(self.memory, "campaign-7")},
                         {("removed", "canceled"), ("kept", "amended")})
        self.assertEqual(learn.main(["checkpoints", "--memory", str(self.memory), "--batch", "campaign-7"]), 0)

    def test_a_checkpoint_needs_a_known_status_and_a_post_id_unless_it_failed(self):
        base = {"batchId": "batch-1", "itemId": "clip-001", "version": 1, "accountId": "acct", "key": "k-1"}
        for bad in (dict(base, status="posted", postId="p1"), dict(base, status="saved"),
                    dict(base, batchId="../escape", status="failed"),
                    dict(base, status="saved", postId="p1", accepted="cover.jpg")):
            with self.assertRaises(learn.LearnError):
                learn.checkpoint(self.memory, bad)
        learn.checkpoint(self.memory, dict(base, status="failed"))
        self.assertEqual(learn.placements(self.memory, "never-posted"), [])

    # -- reading responses -----------------------------------------------------

    def test_newest_observation_wins_and_observations_are_never_summed(self):
        older = {"posts": [target("p1", "acct", 100, "2026-09-01T00:00:00Z", "2026-09-02T00:00:00Z")]}
        newer = {"posts": [target("p1", "acct", 250, "2026-09-01T00:00:00Z", "2026-09-05T00:00:00Z")]}
        rows = learn.destinations([newer, older])
        self.assertEqual(rows[("p1", "acct")]["views"], 250)

    def test_unmeasured_and_pending_destinations_are_not_zero_view_results(self):
        learn.link(self.memory, self.record("pending"))
        learn.link(self.memory, self.record("missing"))
        saves = {"posts": [target("pending", "acct", None, None, None, status="scheduled")]}
        report = learn.build_report(self.memory, [saves])
        self.assertEqual(report["counts"]["compared"], 0)
        reasons = sorted(e["reason"] for e in report["unmeasured"])
        self.assertEqual(reasons, ["not in the saved posts", "status scheduled"])

    # -- fair comparison -------------------------------------------------------

    def test_a_post_is_compared_only_with_its_own_accounts_same_age_and_mode(self):
        learn.link(self.memory, self.record("hit"))
        posts = [target("hit", "acct", 3000, "2026-09-01T12:00:00Z", "2026-09-08T12:00:00Z")]
        posts += self.peers("acct", 5, 1000)                         # same cohort
        posts += self.peers("other", 5, 50000)                       # another account
        posts += self.peers("acct", 5, 9000, prefix="trial", trial="SS_PERFORMANCE")
        posts += [target("young-{}".format(i), "acct", 10, "2026-09-08T00:00:00Z",
                         "2026-09-08T12:00:00Z") for i in range(5)]  # under a day old
        report = learn.build_report(self.memory, [{"posts": posts}])
        entry = report["publications"][0]
        self.assertEqual(entry["peers"], 5)
        self.assertAlmostEqual(entry["viewsIndex"], 3.0)
        self.assertEqual(entry["bucket"], "7-30d")

    def test_no_baseline_without_enough_peers(self):
        learn.link(self.memory, self.record("hit"))
        posts = [target("hit", "acct", 3000, "2026-09-01T12:00:00Z", "2026-09-08T12:00:00Z")]
        posts += self.peers("acct", 4, 1000)
        entry = learn.build_report(self.memory, [{"posts": posts}])["publications"][0]
        self.assertIsNone(entry["viewsIndex"])

    def test_paid_support_is_excluded_from_organic_comparison_and_baselines(self):
        learn.link(self.memory, self.record("boosted", paidSupport=True))
        learn.link(self.memory, self.record("organic", item="clip-002"))
        posts = [target("boosted", "acct", 900000, "2026-09-01T12:00:00Z", "2026-09-08T12:00:00Z"),
                 target("organic", "acct", 2000, "2026-09-01T12:00:00Z", "2026-09-08T12:00:00Z")]
        posts += self.peers("acct", 5, 1000)
        report = learn.build_report(self.memory, [{"posts": posts}])
        self.assertEqual(report["counts"]["paidSupportExcluded"], 1)
        organic = report["publications"][0]
        self.assertEqual(organic["peers"], 5)
        self.assertAlmostEqual(organic["viewsIndex"], 2.0)

    def test_promoted_posts_leave_baselines_even_when_unlinked(self):
        learn.link(self.memory, self.record("organic"))
        learn.link(self.memory, self.record("boosted-later", item="clip-002"))
        posts = [target("organic", "acct", 2000, "2026-09-01T12:00:00Z", "2026-09-08T12:00:00Z"),
                 target("boosted-later", "acct", 2000, "2026-09-01T12:00:00Z", "2026-09-08T12:00:00Z")]
        posts += self.peers("acct", 5, 1000)
        posts += self.peers("acct", 3, 90000, prefix="spark")
        report = learn.build_report(self.memory, [{"posts": posts}],
                                    promoted=["spark-acct-0", "spark-acct-1", ("spark-acct-2", "acct"),
                                              "boosted-later"])
        self.assertEqual(report["counts"]["promotedLeftOutOfBaselines"], 4)
        self.assertEqual(report["counts"]["paidSupportExcluded"], 1)
        organic = report["publications"][0]
        self.assertEqual(organic["peers"], 5)
        self.assertAlmostEqual(organic["viewsIndex"], 2.0)

    def test_engagement_counts_only_reported_counters(self):
        row = learn.destinations([{"posts": [target("p", "a", 1000, "2026-09-01T00:00:00Z",
                                                    "2026-09-02T00:00:00Z", saves=None)]}])[("p", "a")]
        self.assertAlmostEqual(learn.engagement_rate(row), (10 + 1 + 2) / 1000)

    # -- decisions -------------------------------------------------------------

    def format_report(self, views_list, fmt="format-a", baseline=1000, engagement_peer_likes=10,
                      engagement_likes=10, published="2026-09-01T12:00:00Z"):
        posts = self.peers("acct", 6, baseline, likes=engagement_peer_likes)
        for i, views in enumerate(views_list):
            post_id = "{}-{}".format(fmt, i)
            learn.link(self.memory, self.record(post_id, item="clip-{}".format(i), fmt=fmt))
            posts.append(target(post_id, "acct", views, published, "2026-09-08T12:00:00Z",
                                likes=engagement_likes))
        return {s["format"]: s for s in learn.build_report(self.memory, [{"posts": posts}])["formats"]}

    def test_double_down_needs_a_strong_median_and_most_posts_above_baseline(self):
        summary = self.format_report([2000, 1800, 900])["format-a"]
        self.assertEqual(summary["suggestion"], "double down")

    def test_an_old_format_name_counts_under_the_current_id(self):
        (self.memory / "formats" / "format-a").mkdir(parents=True)
        (self.memory / "formats" / "format-a" / "v1.json").write_text(
            json.dumps({"id": "format-a", "revision": 1, "aliases": ["format-a-old"]}), encoding="utf-8")
        summary = self.format_report([2000, 1800, 900], fmt="format-a-old")
        self.assertEqual(list(summary), ["format-a"])
        self.assertEqual(summary["format-a"]["publications"], 3)
        posts = self.peers("acct", 6, 1000) + [
            target("format-a-old-{}".format(i), "acct", views, "2026-09-01T12:00:00Z", "2026-09-08T12:00:00Z")
            for i, views in enumerate([2000, 1800, 900])]
        report = learn.build_report(self.memory, [{"posts": posts}])
        self.assertEqual({e["publication"]["formatId"] for e in report["publications"]}, {"format-a"})
        self.assertEqual({e["publication"]["formerFormatId"] for e in report["publications"]}, {"format-a-old"})
        self.assertNotIn("| format-a-old |", learn.render_markdown(report))

    def test_one_viral_outlier_is_vary_not_double_down(self):
        summary = self.format_report([50000, 700, 800])["format-a"]
        self.assertEqual(summary["suggestion"], "vary")

    def test_high_engagement_without_reach_says_which_job_it_does(self):
        summary = self.format_report([1000, 900, 1100], engagement_likes=40)["format-a"]
        self.assertEqual(summary["suggestion"], "vary")
        self.assertIn("doesn't earn reach", summary["why"])

    def test_too_few_or_too_young_is_keep_testing(self):
        self.assertEqual(self.format_report([5000, 5000])["format-a"]["suggestion"], "keep testing")

    def test_retire_needs_low_views_low_engagement_and_five_publications(self):
        summary = self.format_report([300, 400, 350, 200, 450], engagement_likes=1,
                                     engagement_peer_likes=40)["format-a"]
        self.assertEqual(summary["suggestion"], "retire")
        four = self.format_report([300, 400, 350, 200], fmt="format-b", engagement_likes=1,
                                  engagement_peer_likes=40)["format-b"]
        self.assertEqual(four["suggestion"], "vary")

    # -- command line ----------------------------------------------------------

    def test_command_line_link_and_report(self):
        saved = self.project / "posts.json"
        posts = [target("hit", "acct", 3000, "2026-09-01T12:00:00Z", "2026-09-08T12:00:00Z")]
        posts += self.peers("acct", 5, 1000)
        saved.write_text(json.dumps({"posts": posts}), encoding="utf-8")
        self.assertEqual(learn.main(["link", "--memory", str(self.memory), "--post-id", "hit",
                                     "--account-id", "acct", "--batch", "b", "--item", "clip-1",
                                     "--version", "2", "--format", "format-a"]), 0)
        stored = learn.load_publications(self.memory)[("hit", "acct")]
        self.assertEqual(stored["version"], 2)
        with patch("sys.stdin", io.StringIO('{"accepted": {"cover": "cover.jpg"}}')):
            self.assertEqual(learn.main(["checkpoint", "--memory", str(self.memory), "--batch", "b",
                                         "--item", "clip-1", "--version", "2", "--account-id", "acct",
                                         "--post-id", "hit", "--key", "k-1", "--status", "saved",
                                         "--details", "-"]), 0)
        placement = learn.placements(self.memory, "b")[0]
        self.assertEqual((placement["status"], placement["version"]), ("saved", 2))
        self.assertEqual(learn.main(["checkpoints", "--memory", str(self.memory), "--batch", "b", "--json"]), 0)
        self.assertEqual(learn.main(["compact", "--memory", str(self.memory)]), 0)
        markdown = self.project / "report.md"
        self.assertEqual(learn.main(["report", "--memory", str(self.memory), "--posts", str(saved),
                                     "--markdown", str(markdown)]), 0)
        text = markdown.read_text()
        self.assertIn("| format-a | 1 | 1 | 3.00x", text)
        self.assertEqual(learn.main(["report", "--memory", str(self.memory), "--posts", str(saved),
                                     "--as-of", "2026-09-05T00:00", "--markdown", str(markdown)]), 0)
        self.assertEqual(learn.main(["report", "--memory", str(self.project / "nowhere"),
                                     "--posts", str(saved)]), 1)


if __name__ == "__main__":
    unittest.main()
