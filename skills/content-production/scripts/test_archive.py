#!/usr/bin/env python3
"""Run with: python3 -m unittest discover -s scripts -p 'test_archive.py'."""

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
from unittest.mock import ANY, patch

import archive


def listing(folder):
    """A folder's entries. Windows can't lock a folder, so archive.py keeps a .lock file in it."""
    return sorted(p.name for p in folder.iterdir() if not (archive.fcntl is None and p.name == ".lock"))
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
                              input=stdin, capture_output=True, text=True, check=False, cwd=cwd or self.work, encoding="utf-8")

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
        self.assertEqual(listing((self.root / "brand")), ["catalog.jsonl", "street-interview"])

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
        self.assertEqual(listing((self.root / "brand")), ["catalog.jsonl", "unfiled"])

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
        self.assertEqual(listing((self.root / "brand")), [])
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
        self.assertEqual(listing(stored.parent), [stored.name])

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
            archive.resolve(archive.INSTALLED[0] / "archive", "brand")

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

    # -- ViewPrinter keeps the originals too ---------------------------------------

    def row(self, asset, media_id, purpose="source"):
        """A file as ViewPrinter's media_list or media_save answers describe it."""
        return {"id": media_id, "sha256": asset["sha256"], "purpose": purpose, "kind": asset["kind"]}

    def keep(self, *pairs, purpose="source"):
        """ViewPrinter's media_save answer for these (asset, media id) pairs, recorded."""
        return archive.stored(self.root, "brand", {"saved": [self.row(a, m, purpose) for a, m in pairs]})

    def test_upload_list_gives_media_upload_items_and_what_to_save_about_each(self):
        still = archive.add(self.root, "brand", self.original("still.png", b"still"), {"origin": "generated"},
                            format_id="street-interview")
        self.keep((still, "m-still"))
        reference = archive.add(self.root, "brand", self.original("ref.jpg", b"reference"), {},
                                format_id="street-interview")
        take = archive.add(self.root, "brand", self.original(), self.provenance(
            status="selected", reason="best laugh", identity="Host One", tags=["Couch Scene", "night"],
            batchId="october", itemId="SI-04", inputs=[still["id"], reference["id"], "not-archived"],
            rights={"source": "https://example.com/where-it-was-found"}), format_id="street-interview")
        archive.add(self.root, "brand", self.original("notes.txt", b"notes"), {}, format_id="street-interview")
        listed = archive.upload_list(self.root, "brand")
        self.assertEqual([item["archiveId"] for item in listed["items"]], [reference["id"], take["id"]])
        self.assertEqual(listed["skipped"], {"ViewPrinter keeps video, images and audio only": 1})
        item = listed["items"][1]
        self.assertEqual(item["upload"], {"kind": "video", "mime_type": "video/mp4", "sha256": take["sha256"],
                                          "purpose": "source"})
        self.assertEqual(item["describe"]["tags"], ["brand", "street-interview", "generated", "selected",
                                                    "host-one", "couch-scene", "night"])
        self.assertEqual(item["describe"]["metadata"], {
            "provider": "example-provider", "model": "example-video-1", "prompt": self.provenance()["prompt"],
            "jobId": "req-1", "ref": "SI-04", "costUsd": 4.55,
            "sourceUrl": "https://example.com/where-it-was-found", "inputs": ["m-still"]})
        self.assertEqual(item["pendingInputs"], [reference["id"]])  # takes its media id from this batch's answers
        self.assertIn("Selected: best laugh.", item["describe"]["description"])
        self.assertIn("Prompt: A man laughs", item["describe"]["description"])
        # The description carries the start of a long prompt; metadata keeps all of it, measured as
        # ViewPrinter measures (UTF-16), so a character outside the basic plane counts twice.
        long = dict(take, prompt="word " * 400)
        self.assertTrue(archive.upload_description(long).endswith("word…"))
        self.assertEqual(archive.upload_metadata(long, {})["prompt"], ("word " * 400).strip())
        self.assertEqual(archive.fit("ab\U0001F600cd", 3), "ab")
        # An audio-only .mp4 is uploaded as audio.
        voice = archive.add(self.root, "brand", self.original("voice.mp4", b"voice"), {}, kind="audio")
        voiced = [i for i in archive.upload_list(self.root, "brand")["items"] if i["archiveId"] == voice["id"]]
        self.assertEqual(voiced[0]["upload"]["mime_type"], "audio/mp4")
        # One media_upload call at a time, and nothing missing from disk is offered.
        self.assertEqual((len(archive.upload_list(self.root, "brand", limit=2)["items"]),
                          archive.upload_list(self.root, "brand", limit=2)["remaining"]), (2, 1))
        Path(take["file"]).unlink()
        self.assertEqual(archive.upload_list(self.root, "brand", format_id="street-interview")["skipped"],
                         {"ViewPrinter keeps video, images and audio only": 1, "missing or changed here; run verify": 1})

    def test_upload_steps_pairs_answers_describes_only_new_files_and_links_inputs(self):
        reference = archive.add(self.root, "brand", self.original("ref.jpg", b"reference"), {})
        take = archive.add(self.root, "brand", self.original(), self.provenance(inputs=[reference["id"]]))
        listed = archive.upload_list(self.root, "brand")
        put = {"url": "https://storage.example/put", "headers": {"Content-Type": "x"}, "expires_in_seconds": 900}
        steps = archive.upload_steps(listed, {"items": [dict(put, id="m-ref"), dict(put, id="m-take")]})
        self.assertEqual([p["archiveId"] for p in steps["put"]], [reference["id"], take["id"]])
        self.assertEqual(steps["put"][1]["file"], take["file"])
        self.assertEqual([s["id"] for s in steps["save"]], ["m-ref", "m-take"])
        self.assertEqual(steps["save"][1]["metadata"]["inputs"], ["m-ref"])
        self.assertEqual(steps["landed"], [])
        # A file ViewPrinter already had is recorded as it is, and never described again.
        steps = archive.upload_steps(listed, [{"id": "m-old", "existing": True}, dict(put, id="m-take")])
        self.assertEqual(steps["landed"], [{"id": "m-old", "sha256": reference["sha256"]}])
        self.assertEqual([s["id"] for s in steps["save"]], ["m-take"])
        self.assertEqual(steps["save"][0]["metadata"]["inputs"], ["m-old"])
        for answers in ([dict(put, id="m-ref")], [{"id": "m-ref"}, dict(put, id="m-take")], [{}, {}]):
            with self.assertRaises(archive.ArchiveError):
                archive.upload_steps(listed, answers)

    def test_an_input_outside_the_filter_comes_along_so_it_can_be_linked(self):
        face = archive.add(self.root, "brand", self.original("face.png", b"identity reference"), {})
        take = archive.add(self.root, "brand", self.original(), self.provenance(batchId="b1", inputs=[face["id"]]))
        listed = archive.upload_list(self.root, "brand", batch="b1")
        self.assertEqual([i["archiveId"] for i in listed["items"]], [face["id"], take["id"]])
        put = {"url": "https://storage.example/put", "headers": {}}
        steps = archive.upload_steps(listed, [dict(put, id="m-face"), dict(put, id="m-take")])
        self.assertEqual((steps["save"][1]["metadata"]["inputs"], steps["unlinked"]), (["m-face"], []))
        # An input that can't go along is named, not dropped silently.
        steps = archive.upload_steps({"items": listed["items"][1:]}, [dict(put, id="m-take")])
        self.assertEqual(steps["unlinked"], [{"archiveId": take["id"], "inputs": [face["id"]]}])

    def test_stored_records_only_what_viewprinters_answers_show_matching_by_sha256(self):
        take = archive.add(self.root, "brand", self.original(), self.provenance())
        other = archive.add(self.root, "brand", self.original("b.mp4", b"take two"), self.provenance())
        stranger = {"id": "m-x", "sha256": "0" * 64, "purpose": "source"}
        answer = archive.stored(self.root, "brand", {"saved": [self.row(take, "m-1"), stranger]})
        self.assertEqual((answer["recorded"], answer["otherFiles"]),
                         ([{"id": take["id"], "mediaId": "m-1", "purpose": "source"}], 1))
        self.assertEqual(archive.stored(self.root, "brand", [self.row(take, "m-1")])["recorded"], [])  # again: nothing new
        # Pages of media_list answers, and upload-steps' landed rows, whose purpose isn't known yet.
        archive.stored(self.root, "brand", [{"media": [self.row(take, "m-1", "library")], "nextCursor": None},
                                            {"landed": [{"id": "m-2", "sha256": other["sha256"]}]}])
        state = archive.assets(self.root / "brand")
        self.assertEqual(state[take["id"]]["viewprinterMedia"]["purpose"], "library")
        self.assertEqual(state[other["id"]]["viewprinterMedia"], {"mediaId": "m-2", "storedAt": ANY})
        with self.assertRaises(archive.ArchiveError):
            archive.stored(self.root, "brand", {"saved": []})
        with self.assertRaisesRegex(archive.ArchiveError, "archive the original first"):
            archive.stored(self.root, "brand", {"media": [stranger]})
        with self.assertRaises(archive.ArchiveError):  # only the archive's own events say where it is kept
            archive.note(self.root, "brand", take["id"], {"viewprinterMedia": {"mediaId": "forged"}})
        # Where a listing shows the same bytes twice, source material wins.
        archive.stored(self.root, "brand", [self.row(other, "m-lib", "library"), self.row(other, "m-src")])
        self.assertEqual(archive.show(self.root, "brand", other["id"])["viewprinterMedia"]["mediaId"], "m-src")

    def released_take(self):
        take = archive.add(self.root, "brand", self.original(), self.provenance(), format_id="street-interview")
        self.keep((take, "m-1"))
        archive.release_originals(self.root, "brand", {"media": [self.row(take, "m-1")]}, "yes, free the space",
                                  ids=[take["id"]])
        return take

    def test_release_takes_viewprinters_fresh_word_the_users_approval_and_identical_bytes(self):
        take = archive.add(self.root, "brand", self.original(), self.provenance(), format_id="street-interview")
        other = archive.add(self.root, "brand", self.original("b.mp4", b"take two"), self.provenance(),
                            format_id="street-interview")
        posted = archive.add(self.root, "brand", self.original("c.mp4", b"take six"), self.provenance(),
                             format_id="street-interview")
        listing = {"media": [self.row(take, "m-1"), self.row(other, "m-2"), self.row(posted, "m-3", "library")]}
        with self.assertRaisesRegex(archive.ArchiveError, "not in ViewPrinter"):
            archive.release_originals(self.root, "brand", listing, "yes, free the space", ids=[take["id"]])
        self.keep((take, "m-1"), (other, "m-2"))
        self.keep((posted, "m-3"), purpose="library")
        with self.assertRaisesRegex(archive.ArchiveError, "fresh media_list"):
            archive.release_originals(self.root, "brand", {}, "yes", ids=[take["id"]])
        with self.assertRaisesRegex(archive.ArchiveError, "approval"):
            archive.release_originals(self.root, "brand", listing, "  ", ids=[take["id"]])
        preview = archive.release_originals(self.root, "brand", listing, format_id="street-interview", dry_run=True)
        self.assertEqual((sorted(preview["wouldRelease"]), preview["bytes"]), (sorted([take["id"], other["id"]]), 16))
        self.assertIn("file to post", preview["skipped"][0]["reason"])  # a library file can be deleted
        self.assertTrue(Path(take["file"]).exists())
        # ViewPrinter's listing decides: missing from it, or a different file there, and nothing goes.
        for wrong in ({"media": [self.row(other, "m-2")]}, {"media": [dict(self.row(take, "m-1"), sha256="f" * 64)]}):
            self.assertEqual(archive.release_originals(self.root, "brand", wrong, "yes", ids=[take["id"]])["released"],
                             [])
        Path(other["file"]).write_bytes(b"take TWO")  # same size, different bytes: never released
        released = archive.release_originals(self.root, "brand", listing, "yes, free the space",
                                             format_id="street-interview")
        self.assertEqual((released["released"], released["bytes"]), ([take["id"]], 8))
        self.assertEqual(sorted(s["id"] for s in released["skipped"]), sorted([other["id"], posted["id"]]))
        self.assertFalse(Path(take["file"]).exists())
        kept = archive.show(self.root, "brand", take["id"])["releasedLocally"]
        self.assertEqual((kept["approval"], kept["mediaId"]), ("yes, free the space", "m-1"))
        report = archive.verify(self.root, "brand")
        self.assertEqual(report["releasedToViewPrinter"], 1)
        self.assertNotIn(take["id"], [problem["id"] for problem in report["problems"]])
        with self.assertRaisesRegex(archive.ArchiveError, "media_id m-1.*archive.py restore --id"):
            archive.checkout(self.root, "brand", take["id"], self.work / "copy.mp4")
        self.assertEqual(archive.release_originals(self.root, "brand", listing, "again", ids=[take["id"]])["released"],
                         [])

    def test_a_file_that_cannot_be_removed_is_skipped_and_stays_recorded_as_local(self):
        take = archive.add(self.root, "brand", self.original(), self.provenance())
        self.keep((take, "m-1"))
        with patch.object(Path, "unlink", side_effect=PermissionError("in use")):
            answer = archive.release_originals(self.root, "brand", {"media": [self.row(take, "m-1")]}, "yes",
                                               ids=[take["id"]])
        self.assertEqual((answer["released"], answer["skipped"][0]["id"]), ([], take["id"]))
        self.assertTrue(Path(take["file"]).exists())
        self.assertNotIn("releasedLocally", archive.show(self.root, "brand", take["id"]))

    def test_restore_takes_only_the_same_bytes_and_ends_the_release(self):
        take = self.released_take()
        with self.assertRaisesRegex(archive.ArchiveError, "not the original"):
            archive.restore_original(self.root, "brand", take["id"], self.original("wrong.mp4", b"take two"))
        self.assertIn("releasedLocally", archive.show(self.root, "brand", take["id"]))
        restored = archive.restore_original(self.root, "brand", take["id"],
                                            self.original("download.mp4", b"take one"), move=True)
        self.assertTrue(restored["restored"])
        self.assertNotIn("releasedLocally", archive.show(self.root, "brand", take["id"]))
        self.assertEqual(archive.checkout(self.root, "brand", take["id"], self.work / "copy.mp4").read_bytes(),
                         b"take one")
        self.assertEqual(archive.verify(self.root, "brand")["releasedToViewPrinter"], 0)
        # Copied back another way, such as from a backup: adding it again ends the release too.
        archive.release_originals(self.root, "brand", {"media": [self.row(take, "m-1")]}, "yes", ids=[take["id"]])
        Path(take["file"]).write_bytes(b"take one")
        self.assertTrue(archive.add(self.root, "brand", self.original("again.mp4", b"take one"))["restored"])
        self.assertNotIn("releasedLocally", archive.show(self.root, "brand", take["id"]))
        # A different file of the same size in its place is set aside, and the original goes back.
        archive.release_originals(self.root, "brand", {"media": [self.row(take, "m-1")]}, "yes", ids=[take["id"]])
        Path(take["file"]).write_bytes(b"take ONE")
        archive.restore_original(self.root, "brand", take["id"], self.original("download.mp4", b"take one"))
        self.assertEqual(Path(take["file"]).read_bytes(), b"take one")
        self.assertEqual([p.read_bytes() for p in Path(take["file"]).parent.glob("*.changed-*")], [b"take ONE"])

    def test_fields_an_older_catalog_named_released_or_viewprinter_are_only_fields(self):
        song = archive.add(self.root, "shared-music", self.original("song.mp3", b"song"),
                           {"origin": "licensed", "released": "2019-05-01", "viewprinter": "lib-123"})
        project = self.root / "shared-music"
        # A hand-written line can't claim the archive's own state either.
        with open(project / "catalog.jsonl", "ab") as catalog:
            catalog.write(archive.log_line({"event": "note", "id": song["id"], "notedAt": "2026-01-01T00:00:00Z",
                                            "releasedLocally": {"mediaId": "m"}}))
        state = archive.assets(project)[song["id"]]
        self.assertEqual((state["released"], state.get("releasedLocally")), ("2019-05-01", None))
        self.assertEqual(len(archive.upload_list(self.root, "shared-music")["items"]), 1)
        Path(song["file"]).unlink()
        self.assertEqual([p["problem"] for p in archive.verify(self.root, "shared-music")["problems"]], ["missing"])
        with self.assertRaisesRegex(archive.ArchiveError, "is missing"):
            archive.checkout(self.root, "shared-music", song["id"], self.work / "copy.mp3")

    def test_writes_work_where_a_folder_cannot_be_locked(self):
        if archive.fcntl is None:
            self.skipTest("Windows always locks with a file; every test there takes this path")
        flock = archive.fcntl.flock

        def no_folder_locks(descriptor, operation):
            if stat.S_ISDIR(os.fstat(descriptor).st_mode):
                raise OSError(errno.ENOTSUP, "this disk cannot lock a folder")
            return flock(descriptor, operation)
        with patch.object(archive.fcntl, "flock", side_effect=no_folder_locks):
            take = self.released_take()
            archive.restore_original(self.root, "brand", take["id"], self.original("download.mp4", b"take one"))
            archive.note(self.root, "brand", take["id"], {"status": "selected"})
        self.assertEqual(archive.show(self.root, "brand", take["id"])["status"], "selected")

    def test_command_line_upload_steps_stored_release_and_restore(self):
        take = archive.add(self.root, "brand", self.original(), self.provenance(), format_id="street-interview")
        base = ("--root", self.root, "--project", "brand")
        listed = self.cli("upload-list", *base)
        self.assertEqual(json.loads(listed.stdout)["items"][0]["archiveId"], take["id"])
        self.assertEqual(self.cli("upload-list", *base, "--limit", "51").returncode, 1)
        answers = self.work / "answers.json"
        answers.write_text(json.dumps({"items": [{"id": "m-1", "url": "https://storage.example/put", "headers": {}}]}),
                           encoding="utf-8")
        steps = self.cli("upload-steps", *base, "--list", "-", "--answers", answers, stdin=listed.stdout)
        self.assertEqual(json.loads(steps.stdout)["save"][0]["id"], "m-1", steps.stderr)
        listing = json.dumps({"media": [self.row(take, "m-1")], "nextCursor": None})
        recorded = self.cli("stored", *base, "--listed", "-", stdin=listing)
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        self.assertIn("[also in ViewPrinter]", self.cli("find", *base).stdout)
        refused = self.cli("release", *base, "--all-stored", "--listed", "-", stdin=listing)
        self.assertEqual(refused.returncode, 1)
        self.assertIn("--approval", refused.stderr)
        released = self.cli("release", *base, "--all-stored", "--listed", "-", "--approval", "remove them",
                            stdin=listing)
        self.assertEqual(json.loads(released.stdout)["released"], [take["id"]], released.stderr)
        self.assertIn("[released: in ViewPrinter only]", self.cli("find", *base).stdout)
        back = self.cli("restore", *base, "--id", take["id"], "--file", self.original("download.mp4", b"take one"))
        self.assertTrue(json.loads(back.stdout)["restored"], back.stderr)
        # --out writes UTF-8 itself; and a file Windows PowerShell's > wrote (UTF-16) still reads.
        other = archive.add(self.root, "brand", self.original("e.mp4", b"take two"), self.provenance(prompt="café"))
        written = self.cli("upload-list", *base, "--out", self.work / "list.json")
        self.assertEqual(json.loads(written.stdout)["wrote"], str(self.work / "list.json"), written.stderr)
        listing = (self.work / "list.json").read_text(encoding="utf-8")
        self.assertIn("café", listing)
        (self.work / "list-utf16.json").write_text(listing, encoding="utf-16")
        self.assertEqual(archive.read_json(str(self.work / "list-utf16.json"))["items"][0]["archiveId"], other["id"])


if __name__ == "__main__":
    unittest.main()
