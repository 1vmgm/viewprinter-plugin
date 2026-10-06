"""Run: python -m unittest discover -s scripts -p 'test_review_gallery.py'."""

import base64
import copy
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote

import review_gallery


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def attributes(self, tag):
        return [attrs for name, attrs in self.tags if name == tag]


class GalleryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets = self.root / "assets"
        self.assets.mkdir()
        # Content decoding is the browser's responsibility; generator validates paths/types.
        for name in ("first.png", "prior.jpg", "clip.mp4", 'poster & \'quoted\'.svg'):
            (self.assets / name).write_bytes(b"fixture")
        self.manifest_path = self.root / "review.json"
        self.output = self.root / "nested" / "gallery.html"
        self.item = {"id": "P01", "version": 1, "title": "A useful idea", "format": "Portrait",
                     "status": "Draft", "kind": "image", "src": "assets/first.png"}
        self.manifest = {"title": "Round review", "round": 2, "items": [self.item]}

    def build(self):
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
        original = self.manifest_path.read_bytes()
        review_gallery.build_gallery(self.manifest_path, self.output)
        self.assertEqual(self.manifest_path.read_bytes(), original)
        self.text = self.output.read_text(encoding="utf-8")
        return Document(self.text)

    def test_batches_lead_with_latest_without_renumbering_items(self):
        self.item.update(batch="older", status="revised")
        newest = dict(self.item, id="P02", batch="latest", status="new", changes=[])
        self.manifest.update(batches=[{"id":"latest", "label":"Coffee · P02"},
                                      {"id":"older", "label":"Original · P01"}], items=[self.item, newest])
        doc = self.build()
        cards = doc.attributes("article")
        self.assertEqual([c["data-batch"] for c in cards], ["latest", "older"])
        selected = [o for o in doc.attributes("option") if "selected" in o]
        self.assertEqual([o["value"] for o in selected], ["latest"])
        self.assertEqual([b["data-batch-view"] for b in doc.attributes("button") if "data-batch-view" in b], ["latest", ""])
        original_anchor = cards[1]["id"]
        self.manifest["items"].reverse()
        self.assertEqual(self.build().attributes("article")[1]["id"], original_anchor)

    def test_batches_require_complete_explicit_membership(self):
        cases = [
            ([{"id":"a", "label":"A"}], None, "batch must be a nonempty"),
            ([{"id":"a", "label":"A"}], "missing", "declared batch"),
            ([{"id":"a", "label":"A"}, {"id":"a", "label":"Again"}], "a", "duplicate batch"),
            ([{"id":"a", "label":"A"}, {"id":"b", "label":"Empty"}], "a", "at least one item"),
            ([], "orphan", "requires manifest.batches"),
        ]
        for batches, batch, error in cases:
            with self.subTest(batches=batches, batch=batch):
                self.manifest["batches"] = batches
                self.item["batch"] = batch
                with self.assertRaisesRegex(ValueError, error):
                    self.build()

    def test_batch_labels_and_ids_cannot_inject_markup(self):
        hostile = '\"><script>bad()</script>'
        self.manifest["batches"] = [{"id":hostile, "label":hostile}]
        self.item["batch"] = hostile
        doc = self.build()
        self.assertEqual(len(doc.attributes("script")), 1)
        self.assertEqual(doc.attributes("article")[0]["data-batch"], hostile)
        self.assertEqual(next(o["value"] for o in doc.attributes("option") if "selected" in o), hostile)

    def test_relative_urls_resolve_from_output_directory(self):
        self.item.update(kind="video", src="assets/clip.mp4", poster="assets/poster & 'quoted'.svg")
        self.item["previous"] = {"version": 0, "kind": "image", "src": "assets/prior.jpg"}
        doc = self.build()
        self.assertTrue(doc.attributes("details"))
        urls = [attrs["src"] for tag, attrs in doc.tags if "src" in attrs]
        urls += [attrs["poster"] for attrs in doc.attributes("video")]
        for url in urls:
            self.assertTrue(url.startswith("./../assets/"), url)
            self.assertTrue((self.output.parent / unquote(url)).resolve().is_file())
        self.assertTrue(any("%26" in url and "%27" in url for url in urls))
        self.assertEqual(len([a for a in doc.attributes("a") if a.get("target") == "_blank"]), 2)

    def test_copy_reference_round_trips_punctuation_without_extra_markup(self):
        reference_id = 'clip "A" <three> & café'
        self.item.update(id=reference_id, version=12)
        doc = self.build()
        buttons = [a for a in doc.attributes("button") if "data-copy-reference" in a]
        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons[0]["data-copy-reference"], reference_id + " / v12")
        self.assertEqual(buttons[0]["type"], "button")
        self.assertEqual(len(doc.attributes("img")), 1)
        self.assertTrue(any(a.get("id") == "copy-status" and a.get("aria-live") == "polite"
                            for a in doc.attributes("span")))

    def test_speed_controls_only_when_any_review_media_can_play(self):
        self.assertFalse(any("data-playback-speed" in a for a in self.build().attributes("button")))
        self.item["inputs"] = [{"label":"Performance", "kind":"video", "src":"assets/clip.mp4"}]
        doc = self.build()
        speeds = [a for a in doc.attributes("button") if "data-playback-speed" in a]
        self.assertEqual([a["data-playback-speed"] for a in speeds], ["0.5", "0.75", "1", "1.25", "1.5", "2"])
        self.assertEqual([a["data-playback-speed"] for a in speeds if a["aria-pressed"] == "true"], ["1"])
        self.assertTrue(all(v["preload"] == "none" for v in doc.attributes("video")))
        self.item.pop("inputs")
        self.item["previous"] = {"version":0, "kind":"video", "src":"assets/clip.mp4"}
        self.assertTrue(any("data-playback-speed" in a for a in self.build().attributes("button")))

    def test_hidden_video_sources_wait_for_review(self):
        self.item.update(kind="video", src="assets/clip.mp4")
        self.item["previous"] = {"version":0, "kind":"video", "src":"assets/clip.mp4"}
        self.item["inputs"] = [{"label":"Source", "kind":"video", "src":"assets/clip.mp4"}]
        doc = self.build()
        self.assertEqual([v["preload"] for v in doc.attributes("video")], ["none", "none", "none"])
        self.assertFalse(any("open" in a for a in doc.attributes("details")))

    def test_hostile_manifest_text_cannot_create_markup_or_script(self):
        hostile = '\"><script>alert("bad")</script><img src=x onerror=alert(1)>&'
        self.manifest.update(title=hostile, round=hostile)
        for key in ("id", "version", "title", "format", "caption"):
            self.item[key] = hostile
        self.item["changes"] = [hostile]
        doc = self.build()
        self.assertEqual(len(doc.attributes("script")), 1)
        self.assertEqual(len(doc.attributes("img")), 1)
        self.assertFalse(any(key.startswith("on") for _, attrs in doc.tags for key in attrs))
        self.assertNotIn(hostile, self.text)
        self.assertIn("&lt;script&gt;", self.text)
        self.assertIn(hostile, [option.get("value") for option in doc.attributes("option")])
        self.assertEqual(doc.attributes("script"), [{}])
        expected_hash = base64.b64encode(hashlib.sha256(review_gallery.SCRIPT.encode()).digest()).decode()
        policy = next(attrs["content"] for attrs in doc.attributes("meta") if attrs.get("http-equiv") == "Content-Security-Policy")
        self.assertIn("'sha256-" + expected_hash + "'", policy)

    def test_read_only_page_uses_paused_media_and_accessible_filters(self):
        self.item.update(kind="video", src="assets/clip.mp4")
        doc = self.build()
        self.assertFalse(any(tag in {"textarea", "input", "form"} for tag, _ in doc.tags))
        self.assertEqual({a["id"] for a in doc.attributes("select")}, {"status-filter", "format-filter"})
        self.assertEqual({a["for"] for a in doc.attributes("label")}, {"status-filter", "format-filter"})
        for video in doc.attributes("video"):
            self.assertNotIn("autoplay", video)
            self.assertNotIn("loop", video)
            self.assertIn("controls", video)
            self.assertIn("aria-label", video)
            self.assertEqual(video["preload"], "none")
        self.assertNotIn(".play()", review_gallery.SCRIPT)
        self.assertIn("video !== event.target", review_gallery.SCRIPT)
        self.assertIn("video.pause()", review_gallery.SCRIPT)

    def test_missing_asset_fails_without_writing_output(self):
        self.item["src"] = "assets/missing.png"
        with self.assertRaisesRegex(ValueError, "asset does not exist"):
            self.build()
        self.assertFalse(self.output.exists())

    def test_duplicate_id_and_version_rejected_even_across_number_string(self):
        other = copy.deepcopy(self.item)
        other["version"] = "1"
        self.manifest["items"].append(other)
        with self.assertRaisesRegex(ValueError, "duplicate id/version"):
            self.build()

    def test_revised_first_and_stable_anchors(self):
        revised = dict(self.item, id="P02", version=2, status="Revised")
        self.manifest["items"].append(revised)
        first = self.build().attributes("article")
        self.assertEqual(first[0]["data-status"], "Revised")
        self.manifest["items"].reverse()
        second = self.build().attributes("article")
        self.assertEqual([a["id"] for a in first], [a["id"] for a in second])
        self.assertEqual(len({a["id"] for a in first}), 2)

    def test_urls_rejected_in_all_media_fields(self):
        for url in ("https://example.test/a.png", "//example.test/a.png", "javascript:alert(1)", "data:image/png;base64,AA", "file:///tmp/a.png"):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "asset URLs"):
                review_gallery.asset_path(url, self.root, "test", "image")
        self.item["previous"] = {"version": 0, "kind": "image", "src": "https://example.test/a.png"}
        with self.assertRaisesRegex(ValueError, "previous.src"):
            self.build()
        self.item.pop("previous")
        self.item.update(kind="video", src="assets/clip.mp4", poster="https://example.test/a.png")
        with self.assertRaisesRegex(ValueError, "poster"):
            self.build()

    def test_invalid_schema_and_asset_kind_report_clear_errors(self):
        for field, value, message in (("kind", "document", "kind"), ("changes", "not a list", "changes"),
                                      ("caption", [], "caption"), ("src", "assets/clip.mp4", "extension")):
            with self.subTest(field=field):
                original = copy.deepcopy(self.item)
                self.item[field] = value
                with self.assertRaisesRegex(ValueError, message):
                    self.build()
                self.item.clear()
                self.item.update(original)

    def test_output_cannot_overwrite_manifest(self):
        self.manifest_path = self.root / "manifest.html"
        self.output = self.manifest_path
        with self.assertRaisesRegex(ValueError, "must not overwrite"):
            self.build()

    def test_sections_require_final_stage_and_approval_for_complete(self):
        self.item.update(status="approved", stage="source")
        self.manifest["items"] += [dict(self.item, id="P02", stage="final"),
                                   dict(self.item, id="P03", status="revised", stage="final")]
        cards = self.build().attributes("article")
        self.assertEqual([c["data-lane"] for c in cards], ["review", "progress", "complete"])

    def test_unknown_status_fails_without_writing_and_known_statuses_are_case_insensitive(self):
        for status in ("rejected", "Approved!", '"><script>alert(1)</script>'):
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, r"status .* is not one of"):
                self.item["status"] = status
                self.build()
        self.assertFalse(self.output.exists())
        self.item["status"] = "Changes-Requested"
        self.manifest["items"].append(dict(self.item, id="P02", status="HELD"))
        self.assertEqual([c["data-lane"] for c in self.build().attributes("article")], ["review", "progress"])

    def test_failed_write_keeps_the_previous_gallery(self):
        self.build()
        original = self.output.read_bytes()
        self.manifest["title"] = "Unencodable \ud800"
        with self.assertRaises(UnicodeEncodeError):
            self.build()
        self.manifest["title"] = "Round review"
        with patch.object(review_gallery.os, "replace", side_effect=OSError("disk full")), \
                self.assertRaisesRegex(OSError, "disk full"):
            self.build()
        self.assertEqual(self.output.read_bytes(), original)
        self.assertEqual(list(self.output.parent.iterdir()), [self.output])

    def test_pending_output_needs_no_fake_media(self):
        self.item.update(status="generating", stage="source", nextStep="Performance rendering")
        self.item.pop("src")
        doc = self.build()
        self.assertEqual(doc.attributes("img"), [])
        self.assertIn("Performance rendering", self.text)
        self.item["status"] = "approved"
        with self.assertRaisesRegex(ValueError, "src required"):
            self.build()

    def test_inputs_audio_and_generation_costs_are_explicit(self):
        (self.assets / "clip.wav").write_bytes(b"fixture")
        self.item["inputs"] = [{"kind":"audio", "src":"assets/clip.wav", "label":"Music-only cut"}]
        self.item["generation"] = [
            {"asset":"Performance", "platform":"Provider A", "model":"Model A", "cost":{"status":"estimated", "amount":4.62, "unit":"USD"}},
            {"asset":"Still", "platform":"Provider B", "model":"Model B", "cost":{"status":"reported", "amount":20, "unit":"credits"}},
            {"asset":"Reference", "platform":"Provider C", "model":"Not recorded", "prompt":"<script>unsafe</script>"}]
        doc = self.build()
        self.assertEqual(len(doc.attributes("audio")), 1)
        self.assertIn("4.62 USD · estimated", self.text)
        self.assertIn("20 credits · reported", self.text)
        self.assertIn("Cost not reported", self.text)
        self.assertEqual(len(doc.attributes("script")), 1)
        self.assertFalse(any('open' in x for x in doc.attributes('details')))
        self.assertIn("video,audio", review_gallery.SCRIPT)
        self.assertNotIn("Total spend", self.text)

    def test_invalid_costs_and_undated_balances_are_rejected(self):
        g = {"asset":"Still", "platform":"Provider", "model":"Model"}
        self.item["generation"] = [g]
        for amount in (True, -1, float('nan'), float('inf'), "20"):
            with self.subTest(amount=amount), self.assertRaisesRegex(ValueError, "amount"):
                g["cost"] = {"status":"reported", "amount":amount, "unit":"credits"}
                self.build()
        g["cost"] = {"status":"unknown"}
        self.manifest["balances"] = [{"platform":"Provider", "amount":200, "unit":"credits"}]
        with self.assertRaisesRegex(ValueError, "asOf"):
            self.build()
        self.manifest["balances"][0]["asOf"] = "2026-09-23T12:00:00Z"
        self.build()
        self.assertIn("As of 2026-09-23T12:00:00Z", self.text)

    def test_input_paths_have_same_safety_checks_as_main_output(self):
        self.item["inputs"] = [{"kind":"image", "src":"https://bad.example/a.png", "label":"Reference"}]
        with self.assertRaisesRegex(ValueError, "inputs.*asset URLs"):
            self.build()

    def test_cli_writes_gallery_and_reports_validation_failure(self):
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
        command = [sys.executable, str(Path(review_gallery.__file__)), "--manifest", str(self.manifest_path), "--output", str(self.output)]
        result = subprocess.run(command, text=True, capture_output=True, cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.output.resolve()))
        self.item["src"] = "missing.png"
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
        original = self.output.read_bytes()
        result = subprocess.run(command, text=True, capture_output=True, cwd=self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("asset does not exist", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
