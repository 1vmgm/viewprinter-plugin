#!/usr/bin/env python3
"""Run with: python3 -m unittest discover -s scripts -p 'test_archive.py'."""

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import archive
import memory


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name).resolve()
        self.root = base / "archive"
        self.work = base / "work"
        self.work.mkdir()
        self.environment = patch.dict(os.environ)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        for name in (archive.ROOT_ENVIRONMENT, "VIEWPRINTER_CONTENT_MEMORY"):
            os.environ.pop(name, None)

    def original(self, name="take.mp4", content=b"take one"):
        path = self.work / name
        path.write_bytes(content)
        return path

    def provenance(self, **extra):
        return {"origin": "generated", "tool": "example-provider", "model": "example-video-1",
                "requestId": "req-1", "prompt": "A man laughs on a couch, phone in his right hand",
                "cost": {"amount": 4.55, "unit": "usd", "basis": "estimate"}, **extra}

    def cli(self, *arguments, stdin=None, cwd=None):
        return subprocess.run([sys.executable, str(Path(archive.__file__).resolve()), *map(str, arguments)],
                              input=stdin, capture_output=True, text=True, check=False, cwd=cwd or self.work)

    def problems(self, **options):
        return sorted(p["problem"].split(";")[0] for p in archive.verify(self.root, "brand", **options)["problems"])

    # -- adding ------------------------------------------------------------------

    def test_an_original_is_stored_once_under_its_format_with_one_catalog_line(self):
        source = self.original()
        added = archive.add(self.root, "brand", source, self.provenance(), format_id="street-interview")
        stored = self.root / "brand" / "street-interview" / "video" / (added["id"] + ".mp4")
        self.assertEqual(Path(added["file"]), stored)
        self.assertEqual(stored.read_bytes(), b"take one")
        self.assertTrue(source.exists())
        self.assertTrue(added["id"].startswith("video-"))
        self.assertEqual((added["status"], added["model"]), ("candidate", "example-video-1"))
        again = archive.add(self.root, "brand", self.original("renamed.mp4"), {"prompt": "other words"})
        self.assertTrue(again["duplicate"])
        self.assertEqual(again["id"], added["id"])
        self.assertEqual(len(archive.read_log(self.root / "brand" / "catalog.jsonl")), 1)
        self.assertEqual(sorted(p.name for p in (self.root / "brand").iterdir()), ["catalog.jsonl", "street-interview"])

    def test_an_id_names_one_content_and_ids_stay_inside_the_archive(self):
        archive.add(self.root, "brand", self.original(), identifier="kitchen-01")
        with self.assertRaises(archive.ArchiveError):
            archive.add(self.root, "brand", self.original("other.mp4", b"take two"), identifier="kitchen-01")
        for bad in ("../escape", "a/b"):
            with self.assertRaises(archive.ArchiveError):
                archive.add(self.root, "brand", self.original("x.mp4", bad.encode()), identifier=bad)
            with self.assertRaises(archive.ArchiveError):
                archive.add(self.root, "brand", self.original("x.mp4", bad.encode()), format_id=bad)
            with self.assertRaises(archive.ArchiveError):
                archive.add(self.root, bad, self.original("x.mp4", bad.encode()))

    def test_records_are_checked_before_anything_is_stored(self):
        for bad in ({"status": "approved"}, {"tags": "kitchen"}, {"rights": {"allowedUses": "paid"}},
                    {"cost": {"amount": 1, "basis": "guess"}}, {"sha256": "0" * 64}, {"noteCount": 2},
                    {"file": "/elsewhere.mp4"}, {"identity": ["cast-a", 7]}, [1]):
            with self.assertRaises(archive.ArchiveError):
                archive.add(self.root, "brand", self.original(), bad)
        self.assertFalse((self.root / "brand").exists())

    def test_a_notes_field_is_ordinary_text_and_the_catalog_stays_readable(self):
        added = archive.add(self.root, "brand", self.original(), {"notes": "phantom hand at 2 s"})
        archive.note(self.root, "brand", added["id"], {"notes": "fixed in the next take", "status": "rejected"})
        archive.note(self.root, "brand", added["id"], {"tags": ["hands"]})
        shown = archive.show(self.root, "brand", added["id"])
        self.assertEqual((shown["notes"], shown["noteCount"], shown["status"]),
                         ("fixed in the next take", 2, "rejected"))
        self.assertEqual(len(archive.find(self.root, ["brand"], tags=["hands"])), 1)

    def test_move_renames_the_file_in_and_a_duplicate_leaves_the_source_alone(self):
        source = self.original()
        added = archive.add(self.root, "brand", source, move=True)
        self.assertFalse(source.exists())
        self.assertEqual(Path(added["file"]).read_bytes(), b"take one")
        duplicate = self.original("copy.mp4")
        self.assertTrue(archive.add(self.root, "brand", duplicate, move=True)["duplicate"])
        self.assertTrue(duplicate.exists())
        self.assertEqual(sorted(p.name for p in (self.root / "brand").iterdir()), ["catalog.jsonl", "unfiled"])

    def test_cataloguing_an_original_already_in_place_never_deletes_it(self):
        archive.add(self.root, "brand", self.original(), format_id="f")
        stray = self.root / "brand" / "f" / "video" / "stray.mp4"
        stray.write_bytes(b"found in place")
        self.assertEqual(self.problems(), ["not in catalog"])
        added = archive.add(self.root, "brand", stray, identifier="stray", format_id="f", move=True)
        self.assertEqual(Path(added["file"]), stray)
        self.assertEqual(stray.read_bytes(), b"found in place")
        self.assertEqual(self.problems(rehash=True), [])

    def test_an_interrupted_copy_leaves_the_source_alone_and_nothing_half_added(self):
        source = self.original()

        def interrupted(src, dst):
            Path(dst).write_bytes(b"half")
            raise KeyboardInterrupt
        with patch.object(archive, "clone", interrupted):
            with self.assertRaises(KeyboardInterrupt):
                archive.add(self.root, "brand", source)
        self.assertEqual(source.read_bytes(), b"take one")
        self.assertEqual(sorted(p.name for p in (self.root / "brand").iterdir()), [])
        leftover = self.root / "brand" / (archive.INCOMING + "deadbeef-take.mp4")
        leftover.write_bytes(b"half")  # as a power cut would leave it
        self.assertEqual(self.problems(), ["unfinished copy"])
        with self.assertRaises(archive.ArchiveError):
            archive.add(self.root, "brand", leftover)
        archive.add(self.root, "brand", source)
        self.assertTrue(leftover.exists())  # another writer's file is never deleted

    def test_moving_a_link_archives_the_content_and_removes_only_the_link(self):
        target = self.original("download.mp4")
        link = self.work / "link.mp4"
        link.symlink_to(target)
        added = archive.add(self.root, "brand", link, move=True)
        stored = Path(added["file"])
        self.assertFalse(stored.is_symlink())
        self.assertEqual(stored.read_bytes(), b"take one")
        self.assertFalse(link.exists() or link.is_symlink())
        self.assertTrue(target.exists())
        other_name = self.original("shared.mp4", b"take two")
        hard = self.work / "hard.mp4"
        os.link(other_name, hard)
        stored = Path(archive.add(self.root, "brand", hard, move=True)["file"])
        self.assertNotEqual(os.stat(stored).st_ino, os.stat(other_name).st_ino)
        self.assertEqual(self.problems(rehash=True), [])

    def test_a_file_still_being_written_is_put_back_instead_of_archived(self):
        source = self.original()
        real_locked = archive.locked

        @contextlib.contextmanager
        def writer_finishes(directory):
            with source.open("ab") as stream:
                stream.write(b" and the rest")
            with real_locked(directory):
                yield
        with patch.object(archive, "locked", writer_finishes):
            with self.assertRaises(archive.ArchiveError):
                archive.add(self.root, "brand", source, move=True)
        self.assertEqual(source.read_bytes(), b"take one and the rest")
        self.assertEqual(archive.assets(self.root / "brand"), {})

    def test_an_original_shared_with_another_path_gets_its_own_copy(self):
        archive.add(self.root, "brand", self.original(), format_id="f")
        in_place = self.root / "brand" / "f" / "video" / "Clip.mp4"
        in_place.write_bytes(b"cut for the batch")
        batch_copy = self.work / "batch.mp4"
        os.link(in_place, batch_copy)
        archive.add(self.root, "brand", in_place, identifier="Clip", format_id="f")
        batch_copy.write_bytes(b"edited in the batch")
        self.assertEqual(in_place.read_bytes(), b"cut for the batch")
        self.assertEqual(self.problems(rehash=True), [])
        os.link(in_place, self.work / "another-name.mp4")
        self.assertEqual(self.problems(), ["shares its data with another path"])

    def test_a_refused_restore_leaves_the_old_file_where_it_was(self):
        added = archive.add(self.root, "brand", self.original(), format_id="f")
        stored = Path(added["file"])
        stored.write_bytes(b"wrong size")
        source = self.original("again.mp4")
        real_locked = archive.locked

        @contextlib.contextmanager
        def writer_finishes(directory):
            with real_locked(directory):
                with source.open("ab") as stream:
                    stream.write(b" and more")
                yield
        with patch.object(archive, "locked", writer_finishes):
            with self.assertRaises(archive.ArchiveError):
                archive.add(self.root, "brand", source, move=True)
        self.assertEqual(stored.read_bytes(), b"wrong size")
        self.assertEqual(source.read_bytes(), b"take one and more")
        self.assertEqual(sorted(p.name for p in stored.parent.iterdir()), [stored.name])

    def test_ids_and_formats_that_differ_only_in_case_are_refused(self):
        archive.add(self.root, "brand", self.original(), identifier="kitchen-01", format_id="street-interview")
        with self.assertRaises(archive.ArchiveError):
            archive.add(self.root, "brand", self.original("b.mp4", b"b"), identifier="Kitchen-01")
        with self.assertRaises(archive.ArchiveError):
            archive.add(self.root, "brand", self.original("c.mp4", b"c"), format_id="Street-Interview")
        leftover = self.root / "brand" / "street-interview" / "video" / (archive.MOVING + "abc.mp4")
        leftover.write_bytes(b"moved in")
        self.assertEqual(self.problems(), ["an original moved in by an interrupted restore"])

    def test_a_long_file_name_can_be_copied_in(self):
        added = archive.add(self.root, "brand", self.original("x" * 226 + ".mp4"))
        self.assertEqual(Path(added["file"]).read_bytes(), b"take one")

    def test_a_record_without_a_size_is_judged_by_its_hash(self):
        added = archive.add(self.root, "brand", self.original(), format_id="f")
        catalog = self.root / "brand" / "catalog.jsonl"
        event = archive.read_log(catalog)[0]
        del event["bytes"]  # as a hand-written line might be
        catalog.write_bytes(archive.log_line(event))
        again = archive.add(self.root, "brand", self.original("same.mp4"))
        self.assertTrue(again["duplicate"])
        self.assertNotIn("restored", again)
        self.assertEqual(list(Path(added["file"]).parent.glob("*.changed-*")), [])

    def test_an_original_named_in_another_case_takes_the_recorded_name(self):
        probe = self.work / "Case"
        probe.write_bytes(b"")
        if not (self.work / "case").exists():
            self.skipTest("this disk is case-sensitive")
        archive.add(self.root, "brand", self.original(), format_id="f")
        found = self.root / "brand" / "f" / "video" / "Clip.MP4"
        found.write_bytes(b"found in place")
        archive.add(self.root, "brand", found, identifier="Clip", format_id="f")
        self.assertIn("Clip.mp4", os.listdir(found.parent))
        self.assertEqual(self.problems(rehash=True), [])

    def test_adding_the_same_content_restores_a_missing_or_changed_original(self):
        added = archive.add(self.root, "brand", self.original(), format_id="f")
        stored = Path(added["file"])
        stored.unlink()
        self.assertEqual(self.problems(), ["missing"])
        again = archive.add(self.root, "brand", self.original("found-again.mp4"))
        self.assertTrue(again["duplicate"] and again["restored"])
        self.assertEqual(stored.read_bytes(), b"take one")
        stored.write_bytes(b"edited, wrongly")
        self.assertTrue(archive.add(self.root, "brand", self.original("third.mp4"), move=True)["restored"])
        self.assertEqual(stored.read_bytes(), b"take one")
        [aside] = stored.parent.glob(stored.name + ".changed-*")
        self.assertEqual(aside.read_bytes(), b"edited, wrongly")
        self.assertIsNotNone(archive.show(self.root, "brand", added["id"])["restoredAt"])

    # -- notes, search and reuse -----------------------------------------------------

    def test_notes_add_status_tags_and_usage_without_rewriting_history(self):
        added = archive.add(self.root, "brand", self.original(), self.provenance(tags=["kitchen"]))
        archive.note(self.root, "brand", added["id"], {"status": "rejected", "reason": "a third hand at 2.1 s",
                                                       "tags": ["night"]})
        archive.note(self.root, "brand", added["id"], {"usedIn": [{"batchId": "b1", "itemId": "M01", "version": 3}]})
        shown = archive.show(self.root, "brand", added["id"])
        self.assertEqual((shown["status"], shown["reason"]), ("rejected", "a third hand at 2.1 s"))
        self.assertEqual(shown["tags"], ["kitchen", "night"])
        self.assertEqual(len(shown["events"]), 3)
        for bad in ({"sha256": "0" * 64}, {"format": "elsewhere"}, {"status": "approved"}, {"updatedAt": "x"}, {}):
            with self.assertRaises(archive.ArchiveError):
                archive.note(self.root, "brand", added["id"], bad)
        with self.assertRaises(archive.ArchiveError):
            archive.note(self.root, "brand", "missing", {"status": "selected"})
        first = archive.read_log(self.root / "brand" / "catalog.jsonl")[0]
        self.assertEqual((first["event"], first["status"]), ("add", "candidate"))

    def test_find_filters_by_kind_format_status_identity_text_and_allowed_use(self):
        a = archive.add(self.root, "brand", self.original("a.mp4", b"a"),
                        self.provenance(tags=["kitchen"], identity="cast-a"), format_id="street-interview")
        b = archive.add(self.root, "brand", self.original("b.png", b"b"),
                        {"rights": {"source": "made here", "allowedUses": ["organic", "paid"]}},
                        format_id="product-demo")
        c = archive.add(self.root, "shared", self.original("c.wav", b"c"),
                        {"rights": {"source": "a scraped sound", "allowedUses": ["organic"]}})
        archive.note(self.root, "brand", a["id"], {"status": "selected"})

        def ids(found):
            return sorted(asset["id"] for asset in found)
        self.assertEqual(ids(archive.find(self.root, ["brand"], kind="video")), [a["id"]])
        self.assertEqual(ids(archive.find(self.root, ["brand"], format_id="product-demo")), [b["id"]])
        self.assertEqual(ids(archive.find(self.root, ["brand"], status="selected")), [a["id"]])
        self.assertEqual(ids(archive.find(self.root, ["brand"], tags=["kitchen"], identity="cast-a")), [a["id"]])
        self.assertEqual(ids(archive.find(self.root, ["brand"], text="RIGHT HAND")), [a["id"]])
        self.assertEqual(archive.projects_in(self.root), ["brand", "shared"])
        self.assertEqual(ids(archive.find(self.root, archive.projects_in(self.root), allowed_use="paid")), [b["id"]])
        self.assertEqual((c["kind"], c["format"]), ("audio", archive.UNFILED))

    def test_checkout_gives_a_batch_its_own_copy_and_records_the_use(self):
        added = archive.add(self.root, "brand", self.original(), format_id="street-interview")
        batch = self.work / "batch" / "Sources"
        use = {"batchId": "b1", "itemId": "M01", "version": 1}
        copy = archive.checkout(self.root, "brand", added["id"], str(batch) + "/", use)
        self.assertEqual((copy.parent, copy.read_bytes()), (batch, b"take one"))
        self.assertEqual(archive.checkout(self.root, "brand", added["id"], copy), copy)
        copy.write_bytes(b"edited")
        with self.assertRaises(archive.ArchiveError):
            archive.checkout(self.root, "brand", added["id"], copy)
        with self.assertRaises(archive.ArchiveError):
            archive.checkout(self.root, "brand", added["id"], self.root / "brand" / "edit-here.mp4")
        with self.assertRaises(archive.ArchiveError):
            archive.checkout(self.root, "brand", added["id"], str(self.root / "brand" / "new-folder") + "/")
        self.assertFalse((self.root / "brand" / "new-folder").exists())
        self.assertEqual(Path(added["file"]).read_bytes(), b"take one")
        self.assertEqual(archive.show(self.root, "brand", added["id"])["usedIn"], [use])

    # -- integrity -----------------------------------------------------------------

    def test_verify_reports_missing_changed_and_uncatalogued_files(self):
        added = archive.add(self.root, "brand", self.original(), format_id="f")
        self.assertEqual(self.problems(), [])
        (self.root / "brand" / "f" / "video" / "stray.mp4").write_bytes(b"?")
        (self.root / "brand" / "f" / "video" / ".DS_Store").write_bytes(b"")
        Path(added["file"]).write_bytes(b"take 1!!")  # same size, different content
        self.assertEqual(self.problems(), ["not in catalog"])
        self.assertEqual(self.problems(rehash=True), ["changed", "not in catalog"])
        Path(added["file"]).unlink()
        self.assertIn("missing", self.problems())

    def test_an_unfinished_last_line_is_skipped_then_moved_aside_before_the_next_add(self):
        added = archive.add(self.root, "brand", self.original())
        catalog = self.root / "brand" / "catalog.jsonl"
        with catalog.open("ab") as stream:
            stream.write(b'{"event":"add","id":"half')
        warnings = io.StringIO()
        with contextlib.redirect_stderr(warnings):
            self.assertEqual(list(archive.assets(self.root / "brand")), [added["id"]])
            archive.add(self.root, "brand", self.original("z.mp4", b"z"))
        self.assertIn("unfinished last line", warnings.getvalue())
        self.assertEqual(len(archive.read_log(catalog)), 2)
        self.assertEqual(self.problems(), ["catalog line cut off by a crash"])

    def test_odd_hand_edits_and_links_are_reported_not_fatal(self):
        added = archive.add(self.root, "brand", self.original(), format_id="f")
        catalog = self.root / "brand" / "catalog.jsonl"
        with catalog.open("ab") as stream:
            stream.write(archive.log_line({"event": "note", "id": ["not", "an", "id"], "status": "selected"}))
        self.assertEqual(list(archive.assets(self.root / "brand")), [added["id"]])
        (self.root / "brand" / "f" / "video" / "linked.mp4").symlink_to(self.original("outside.mp4", b"o"))
        self.assertEqual(self.problems(), ["symlink inside the archive"])

    def test_a_whole_last_record_missing_its_newline_is_kept(self):
        added = archive.add(self.root, "brand", self.original())
        catalog = self.root / "brand" / "catalog.jsonl"
        catalog.write_bytes(catalog.read_bytes().rstrip(b"\n"))
        self.assertEqual(list(archive.assets(self.root / "brand")), [added["id"]])
        archive.add(self.root, "brand", self.original("z.mp4", b"z"))
        self.assertEqual(len(archive.read_log(catalog)), 2)
        self.assertEqual(self.problems(), [])

    def test_parallel_adds_from_separate_processes_are_all_kept(self):
        files = [self.original("p{}.mp4".format(i), "take {}".format(i).encode()) for i in range(10)]
        processes = [subprocess.Popen(
            [sys.executable, str(Path(archive.__file__).resolve()), "add", "--root", str(self.root),
             "--project", "brand", "--file", str(path)],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE) for path in files]
        for process in processes:
            _, errors = process.communicate(timeout=60)
            self.assertEqual(process.returncode, 0, errors)
        self.assertEqual(len(archive.assets(self.root / "brand")), 10)
        self.assertEqual(self.problems(rehash=True), [])

    # -- location ------------------------------------------------------------------

    def test_root_and_project_come_from_flags_then_environment_then_memory_then_home(self):
        project = self.work / "project"
        project.mkdir()
        location = memory.initialize(project, "Example Studio")
        home = self.work / "home"
        with patch.object(Path, "home", return_value=home):
            self.assertEqual(archive.resolve(start=project), (home / "ViewPrinter" / "archive", "example-studio"))
            config = json.loads((location / "config.json").read_text(encoding="utf-8"))
            config["archive"] = {"project": "studio", "root": "../../archive-from-config"}
            (location / "config.json").write_text(json.dumps(config), encoding="utf-8")
            self.assertEqual(archive.resolve(start=project), (project / "archive-from-config", "studio"))
            os.environ[archive.ROOT_ENVIRONMENT] = str(self.work / "environment-root")
            self.assertEqual(archive.resolve(start=project)[0], self.work / "environment-root")
            self.assertEqual(archive.resolve(self.work / "flag-root", "flagged", start=project),
                             (self.work / "flag-root", "flagged"))
        with self.assertRaises(archive.ArchiveError):
            archive.resolve(start=self.work)

    def test_an_old_format_name_files_under_the_current_id_and_an_unknown_one_warns(self):
        project = self.work / "project"
        project.mkdir()
        location = memory.initialize(project, "Example Studio")
        (location / "formats" / "street-quiz").mkdir()
        (location / "formats" / "street-quiz" / "v1.json").write_text(json.dumps(
            {"id": "street-quiz", "revision": 1, "aliases": ["street-quiz-old"]}), encoding="utf-8")
        old = self.cli("add", "--root", self.root, "--file", self.original(), "--format", "street-quiz-old",
                       cwd=project)
        self.assertEqual(old.returncode, 0, old.stderr)
        self.assertEqual(json.loads(old.stdout)["format"], "street-quiz")
        self.assertIn("old name", old.stderr)
        unknown = self.cli("add", "--root", self.root, "--file", self.original("b.mp4", b"b"), "--format", "streetquiz",
                           cwd=project)
        self.assertEqual(unknown.returncode, 0, unknown.stderr)
        self.assertIn("not one of this project's formats", unknown.stderr)
        self.assertEqual(archive.canonical_format("another-project", "streetquiz", start=project), "streetquiz")
        (location / "formats" / "street-quiz-old").mkdir()  # the superseded folder is still there
        (location / "formats" / "street-quiz-old" / "v1.json").write_text(json.dumps({"id": "street-quiz-old"}), encoding="utf-8")
        self.assertEqual(archive.canonical_format("example-studio", "street-quiz-old", start=project), "street-quiz")

    def test_the_root_may_be_a_link_to_another_disk_but_nothing_inside_may_be(self):
        drive = self.work / "drive"
        drive.mkdir()
        linked = self.work / "linked-root"
        linked.symlink_to(drive, target_is_directory=True)
        root, _ = archive.resolve(linked, "brand")
        archive.add(root, "brand", self.original())
        self.assertTrue((drive / "brand" / "catalog.jsonl").is_file())
        elsewhere = self.work / "elsewhere"
        elsewhere.mkdir()
        (drive / "redirected").symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaises(archive.ArchiveError):
            archive.add(root, "redirected", self.original("y.mp4", b"y"))
        (drive / "linked-catalog").mkdir()
        (drive / "linked-catalog" / "catalog.jsonl").symlink_to(elsewhere / "catalog.jsonl")
        with self.assertRaises(archive.ArchiveError):
            archive.add(root, "linked-catalog", self.original("w.mp4", b"w"))
        with self.assertRaises(archive.ArchiveError):
            archive.resolve(archive.SKILL_ROOT / "archive", "brand")

    # -- command line ----------------------------------------------------------------

    def test_command_line_add_note_find_checkout_verify_and_where(self):
        added = self.cli("add", "--root", self.root, "--project", "brand", "--file", self.original(),
                         "--format", "street-interview", "--record", "-", stdin=json.dumps(self.provenance()))
        self.assertEqual(added.returncode, 0, added.stderr)
        identifier = json.loads(added.stdout)["id"]
        noted = self.cli("note", "--root", self.root, "--project", "brand", "--id", identifier,
                         "--status", "selected", "--tag", "keeper")
        self.assertEqual(noted.returncode, 0, noted.stderr)
        found = self.cli("find", "--root", self.root, "--all-projects", "--status", "selected", "--json")
        self.assertEqual([json.loads(line)["id"] for line in found.stdout.splitlines()], [identifier])
        checkout = self.cli("checkout", "--root", self.root, "--project", "brand", "--id", identifier,
                            "--to", self.work / "copy.mp4", "--batch", "b", "--item", "i", "--version", "2")
        self.assertEqual(checkout.returncode, 0, checkout.stderr)
        self.assertEqual(self.cli("verify", "--root", self.root, "--project", "brand").returncode, 0)
        where = json.loads(self.cli("where", "--root", self.root, "--project", "brand").stdout)
        self.assertEqual(where["catalog"], str(self.root / "brand" / "catalog.jsonl"))
        missing = self.cli("add", "--root", self.root, "--project", "brand", "--file", self.work / "nope.mp4")
        self.assertEqual(missing.returncode, 1)
        self.assertIn("No file", missing.stderr)


if __name__ == "__main__":
    unittest.main()
