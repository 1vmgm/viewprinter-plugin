#!/usr/bin/env python3
"""Run with: python3 -m unittest discover -s scripts -p 'test_describe.py'.

Gemini is a local fake server here: no network, no real key, nothing spent."""

import contextlib
import http.server
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

import archive
import describe
import tools

KEY = "test-key-not-real-1234567890"
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360f8cfc0f01f0005fe02fea7d6"
                    "c34b0000000049454e44ae426082")


def reply(description="Image: a red square on white.", tags=("R&B", "Red Square", "red-square", "  "), text="SALE",
          tokens=(1000, 100), model="gemini-test-001"):
    content = json.dumps({"description": description, "tags": list(tags), "on_screen_text": text})
    return {"candidates": [{"content": {"parts": [{"text": content}]}}],
            "usageMetadata": {"promptTokenCount": tokens[0], "candidatesTokenCount": tokens[1]}, "modelVersion": model}


class FakeGemini(http.server.BaseHTTPRequestHandler):
    queue, seen = [], []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8"))
        FakeGemini.seen.append({"path": self.path, "key": self.headers.get("x-goog-api-key"), "body": body})
        status, payload = FakeGemini.queue.pop(0) if FakeGemini.queue else (200, reply())
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class DescribeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeGemini)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = "http://127.0.0.1:{}/v1beta".format(cls.server.server_address[1])

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        FakeGemini.queue[:], FakeGemini.seen[:] = [], []
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name).resolve()
        self.root, self.work = base / "archive", base / "work"
        self.work.mkdir()
        environment = patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        for name in describe.KEY_NAMES + [describe.BASE_ENVIRONMENT, archive.ROOT_ENVIRONMENT]:
            os.environ.pop(name, None)
        state = patch.object(tools, "state_path", return_value=base / "ViewPrinter/tools.json")
        state.start()
        self.addCleanup(state.stop)
        retry = patch.object(describe, "RETRY_SECONDS", 0)
        retry.start()
        self.addCleanup(retry.stop)

    def add(self, name, content=PNG, **record):
        path = self.work / name
        path.write_bytes(content)
        return archive.add(self.root, "brand", path, dict({"origin": "generated", "prompt": "A red square"}, **record),
                           format_id="squares")

    def run_describe(self, chosen=None, cap=1.0, workers=1, key=KEY):
        chosen = describe.select(self.root, "brand")[0] if chosen is None else chosen
        out = io.StringIO()
        totals = describe.run(self.root, "brand", chosen, "gemini-test", 0.5, 2.0, cap, workers, key, self.base, out)
        return totals, out.getvalue()

    def asset(self, identifier):
        return archive.assets(self.root / "brand")[identifier]

    def test_a_summary_its_tags_and_its_receipt_go_into_the_catalog(self):
        added = self.add("square.png", batchId="b1")
        totals, printed = self.run_describe()
        self.assertEqual((totals["described"], totals["failed"]), (1, 0))
        cost = (1000 * 0.5 + 100 * 2.0) / 1e6
        self.assertAlmostEqual(totals["runUsd"], cost)
        self.assertAlmostEqual(totals["allTimeUsd"], cost)
        asset = self.asset(added["id"])
        self.assertEqual(asset["summary"], "Image: a red square on white.")
        self.assertEqual(asset["onScreenText"], "SALE")
        self.assertTrue({"r-and-b", "red-square"} <= set(asset["tags"]))
        self.assertNotIn("", asset["tags"])
        self.assertEqual(asset["summaryBy"]["model"], "gemini-test-001")
        self.assertEqual((asset["summaryBy"]["inputTokens"], asset["summaryBy"]["outputTokens"]), (1000, 100))
        self.assertAlmostEqual(asset["summaryBy"]["costUsd"], cost)
        # The request: the key in a header only, the image inline, the cataloguing rules in the prompt.
        request = FakeGemini.seen[0]
        self.assertEqual((request["path"], request["key"]), ("/v1beta/models/gemini-test:generateContent", KEY))
        parts = request["body"]["contents"][0]["parts"]
        self.assertIn("do not identify anyone from their face", parts[0]["text"])
        self.assertEqual(parts[1]["inlineData"]["mimeType"], "image/png")
        self.assertNotIn(KEY, printed)
        self.assertNotIn(KEY, (self.root / "brand/catalog.jsonl").read_text(encoding="utf-8"))
        # find searches the summary, and upload-list hands it to media_save as the description.
        self.assertEqual([a["id"] for a in archive.find(self.root, ["brand"], text="red square on white")], [added["id"]])
        listed = archive.upload_list(self.root, "brand")["items"][0]
        self.assertEqual(listed["describe"]["description"], "Image: a red square on white.")
        self.assertIn("r-and-b", listed["describe"]["tags"])
        # Described once: it is left out next time unless asked again.
        chosen, skipped = describe.select(self.root, "brand")
        self.assertEqual((chosen, skipped), ([], {"already described (pass --again)": 1}))
        self.assertEqual(len(describe.select(self.root, "brand", again=True)[0]), 1)

    def test_an_unusable_reply_still_counts_as_spent_and_leaves_no_summary(self):
        added = self.add("square.png")
        broken = reply()
        broken["candidates"][0]["content"]["parts"][0]["text"] = "Sorry, I can't help with that."
        FakeGemini.queue[:] = [(200, broken)] * describe.ATTEMPTS
        totals, printed = self.run_describe()
        self.assertEqual((totals["described"], totals["failed"]), (0, 1))
        asset = self.asset(added["id"])
        self.assertNotIn("summary", asset)
        self.assertIn("usable description", asset["summaryBy"]["failed"])
        self.assertEqual(asset["summaryBy"]["replies"], describe.ATTEMPTS)
        self.assertAlmostEqual(asset["summaryBy"]["costUsd"], describe.ATTEMPTS * (1000 * 0.5 + 100 * 2.0) / 1e6)
        self.assertAlmostEqual(totals["allTimeUsd"], asset["summaryBy"]["costUsd"])
        self.assertIn("failed", printed)
        # Still undescribed, so it is offered again.
        self.assertEqual(len(describe.select(self.root, "brand")[0]), 1)

    def test_busy_and_server_errors_are_retried_and_a_fenced_reply_is_read(self):
        added = self.add("square.png")
        fenced = reply()
        text = fenced["candidates"][0]["content"]["parts"][0]["text"]
        fenced["candidates"][0]["content"]["parts"][0]["text"] = "```json\n" + text + "\n```"
        FakeGemini.queue[:] = [(429, {"error": "busy"}), (503, {"error": "down"}), (200, fenced)]
        totals, _ = self.run_describe()
        self.assertEqual(totals["described"], 1)
        self.assertEqual(len(FakeGemini.seen), 3)
        self.assertEqual(self.asset(added["id"])["summaryBy"]["replies"], 1)

    def test_a_refused_request_costs_nothing_and_never_shows_the_key(self):
        added = self.add("square.png")
        FakeGemini.queue[:] = [(400, ("API key " + KEY + " is not valid").encode("utf-8"))]
        totals, printed = self.run_describe()
        self.assertEqual((totals["failed"], totals["runUsd"]), (1, 0.0))
        self.assertIn("HTTP 400", printed)
        self.assertIn("[key]", printed)
        self.assertNotIn(KEY, printed)
        self.assertNotIn("summaryBy", self.asset(added["id"]))  # nothing was paid for, so no receipt

    def test_the_cap_stops_new_requests(self):
        for n in range(3):
            self.add("square-{}.png".format(n), content=PNG + bytes([n]))
        totals, printed = self.run_describe(cap=0.0012, workers=1)  # each reply costs 0.0007
        self.assertEqual((totals["described"], len(FakeGemini.seen)), (3 - 1, 2))
        self.assertEqual(totals["skipped"], {"the spending cap for this run was reached": 1})
        self.assertGreaterEqual(totals["runUsd"], 0.0014)

    def test_video_and_audio_need_ffmpeg_and_nothing_is_sent_without_it(self):
        self.add("take.mp4", content=b"not really a video")
        with patch.object(describe.shutil, "which", return_value=None):
            totals, printed = self.run_describe()
        self.assertEqual(totals["skipped"], {"ffmpeg is needed to make the small copy Gemini gets of video and audio": 1})
        self.assertEqual(FakeGemini.seen, [])

    def test_the_estimate_counts_what_gemini_would_see_before_anything_is_sent(self):
        self.add("square.png")
        self.add("take.mp4", content=b"video one")
        self.add("long.mp4", content=b"video two")
        self.add("loop.wav", content=b"audio")
        durations = {"take.mp4": (30.0, 1080, 1920), "long.mp4": (600.0, 1920, 1080), "loop.wav": (16.0, None, None),
                     "square.png": (None, 1, 1)}
        with patch.object(describe, "probe", side_effect=lambda path: durations[next(
                name for name in durations if path.name.endswith(Path(name).suffix) and (
                    archive.assets(self.root / "brand")[path.stem]["originalName"] == name))]):
            report = describe.estimate(describe.select(self.root, "brand")[0], 0.5, 2.0, "gemini-test")
        self.assertEqual(report["byKind"], {"audio": {"count": 1, "seconds": 16.0}, "image": {"count": 1, "seconds": 0.0},
                                            "video": {"count": 2, "seconds": 150.0}})
        expected_in = 150 * describe.VIDEO_TOKENS + 16 * describe.AUDIO_TOKENS + describe.TILE_TOKENS + 4 * describe.PROMPT_TOKENS
        self.assertEqual((report["inputTokens"], report["outputTokens"]), (expected_in, 4 * describe.REPLY_TOKENS))
        self.assertAlmostEqual(report["estimatedUsd"], round((expected_in * 0.5 + 1600 * 2.0) / 1e6, 4))
        self.assertEqual(FakeGemini.seen, [])

    def test_the_key_comes_from_a_keys_file_the_user_named_and_the_command_line_never_shows_it(self):
        added = self.add("square.png")
        secrets = self.work / "keys.env"
        secrets.write_text('GEMINI_API_KEY="{}"\n'.format(KEY), encoding="utf-8")
        tools.keys("add", secrets, tools.state_path())
        self.assertEqual(describe.gemini_key({}), KEY)
        os.environ[describe.BASE_ENVIRONMENT] = self.base
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = describe.main(["run", "--root", str(self.root), "--project", "brand", "--model", "gemini-test",
                                  "--price-in", "0.5", "--price-out", "2", "--cap", "1"])
        self.assertEqual(code, 0)
        self.assertEqual(FakeGemini.seen[0]["key"], KEY)
        self.assertNotIn(KEY, output.getvalue() + errors.getvalue())
        self.assertEqual(json.loads(output.getvalue()[output.getvalue().index("{"):])["described"], 1)
        self.assertEqual(self.asset(added["id"])["summary"], "Image: a red square on white.")
        tools.keys("remove", secrets, tools.state_path())
        with self.assertRaises(describe.DescribeError):
            describe.gemini_key({}, cwd=self.work)

    def test_originals_kept_elsewhere_or_named_are_chosen_as_asked(self):
        first = self.add("square.png")
        second = self.add("other.png", content=PNG + b"2")
        stored = {"media": [{"id": "media-1", "sha256": first["sha256"], "purpose": "source"}]}
        archive.stored(self.root, "brand", stored)
        self.assertEqual([a["id"] for a, _ in describe.select(self.root, "brand")[0]], [second["id"]])
        self.assertEqual(len(describe.select(self.root, "brand", stored=True)[0]), 2)
        self.assertEqual([a["id"] for a, _ in describe.select(self.root, "brand", ids=[first["id"]])[0]], [first["id"]])
        self.assertEqual(describe.select(self.root, "brand", ids=["nope"])[1], {"no such original": 1})

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg")
    def test_the_small_copies_are_made_with_ffmpeg(self):
        video = self.work / "clip.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=10:duration=1",
                        "-f", "lavfi", "-i", "sine=duration=1", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        str(video)], check=True)
        with tempfile.TemporaryDirectory() as folder:
            data, mime = describe.proxy({"kind": "video"}, video, folder)
            copy = Path(folder) / "copy.mp4"
            self.assertEqual(mime, "video/mp4")
            self.assertEqual(describe.probe(copy)[1:], (540, 960))
        self.assertGreater(len(data), 0)
        seconds, width, height = describe.probe(video)
        self.assertEqual((width, height), (1080, 1920))
        self.assertEqual(describe.opening({"kind": "video"}, seconds, width, height), '"Video, 1 s, vertical: ..."')


if __name__ == "__main__":
    unittest.main()
