"""Run: python -m unittest discover -s scripts -p 'test_review_media.py'."""

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from review_gallery import build_gallery
import review_media as media
import review_workspace as ws

archive = media.archive_module()
import memory  # noqa: E402  the content-production skill's, on the path the archive added


class ReviewMediaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.project = self.base / "brand"
        self.project.mkdir()
        self.env = patch.dict(os.environ, VIEWPRINTER_REVIEW_ROOT=str(self.base / "hub"), VIEWPRINTER_REVIEW_HUB="0",
                              VIEWPRINTER_ARCHIVE_ROOT=str(self.base / "archive"))
        self.env.start()
        self.addCleanup(self.env.stop)
        os.environ.pop("VIEWPRINTER_CONTENT_MEMORY", None)
        memory.initialize(self.project, "Brand")
        config = self.project / ".viewprinter/content-memory/config.json"
        ws.atomic(config, dict(ws.read(config), archive={"project": "brand"}))
        self.served = {}
        self.link = self.serve()
        self.batch = self.project / "batch"
        self.batch.mkdir()
        self.content = {"final.mp4": b"final cut", "cover.png": b"cover", "draft.mp4": b"first draft",
                        "still.png": b"generated still", "music.wav": b"shared music", "other.png": b"in review"}
        for name, content in self.content.items():
            (self.batch / name).write_bytes(content)
        finished = {"id": "A", "version": 2, "title": "Finished", "format": "Demo", "kind": "video", "status": "approved",
                    "stage": "final", "src": "final.mp4", "poster": "cover.png", "batch": "b1",
                    "previous": {"version": 1, "kind": "video", "src": "draft.mp4"},
                    "inputs": [{"label": "Opening still", "kind": "image", "src": "still.png"},
                               {"label": "Music", "kind": "audio", "src": "music.wav"}],
                    "generation": [{"asset": "Opening still", "platform": "example-provider", "model": "image-1",
                                    "jobId": "job-1", "prompt": "A still of a kitchen",
                                    "cost": {"status": "reported", "amount": 0.04, "unit": "USD"}}],
                    "captionStatus": "approved", "captions": {"instagram": {"caption": "Hi"}},
                    "distribution": {"targets": [{"organizationId": "o", "accountId": "a", "platform": "instagram"}]}}
        active = {"id": "B", "version": 1, "title": "In review", "format": "Demo", "kind": "image", "status": "needs-review",
                  "src": "other.png", "batch": "b1", "inputs": [{"label": "Music", "kind": "audio", "src": "music.wav"}]}
        ws.atomic(self.batch / "review.json", {
            "title": "Demo", "round": 1, "batches": [{"id": "b1", "label": "Batch one"}],
            "reviewHub": {"kind": "social-content", "formatId": "demo", "owner": "test"},
            "delivery": {"snapshot": "delivery.json"}, "items": [finished, active]})
        ws.atomic(self.batch / "delivery.json", {"placements": [{
            "itemId": "A", "version": 2, "postId": "p", "accountId": "a", "organizationId": "o", "platform": "instagram",
            "caption": "Hi", "status": "scheduled", "checkedAt": "2026-10-06T12:00:00Z"}]})
        build_gallery(self.batch / "review.json", self.batch / "review.html")
        self.entry = ws.register(self.batch)

    def serve(self):
        """A stand-in for ViewPrinter's media links."""
        served = self.served

        class Media(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                body = served.get(self.path)
                self.send_response(200 if body is not None else 404)
                self.send_header("Content-Length", str(len(body or b"")))
                self.end_headers()
                self.wfile.write(body or b"")

        server = ThreadingHTTPServer(("127.0.0.1", 0), Media)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return "http://127.0.0.1:{}".format(server.server_address[1])

    def sha(self, name):
        return hashlib.sha256(self.content[name]).hexdigest()

    def kept(self, name):
        return self.project / ".viewprinter/content-memory/reviews/.media" / self.sha(name) / name

    def listing(self, library=()):
        """ViewPrinter's media_list answer for what the archive holds, as source material, and these as library files."""
        rows = []
        for asset in archive.assets(self.base / "archive" / "brand").values():
            path = "/media/m-" + asset["sha256"][:8]
            self.served[path] = Path(asset["file"] if "file" in asset else self.base / "archive/brand" / asset["path"]).read_bytes()
            rows.append({"id": "m-" + asset["sha256"][:8], "sha256": asset["sha256"], "purpose": "source",
                         "url": self.link + path})
        rows += [{"id": "m-lib", "sha256": self.sha(name), "purpose": "library", "url": self.link + "/media/m-lib"} for name in library]
        return {"media": rows, "nextCursor": None}

    def shown(self):
        return ws.read(ws.get(self.entry)["manifest"])["items"]

    def test_finished_work_goes_to_viewprinter_and_comes_back_exactly(self):
        status = media.status(self.project)
        self.assertEqual((status["finishedWork"]["files"], status["activeWork"]["files"], status["released"]["files"]), (4, 2, 0))
        self.assertEqual(status["viewprinterKeeps"], "archive catalog")
        self.assertEqual(media.save(self.project, dry_run=True)["wouldAdd"], 4)
        self.assertEqual(archive.projects_in(self.base / "archive"), [])  # a dry run adds nothing
        saved = media.save(self.project)
        self.assertEqual((saved["added"], saved["byKind"], saved["skipped"]["activeWork"]), (4, {"video": 2, "image": 2, "audio": 0}, 2))
        assets = {a["sha256"]: a for a in archive.assets(self.base / "archive" / "brand").values()}
        final, still, draft = assets[self.sha("final.mp4")], assets[self.sha("still.png")], assets[self.sha("draft.mp4")]
        self.assertEqual((final["format"], final["itemId"], final["status"], final["origin"], final["batchId"]),
                         ("demo", "A/v2", "selected", "edited", "b1"))
        self.assertEqual(final["usedIn"], [{"review": self.entry, "format": "demo", "batch": "b1", "item": "A", "version": 2, "role": "final"}])
        self.assertEqual((still["tool"], still["model"], still["requestId"], still["cost"]),
                         ("example-provider", "image-1", "job-1", {"basis": "reported", "amount": 0.04, "unit": "usd"}))
        self.assertEqual((draft["status"], draft["tags"]), ("candidate", ["review-media", "review-previous"]))
        self.assertNotIn("origin", still)
        self.assertEqual(media.save(self.project)["skipped"]["alreadyArchived"], 4)  # nothing is added twice
        # The archive's upload flow offers them as source material.
        offered = archive.upload_list(self.base / "archive", "brand")["items"]
        self.assertEqual({i["upload"]["sha256"] for i in offered}, set(assets))
        self.assertIn("review-final", next(i for i in offered if i["upload"]["sha256"] == self.sha("final.mp4"))["describe"]["tags"])

        listed = self.listing(library=["music.wav", "other.png"])
        status = media.status(self.project, listed)
        self.assertEqual((status["finishedWork"]["keptInViewPrinter"]["files"], status["releaseNow"]["files"]), (4, 4))
        with self.assertRaisesRegex(media.MediaError, "approval"):
            media.release(self.project, listed)
        dry = media.release(self.project, listed, dry_run=True)
        self.assertEqual((dry["wouldRelease"], dry["skipped"]), (4, {"work still in review": 2}))
        self.assertTrue(self.kept("final.mp4").is_file())
        released = media.release(self.project, listed, "yes, let the local copies go")
        self.assertEqual((released["released"], released["reviewsUpdated"]), (4, [self.entry]))
        for name in ("final.mp4", "cover.png", "draft.mp4", "still.png"):
            self.assertFalse(self.kept(name).exists(), name)
            note = json.loads((self.kept(name).parent / "kept.json").read_text(encoding="utf-8"))
            self.assertEqual((note["name"], note["purpose"], note["approval"]), (name, "source", "yes, let the local copies go"))
        for name in ("music.wav", "other.png"):  # library rows never count, and work in review stays here
            self.assertTrue(self.kept(name).is_file(), name)
        item = next(i for i in self.shown() if i["id"] == "A")
        self.assertEqual([bool(m.get("keptInViewPrinter")) for m in (item, item["previous"], *item["inputs"])], [True, True, True, False])
        self.assertIn("Kept in ViewPrinter", Path(ws.get(self.entry)["gallery"]).read_text(encoding="utf-8"))
        self.assertEqual(media.status(self.project, listed)["released"]["files"], 4)

        restored = media.restore(self.project, item="A", version=2)
        self.assertEqual((len(restored["restored"]), restored["skipped"]), (4, {"not let go": 1}))
        for name in ("final.mp4", "cover.png", "draft.mp4", "still.png"):
            self.assertEqual(self.kept(name).read_bytes(), self.content[name])
            self.assertFalse((self.kept(name).parent / "kept.json").exists())
        item = next(i for i in self.shown() if i["id"] == "A")
        self.assertFalse(any(m.get("keptInViewPrinter") for m in (item, item["previous"], *item["inputs"])))

    def test_restore_takes_only_the_same_bytes(self):
        media.save(self.project)
        listed = self.listing()
        media.release(self.project, listed, "yes")
        url = json.loads((self.kept("final.mp4").parent / "kept.json").read_text(encoding="utf-8"))["url"]
        self.served[url[len(self.link):]] = b"something else"
        with self.assertRaisesRegex(media.MediaError, "didn't match"):
            media.restore(self.project, sha=self.sha("final.mp4"))
        self.assertFalse(self.kept("final.mp4").exists())
        self.assertTrue((self.kept("final.mp4").parent / "kept.json").exists())
        self.assertEqual([p.name for p in self.kept("final.mp4").parent.iterdir()], ["kept.json"])  # no partial download left

    def test_save_never_adds_what_another_archive_project_holds(self):
        archive.add(self.base / "archive", "shared", self.batch / "still.png", {})
        saved = media.save(self.project)
        self.assertEqual((saved["added"], saved["skipped"]["alreadyArchived"]), (3, 1))

    def test_a_file_changed_since_it_was_kept_is_not_let_go(self):
        media.save(self.project)
        listed = self.listing()
        path = self.kept("cover.png")
        path.chmod(0o644)
        path.write_bytes(b"edited by hand")
        released = media.release(self.project, listed, "yes")
        self.assertEqual((released["released"], released["skipped"]["changed since it was kept"]), (3, 1))
        self.assertEqual(path.read_bytes(), b"edited by hand")

    def second_review(self):
        """A finished item with a final, its cover, an earlier version, a raw take and a preview of the final."""
        second = self.project / "second"
        second.mkdir()
        content = {"cut.mp4": b"second cut", "poster.png": b"poster", "rough.mp4": b"rough cut",
                   "take.mp4": b"raw take", "frames.png": b"frames of the cut"}
        for name, data in content.items():
            (second / name).write_bytes(data)
        item = {"id": "C", "version": 2, "title": "Done", "format": "Demo", "kind": "video", "status": "approved",
                "stage": "final", "src": "cut.mp4", "poster": "poster.png", "batch": "b2",
                "previous": {"version": 1, "kind": "video", "src": "rough.mp4"},
                "inputs": [{"label": "Raw take", "kind": "video", "src": "take.mp4"},
                           {"label": "Final frames · v2", "kind": "image", "src": "frames.png"}],
                "captionStatus": "approved", "captions": {"instagram": {"caption": "Hi"}},
                "distribution": {"targets": [{"organizationId": "o", "accountId": "a", "platform": "instagram"}]}}
        ws.atomic(second / "review.json", {
            "title": "Second", "round": 1, "batches": [{"id": "b2", "label": "Two"}],
            "reviewHub": {"kind": "social-content", "formatId": "second", "owner": "test"},
            "delivery": {"snapshot": "delivery.json"}, "items": [item]})
        ws.atomic(second / "delivery.json", {"placements": [{
            "itemId": "C", "version": 2, "postId": "p2", "accountId": "a", "organizationId": "o", "platform": "instagram",
            "caption": "Hi", "status": "scheduled", "checkedAt": "2026-10-06T12:00:00Z"}]})
        build_gallery(second / "review.json", second / "review.html")
        return second, ws.register(second)

    def test_a_project_drops_what_it_keeps_no_copy_of_and_cleans_its_batch_files(self):
        second, entry = self.second_review()
        with self.assertRaisesRegex(media.MediaError, "dropWhenFinished"):
            media.drop(self.project, "yes")
        self.assertEqual(media.status(self.project)["dropNow"]["files"], 0)  # without a policy nothing drops
        config = self.project / ".viewprinter/content-memory/config.json"
        ws.atomic(config, dict(ws.read(config), reviewMedia={"dropWhenFinished": ["previous", "cover", "preview"]}))
        status = media.status(self.project)
        self.assertEqual((status["dropPolicy"], status["dropNow"]["files"]), (["cover", "preview", "previous"], 5))
        saved = media.save(self.project)  # only what the project keeps goes to ViewPrinter
        self.assertEqual((saved["added"], saved["skipped"]["dropped"]), (4, 5))
        archived = {a["sha256"] for a in archive.assets(self.base / "archive" / "brand").values()}
        self.assertEqual(archived, {hashlib.sha256(b).hexdigest()
                                    for b in (b"final cut", b"generated still", b"second cut", b"raw take")})
        with self.assertRaisesRegex(media.MediaError, "approval"):
            media.drop(self.project)
        self.assertEqual(media.drop(self.project, dry_run=True)["wouldDrop"], 5)
        dropped = media.drop(self.project, "we dont keep covers or old versions")
        self.assertEqual((dropped["dropped"], dropped["skipped"]), (5, {}))
        self.assertEqual(sorted(dropped["reviewsUpdated"]), sorted([self.entry, entry]))
        store = self.project / ".viewprinter/content-memory/reviews/.media"
        poster = store / hashlib.sha256(b"poster").hexdigest() / "poster.png"
        self.assertFalse(poster.exists())
        note = json.loads((poster.parent / "dropped.json").read_text(encoding="utf-8"))
        self.assertEqual((note["reason"], note["approval"]), ("cover", "we dont keep covers or old versions"))
        self.assertIn("Removed after review", Path(ws.get(entry)["gallery"]).read_text(encoding="utf-8"))
        self.assertEqual(media.status(self.project)["dropped"]["files"], 5)
        restored = media.restore(self.project, item="C", version=2)
        self.assertEqual(restored["skipped"]["dropped after review; no copy kept"], 3)

        with self.assertRaisesRegex(media.MediaError, "approval"):
            media.clean_sources(self.project)
        self.assertEqual(media.clean_sources(self.project, dry_run=True)["wouldDelete"], 9)
        cleaned = media.clean_sources(self.project, "yes, delete the batch copies")
        self.assertEqual(cleaned["deleted"], 9)
        for name in ("cut.mp4", "poster.png", "rough.mp4", "take.mp4", "frames.png"):
            self.assertFalse((second / name).exists(), name)
        for name in ("final.mp4", "cover.png", "draft.mp4", "still.png"):
            self.assertFalse((self.batch / name).exists(), name)
        for name in ("music.wav", "other.png"):  # work still in review keeps its files
            self.assertTrue((self.batch / name).is_file(), name)
        # Both reviews still build from their source manifests once the batch files are gone.
        build_gallery(second / "review.json", second / "review.html")
        built = (second / "review.html").read_text(encoding="utf-8")
        self.assertIn("Removed after review", built)
        self.assertIn(hashlib.sha256(b"second cut").hexdigest(), built)  # the final plays from the workspace's copy
        build_gallery(self.batch / "review.json", self.batch / "review.html")

    def test_a_rebuild_without_its_batch_file_shows_the_copy_its_own_review_accepted(self):
        import review_gallery
        manifest, raw = self.batch / "review.json", (self.batch / "final.mp4").as_posix()
        store = self.project / ".viewprinter/content-memory/reviews/.media"
        older = hashlib.sha256(b"older cut").hexdigest()
        (store / older).mkdir()
        (store / older / "final.mp4").write_bytes(b"older cut")
        # An archived snapshot of an earlier round accepted other bytes at the same batch path,
        # listed before the live review.
        ws.atomic(ws.registry() / "0-snapshot.json", {
            "id": "snapshot", "lifecycle": "archived", "projectRoot": str(self.project),
            "sources": [{"manifest": str(manifest), "frozenMedia": {raw: older + "/final.mp4"}}]})
        (self.batch / "final.mp4").unlink()
        build_gallery(manifest, self.batch / "review.html")
        page = (self.batch / "review.html").read_text(encoding="utf-8")
        self.assertIn(self.sha("final.mp4"), page)
        self.assertNotIn(older, page)
        review_gallery._registered = None  # built for no registered review, the two copies disagree: no guess
        self.assertIsNone(review_gallery.registered_copy(raw))

    def test_one_set_of_bytes_under_two_names_is_let_go_and_restored_under_both(self):
        third = self.project / "third"
        third.mkdir()
        for name in ("a.mp4", "b.mp4"):
            (third / name).write_bytes(b"same cut")
        target = {"targets": [{"organizationId": "o", "accountId": "a", "platform": "instagram"}]}
        items = [{"id": ident, "version": 1, "title": ident, "format": "Demo", "kind": "video", "status": "approved",
                  "stage": "final", "src": name, "batch": "b3", "captionStatus": "approved",
                  "captions": {"instagram": {"caption": "Hi"}}, "distribution": target}
                 for ident, name in (("D", "a.mp4"), ("E", "b.mp4"))]
        ws.atomic(third / "review.json", {
            "title": "Third", "round": 1, "batches": [{"id": "b3", "label": "Three"}],
            "reviewHub": {"kind": "social-content", "formatId": "third", "owner": "test"},
            "delivery": {"snapshot": "delivery.json"}, "items": items})
        ws.atomic(third / "delivery.json", {"placements": [{
            "itemId": ident, "version": 1, "postId": "p-" + ident, "accountId": "a", "organizationId": "o",
            "platform": "instagram", "caption": "Hi", "status": "scheduled", "checkedAt": "2026-10-06T12:00:00Z"}
            for ident in ("D", "E")]})
        build_gallery(third / "review.json", third / "review.html")
        ws.register(third)
        media.save(self.project)
        media.release(self.project, self.listing(), "yes")
        sha = hashlib.sha256(b"same cut").hexdigest()
        folder = self.project / ".viewprinter/content-memory/reviews/.media" / sha
        note = json.loads((folder / "kept.json").read_text(encoding="utf-8"))
        self.assertEqual(note["names"], ["a.mp4", "b.mp4"])
        self.assertFalse((folder / "a.mp4").exists() or (folder / "b.mp4").exists())
        for name in ("a.mp4", "b.mp4"):
            (third / name).unlink()  # cleaned up: both names still resolve to ViewPrinter's copy
        build_gallery(third / "review.json", third / "review.html")
        media.restore(self.project, sha=sha)
        self.assertEqual([(folder / n).read_bytes() for n in ("a.mp4", "b.mp4")], [b"same cut", b"same cut"])

    def test_command_line(self):
        result = subprocess.run([sys.executable, str(Path(media.__file__)), "status", "--project", str(self.project)],
                                capture_output=True, text=True, timeout=60, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["finishedWork"]["files"], 4)
        result = subprocess.run([sys.executable, str(Path(media.__file__)), "release", "--project", str(self.project),
                                 "--listed", "-"], input=json.dumps(self.listing()), capture_output=True, text=True,
                                timeout=60, encoding="utf-8")
        self.assertEqual(result.returncode, 1)
        self.assertIn("approval", result.stderr)


if __name__ == "__main__":
    unittest.main()
