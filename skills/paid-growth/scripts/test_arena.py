#!/usr/bin/env python3
"""Run from this directory: python3 -m unittest discover -s . -p 'test_*.py'. All numbers are invented."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import arena


def ad(**fields):
    row = {"ad_id": fields.pop("ad_id", "a1"), "group": fields.pop("group", "t1"),
           "role": fields.pop("role", "test"), "spend": 0}
    row.update(fields)
    return arena.normalize_row(row, 1)


def day(number, **fields):
    return ad(date="2026-03-{:02d}".format(number), **fields)


# Break-even $30 per payer: 0.8 x $27 per trial + 0.2 x $42 per purchase.
CONFIG = {
    "schemaVersion": 1,
    "value": {"perTrial": 27.0, "perPurchase": 42.0, "trialShare": 0.8, "breakEvenPerPayer": 30.0,
              "basis": "measured"},
    "rules": {},
}


def verdicts(rows, account_window=False, config=CONFIG):
    result = arena.evaluate(config, rows, account_window)
    return {row["ad_id"]: (row["verdict"], row["reason"]) for row in result["ads"]}, result


class RuleTests(unittest.TestCase):
    def test_weak_engagement_is_cut_even_with_cheap_early_payers(self):
        # The failure this rule exists for: cheap early payers hid a weak ad.
        rows = [ad(spend=60, impressions=10000, clicks=35, plays=9000, views_2s=1620,
                   trials=3, purchases=2)]
        verdict, reason = verdicts(rows)[0]["a1"]
        self.assertEqual(verdict, "cut")
        self.assertIn("CTR 0.35%", reason)
        self.assertIn("2s hold 18.00%", reason)

    def test_engagement_stops_deciding_once_revenue_is_proven(self):
        rows = [ad(spend=450, impressions=90000, clicks=300, trials=14, purchases=4)]
        self.assertEqual(verdicts(rows)[0]["a1"][0], "graduate")

    def test_starved_ad_is_no_read_not_a_loser(self):
        rows = [ad(ad_id="fav", spend=144, impressions=18000, clicks=165, trials=2),
                ad(ad_id="starved", spend=6, impressions=700, clicks=2, trials=0)]
        verdict, reason = verdicts(rows)[0]["starved"]
        self.assertEqual(verdict, "no read")
        self.assertIn("4%", reason)

    def test_below_the_first_check_waits(self):
        rows = [ad(spend=40, impressions=4500, clicks=8, trials=0)]
        self.assertEqual(verdicts(rows)[0]["a1"][0], "wait")

    def test_no_payer_at_three_times_break_even_is_cut(self):
        rows = [ad(spend=92, impressions=8000, clicks=70, plays=7000, views_2s=3500, trials=0)]
        self.assertEqual(verdicts(rows)[0]["a1"][0], "cut")

    def test_value_cut_needs_enough_payers(self):
        weak = [ad(spend=375, impressions=30000, clicks=300, trials=5, purchases=1)]
        verdict, reason = verdicts(weak)[0]["a1"]
        self.assertEqual(verdict, "cut")
        self.assertIn("projected ROAS 0.47", reason)
        few = [ad(spend=180, impressions=22000, clicks=220, trials=3)]
        self.assertEqual(verdicts(few)[0]["a1"][0], "hold")

    def test_few_payers_are_cut_once_even_the_best_case_loses(self):
        rows = [ad(ad_id="bleeding", spend=300, impressions=30000, clicks=300, plays=27000,
                   views_2s=13500, trials=1),
                ad(ad_id="early", group="t2", spend=100, impressions=10000, clicks=100, plays=9000,
                   views_2s=4500, trials=1),
                ad(ad_id="winner", group="w1", role="winner", spend=750, impressions=90000,
                   clicks=800, trials=2)]
        result = verdicts(rows)[0]
        self.assertEqual(result["bleeding"][0], "cut")
        self.assertIn("top of the 90% range", result["bleeding"][1])
        self.assertEqual(result["early"][0], "hold")
        self.assertEqual(result["winner"][0], "pull back")

    def test_one_graduate_per_round(self):
        rows = [ad(ad_id="best", spend=100, impressions=11000, clicks=110, trials=5),
                ad(ad_id="second", spend=100, impressions=11000, clicks=110, trials=4),
                ad(ad_id="other-group", group="t2", spend=90, impressions=10000, clicks=100, trials=4)]
        result = verdicts(rows)[0]
        self.assertEqual(result["best"][0], "graduate")
        self.assertEqual(result["second"][0], "hold")
        self.assertIn("leads its round", result["second"][1])
        self.assertEqual(result["other-group"][0], "graduate")

    def test_rounds_scope_starvation_and_graduation(self):
        def pull(with_round):
            def row(ad_id, number, **fields):
                return ad(ad_id=ad_id, round="r{}".format(number) if with_round else None, **fields)
            return [row("old-a", 1, spend=180, impressions=20000, clicks=200, trials=3),
                    row("old-b", 1, spend=30, impressions=3000, clicks=30, trials=0),
                    row("new-a", 2, spend=45, impressions=5000, clicks=50, trials=1),
                    row("new-b", 2, spend=22.5, impressions=2500, clicks=25, trials=0)]
        scoped, _ = verdicts(pull(True), account_window=True)
        self.assertEqual(scoped["new-b"][0], "wait")
        self.assertEqual(scoped["old-b"][0], "no read")
        mixed, result = verdicts(pull(False), account_window=True)
        self.assertEqual(mixed["new-b"][0], "no read")
        self.assertTrue(any("no round" in warning for warning in result["warnings"]))

        winners = [ad(ad_id="old", round="r1", spend=100, impressions=11000, clicks=110, trials=5),
                   ad(ad_id="new", round="r2", spend=100, impressions=11000, clicks=110, trials=5)]
        self.assertEqual({v for v, _ in verdicts(winners)[0].values()}, {"graduate"})

    def test_unknown_payers_never_cut_on_revenue(self):
        rows = [ad(spend=150, impressions=15000, clicks=135, plays=13000, views_2s=6500)]
        verdict, reason = verdicts(rows)[0]["a1"]
        self.assertEqual(verdict, "hold")
        self.assertIn("payers unknown", reason)

    def test_winner_scales_only_on_enough_payers_and_margin(self):
        rows = [ad(role="winner", group="w1", spend=375, trials=14, purchases=4),
                ad(ad_id="thin", role="winner", group="w2", spend=150, trials=6)]
        result = verdicts(rows)[0]
        self.assertEqual(result["a1"][0], "scale")
        self.assertEqual(result["thin"][0], "hold")

    def test_fatigue_blocks_scaling_and_pull_back_wins(self):
        tired = [ad(role="winner", group="w1", spend=375, impressions=60000, clicks=360,
                    peak_ctr="0.9%", trials=14, purchases=4)]
        verdict, reason = verdicts(tired)[0]["a1"]
        self.assertEqual(verdict, "fatigue")
        self.assertIn("best 3 days 0.90%", reason)
        losing = [ad(role="winner", group="w1", spend=375, impressions=60000, clicks=360,
                     peak_ctr="0.9%", trials=9)]
        self.assertEqual(verdicts(losing)[0]["a1"][0], "pull back")

    def test_daily_series_gives_latest_and_best_three_days(self):
        def week(clicks_by_day):
            return [day(number, role="winner", group="w1", spend=100, impressions=20000, clicks=clicks,
                        plays=18000, views_2s=8100, trials=4)
                    for number, clicks in enumerate(clicks_by_day, start=1)]
        verdict, reason = verdicts(week([200, 200, 200, 160, 120, 120, 120]))[0]["a1"]
        self.assertEqual(verdict, "fatigue")
        self.assertIn("CTR 0.60% (last 3 days) vs best 3 days 1.00%", reason)
        self.assertNotIn("hold", reason)
        self.assertEqual(verdicts(week([200] * 7))[0]["a1"], ("hold", "steady"))

    def test_daily_rows_are_one_ad(self):
        daily = [day(number, spend=35, impressions=3000, clicks=30, plays=2800, views_2s=1400,
                     trials=0 if number == 2 else None) for number in (1, 2, 3)]
        verdict_map, result = verdicts(daily)
        self.assertEqual(len(result["ads"]), 1)
        combined = result["ads"][0]
        self.assertEqual((combined["spend"], combined["days"], combined["payers"]), (105, 3, 0))
        self.assertAlmostEqual(combined["ctr"], 0.01)
        self.assertEqual(verdict_map["a1"][0], "cut")
        single = [ad(spend=105, impressions=9000, clicks=90, plays=8400, views_2s=4200, trials=0)]
        self.assertEqual(verdicts(single)[0], verdict_map)

    def test_repeated_or_conflicting_rows_are_refused(self):
        for rows in ([ad(spend=10), ad(spend=12)],
                     [day(1, spend=10), day(1, spend=12)],
                     [day(1, spend=10), day(2, group="t2", spend=12)],
                     [day(1, spend=10), day(2, role="winner", spend=12)]):
            with self.assertRaises(arena.ArenaError):
                arena.evaluate(CONFIG, rows)

    def test_governor_turns_scale_into_hold_only_on_an_account_window(self):
        rows = [ad(role="winner", group="w1", spend=375, trials=14, purchases=4),
                ad(ad_id="loser", group="t2", round="r1", spend=750, impressions=90000, clicks=750,
                   trials=5)]
        result, full = verdicts(rows, account_window=True)
        self.assertEqual(full["summary"]["governor"], "fired")
        self.assertEqual(result["a1"][0], "hold")
        self.assertIn("governor", result["a1"][1])
        result, partial = verdicts(rows)
        self.assertEqual(result["a1"][0], "scale")
        self.assertTrue(partial["summary"]["governor"].startswith("not applied"))

    def test_missing_role_is_judged_as_test_and_said_loudly(self):
        rows = [ad(role=None, group="w1", spend=450, impressions=60000, clicks=500, trials=14,
                   purchases=4)]
        verdict_map, result = verdicts(rows)
        self.assertEqual(verdict_map["a1"][0], "graduate")
        self.assertTrue(result["ads"][0]["roleAssumed"])
        self.assertIn("no role", result["warnings"][0])
        rendered = arena.render(result, "Mar 1-7")
        self.assertTrue(rendered.startswith("WARNING: Ads with no role: 1 of 1."))
        self.assertIn("test (assumed)", rendered)


class ValueModelTests(unittest.TestCase):
    def test_missing_value_model_is_refused(self):
        for value in ({}, {"perTrial": 27.0, "perPurchase": 42.0}):
            with self.assertRaises(arena.ArenaError):
                arena.evaluate({"schemaVersion": 1, "value": value}, [ad(spend=10)])

    def test_break_even_comes_from_config_not_the_pull(self):
        config = {"schemaVersion": 1, "value": {"perTrial": 27.0, "perPurchase": 42.0, "trialShare": 0.8}}
        for rows in ([ad(spend=50, trials=3)], [ad(spend=50, purchases=3)], [ad(spend=50, trials=0)]):
            self.assertAlmostEqual(arena.evaluate(config, rows)["breakEven"], 30.0)
        drifted = dict(config, value=dict(config["value"], breakEvenPerPayer=40.0))
        result = arena.evaluate(drifted, [ad(spend=50, trials=3)])
        self.assertEqual(result["breakEven"], 40.0)
        self.assertIn("differs from the trialShare mix", result["warnings"][0])

    def test_config_values_must_be_numbers(self):
        for config in ({"value": {"breakEvenPerPayer": "30"}},
                       {"value": {"breakEvenPerPayer": 30.0}, "rules": {"ctrFloor": "0.6%"}},
                       {"value": {"perTrial": 27.0, "perPurchase": 42.0, "trialShare": 1.5}},
                       {"value": {"breakEvenPerPayer": 30.0}, "rules": ["ctrFloor"]}):
            with self.assertRaises(arena.ArenaError):
                arena.evaluate(dict(config, schemaVersion=1), [ad(spend=10)])


class InputTests(unittest.TestCase):
    def test_poisson_interval_matches_exact_values(self):
        low, high = arena.poisson_interval(8)
        self.assertAlmostEqual(low, 3.98, places=1)
        self.assertAlmostEqual(high, 14.43, places=1)
        self.assertEqual(arena.poisson_interval(0)[0], 0.0)

    def test_ads_manager_export_headers_and_formats(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pull.csv"
            path.write_text("Ad name,Ad ID,Ad group name,Cost,Impressions,Clicks (destination),"
                            "Video views,2-second video views,Trials,Purchases\n"
                            "price-first,123,t2,\"$1,020.50\",\"100,000\",900,90000,45000,40,12\n",
                            encoding="utf-8")
            row = arena.load_rows(path)[0]
        self.assertEqual((row["ad_id"], row["group"], row["name"]), ("123", "t2", "price-first"))
        self.assertEqual(row["spend"], 1020.5)
        self.assertEqual(row["impressions"], 100000)
        self.assertEqual(row["views_2s"], 45000)
        self.assertIsNone(row["role"])

    def test_api_daily_rows_with_bare_percent_ctr(self):
        # The Marketing API sends ctr as a percent without the sign; the counts win.
        rows = [{"ad_id": "9", "adgroup_id": "77", "stat_time_day": "2026-03-0{} 00:00:00".format(n),
                 "spend": "10.50", "impressions": "1000", "clicks": "9", "ctr": "0.90",
                 "role": "test", "round": "r1"} for n in (1, 2)]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pull.json"
            path.write_text(json.dumps({"ads": rows}), encoding="utf-8")
            result = arena.evaluate(CONFIG, arena.load_rows(path))
        combined = result["ads"][0]
        self.assertEqual((combined["spend"], combined["days"], combined["group"]), (21.0, 2, "77"))
        self.assertAlmostEqual(combined["ctr"], 0.009)

    def test_rates_need_a_percent_sign_unless_counts_are_given(self):
        base = {"ad_id": "1", "group": "g", "role": "test", "spend": 40}
        with self.assertRaisesRegex(arena.ArenaError, "% sign"):
            arena.normalize_row(dict(base, ctr="0.45"), 1)
        with self.assertRaises(arena.ArenaError):
            arena.normalize_row(dict(base, peak_ctr=0.009), 1)
        self.assertAlmostEqual(arena.normalize_row(dict(base, ctr="0.45%"), 1)["ctr"], 0.0045)
        counted = arena.normalize_row(dict(base, ctr="0.45", clicks=9, impressions=1000), 1)
        self.assertIsNone(counted["ctr"])
        idle_day = arena.normalize_row(dict(base, spend=0, ctr="0.00", clicks=0, impressions=0), 1)
        self.assertIsNone(arena.measure(idle_day, {"perTrial": 1, "perPurchase": 1})["ctr"])

    def test_numbers_blanks_and_non_finite_values(self):
        self.assertAlmostEqual(arena.parse_number("0.83%"), 0.0083)
        self.assertAlmostEqual(arena.parse_number("0.0083"), 0.0083)
        self.assertIsNone(arena.parse_number(""))
        self.assertIsNone(arena.parse_number("-"))
        for bad in ("lots", "nan", "inf", float("nan")):
            with self.assertRaises(arena.ArenaError):
                arena.parse_number(bad)
        with self.assertRaises(arena.ArenaError):
            arena.normalize_row({"ad_id": "1", "group": "g", "spend": "nan"}, 1)
        with self.assertRaises(arena.ArenaError):
            arena.normalize_row({"ad_id": "1", "group": "g", "spend": 5, "clicks": -3}, 1)

    def test_rows_need_id_group_and_spend(self):
        with self.assertRaises(arena.ArenaError):
            arena.normalize_row({"ad_id": "1", "spend": 3}, 1)
        with self.assertRaises(arena.ArenaError):
            arena.normalize_row({"ad_id": "1", "group": "g", "spend": 3, "role": "champion"}, 1)


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.project = self.root / "project"
        self.project.mkdir()
        self.environment = patch.dict(os.environ)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        os.environ.pop(arena.ENVIRONMENT, None)

    def test_init_is_idempotent_and_never_overwrites_config(self):
        memory = arena.initialize(self.project, "Example")
        config = json.loads((memory / "config.json").read_text())
        self.assertEqual(config["rules"]["scalePayers"], 15)
        config["value"]["breakEvenPerPayer"] = 31.5
        (memory / "config.json").write_text(json.dumps(config))
        self.assertEqual(arena.initialize(self.project, "Example"), memory)
        self.assertEqual(json.loads((memory / "config.json").read_text())["value"]["breakEvenPerPayer"], 31.5)
        nested = self.project / "a" / "b"
        nested.mkdir(parents=True)
        self.assertEqual(arena.locate(nested), memory)

    def test_symlinked_project_path_is_resolved(self):
        # macOS /tmp and /var are symlinks; a path through one must still work.
        link = self.root / "link"
        link.symlink_to(self.project, target_is_directory=True)
        memory = arena.initialize(link, "Example")
        self.assertEqual(memory, self.project / ".viewprinter" / "paid-growth")
        self.assertEqual(arena.locate(link), memory)
        self.assertEqual(arena.initialize(Path(self.temporary.name) / "project"), memory)

    def test_symlink_inside_memory_is_refused(self):
        memory = arena.initialize(self.project, "Example")
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        decisions = memory / "history" / "decisions"
        decisions.rmdir()
        decisions.symlink_to(elsewhere, target_is_directory=True)
        event = {"id": "decision-001", "createdAt": "2026-03-01T15:00:00Z"}
        with self.assertRaises(arena.ArenaError):
            arena.append(memory, "decisions", event)
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_append_is_immutable_and_retry_safe(self):
        memory = arena.initialize(self.project, "Example")
        event = {"id": "decision-001", "createdAt": "2026-03-01T15:00:00Z", "proposal": "pause b"}
        first = arena.append(memory, "decisions", event)
        self.assertEqual(arena.append(memory, "decisions", event), first)
        with self.assertRaises(arena.ArenaError):
            arena.append(memory, "decisions", dict(event, proposal="pause c"))
        with self.assertRaises(arena.ArenaError):
            arena.append(memory, "decisions", dict(event, id="../escape"))
        with self.assertRaises(arena.ArenaError):
            arena.append(memory, "budgets", event)

    def test_memory_inside_the_skill_is_refused(self):
        with self.assertRaises(arena.ArenaError):
            arena.outside_skill(arena.SKILL_ROOT / "memory")
        link = self.root / "into-skill"
        link.symlink_to(arena.SKILL_ROOT, target_is_directory=True)
        with self.assertRaises(arena.ArenaError):
            arena.initialize(link, "Example")
        self.assertFalse((arena.SKILL_ROOT / ".viewprinter").exists())


if __name__ == "__main__":
    unittest.main()
