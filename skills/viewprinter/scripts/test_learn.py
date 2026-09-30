#!/usr/bin/env python3
"""Run with: python3 -m unittest discover -s scripts -p 'test_learn.py'."""

import json
import os
from pathlib import Path
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

    # -- link ---------------------------------------------------------------

    def test_link_writes_one_immutable_event_and_accepts_identical_retry(self):
        first = learn.link(self.memory, self.record("p1"))
        again = learn.link(self.memory, self.record("p1"))
        self.assertEqual(first, again)
        self.assertEqual(first.name, "p1--acct.json")
        with self.assertRaises(learn.LearnError):
            learn.link(self.memory, self.record("p1", version=2))

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
        stored = json.loads((self.memory / "history/publications/hit--acct.json").read_text())
        self.assertEqual(stored["version"], 2)
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
