#!/usr/bin/env python3
"""Run with: python3 -m unittest discover -s scripts -p 'test_memory.py'."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import memory


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name).resolve() / "project"
        self.project.mkdir()
        self.environment = patch.dict(os.environ)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        os.environ.pop("VIEWPRINTER_CONTENT_MEMORY", None)

    def event(self, identifier="feedback-001"):
        return {"id": identifier, "createdAt": "2026-09-23T17:30:00Z",
                "rawMessage": "Keep this verbatim.", "scope": {"formatId": "morning"}}

    def cli(self, *arguments):
        return subprocess.run([sys.executable, str(Path(memory.__file__).resolve()), *map(str, arguments)],
                              capture_output=True, text=True, check=False)

    def alias(self):
        """A symlinked ancestor, as macOS /tmp and /var are, on every platform."""
        link = self.project.parent / "alias"
        link.symlink_to(self.project.parent, target_is_directory=True)
        return link

    def test_init_is_idempotent_and_preserves_preferences_and_open_items(self):
        location = memory.initialize(self.project, "Example")
        project_md = location / "project.md"
        project_md.write_text("# Preferences\nKeep warm language.\n", encoding="utf-8")
        state_file = location / "state" / "carry-forward.json"
        state_file.write_text(json.dumps({"schemaVersion": 1, "openItems": [
            {"id": "pending-1", "text": "Next batch needs review"}]}), encoding="utf-8")
        memory.append(location, "feedback", self.event())
        before = {str(path.relative_to(location)): (path.read_bytes(), path.stat().st_mtime_ns)
                  for path in location.rglob("*") if path.is_file()}
        self.assertEqual(memory.initialize(self.project, "Changed name ignored"), location)
        after = {str(path.relative_to(location)): (path.read_bytes(), path.stat().st_mtime_ns)
                 for path in location.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(memory.read_object(location / "config.json"), {
            "schemaVersion": 1, "projectName": "Example"})

    def test_partial_init_is_refused_without_changing_existing_files(self):
        location = self.project / memory.MEMORY_RELATIVE
        location.mkdir(parents=True)
        valuable = location / "notes.txt"
        valuable.write_text("Do not delete this.", encoding="utf-8")
        with self.assertRaises(memory.MemoryError):
            memory.initialize(self.project)
        self.assertEqual(list(location.iterdir()), [valuable])
        self.assertEqual(valuable.read_text(encoding="utf-8"), "Do not delete this.")

    def test_init_completes_a_memory_the_posting_helper_started_and_keeps_its_logs(self):
        location = self.project / memory.MEMORY_RELATIVE
        logs = location / "history" / "publications"
        logs.mkdir(parents=True)
        (logs / "2026-10.jsonl").write_text('{"postId": "p1"}\n', encoding="utf-8")
        (logs / ".gitattributes").write_text("*.jsonl merge=union\n", encoding="utf-8")
        (location / ".DS_Store").write_bytes(b"")
        with self.assertRaises(memory.MemoryError):
            memory.locate(self.project)
        self.assertEqual(memory.initialize(self.project, "Example"), location)
        self.assertEqual((logs / "2026-10.jsonl").read_text(encoding="utf-8"), '{"postId": "p1"}\n')
        self.assertEqual(memory.locate(self.project), location)
        (location / "config.json").unlink()  # now partial in the ordinary way
        with self.assertRaises(memory.MemoryError):
            memory.initialize(self.project, "Example")
        self.assertFalse((location / "config.json").exists())

    def test_append_is_immutable_and_identical_replay_does_not_write(self):
        location = memory.initialize(self.project)
        record = self.event()
        destination = memory.append(location, "feedback", record)
        original = (destination.read_bytes(), destination.stat().st_mtime_ns)
        self.assertEqual(memory.append(location, "feedback", dict(reversed(list(record.items())))), destination)
        self.assertEqual((destination.read_bytes(), destination.stat().st_mtime_ns), original)
        with self.assertRaisesRegex(memory.MemoryError, "Conflicting"):
            memory.append(location, "feedback", dict(record, rawMessage="Replacement"))
        self.assertEqual((destination.read_bytes(), destination.stat().st_mtime_ns), original)
        self.assertEqual(list(destination.parent.iterdir()), [destination])

    def test_a_drive_without_hard_links_still_never_overwrites_a_record(self):
        # FAT and exFAT drives refuse os.link; records are created exclusively instead.
        location = memory.initialize(self.project)
        record = self.event()
        with patch.object(memory.os, "link", side_effect=PermissionError(1, "Operation not permitted")):
            destination = memory.append(location, "feedback", record)
            self.assertEqual(json.loads(destination.read_text(encoding="utf-8")), record)
            self.assertEqual(memory.append(location, "feedback", dict(record)), destination)
            with self.assertRaisesRegex(memory.MemoryError, "Conflicting"):
                memory.append(location, "feedback", dict(record, rawMessage="Replacement"))
        self.assertEqual(list(destination.parent.iterdir()), [destination])

    def test_concurrent_independent_events_have_no_lost_updates(self):
        location = memory.initialize(self.project)
        records = [self.event("parallel-{:03d}".format(index)) for index in range(64)]
        with ThreadPoolExecutor(max_workers=12) as executor:
            results = list(executor.map(lambda record: memory.append(location, "feedback", record), records))
        self.assertEqual(len(set(results)), len(records))
        for result, expected in zip(results, records):
            self.assertEqual(memory.read_object(result), expected)
        self.assertEqual(len(list((location / "history" / "feedback").iterdir())), len(records))

    def test_concurrent_identical_replays_publish_one_record(self):
        location = memory.initialize(self.project)
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _: memory.append(location, "findings", self.event()), range(24)))
        self.assertEqual(len(set(results)), 1)
        self.assertEqual(list((location / "history" / "findings").iterdir()), [results[0]])

    def test_discovery_walks_project_ancestors_and_never_initializes(self):
        location = memory.initialize(self.project)
        child = self.project / "src" / "nested"
        child.mkdir(parents=True)
        self.assertEqual(memory.locate(child), location)
        with patch.object(Path, "cwd", return_value=child):
            self.assertEqual(memory.locate(), location)
        other = self.project.parent / "other"
        other.mkdir()
        with self.assertRaises(memory.MemoryError):
            memory.locate(other)
        self.assertFalse((other / ".viewprinter").exists())

    def test_environment_override_wins_and_invalid_override_does_not_fall_back(self):
        first = memory.initialize(self.project)
        other = self.project.parent / "other"
        other.mkdir()
        second = memory.initialize(other)
        with patch.dict(os.environ, {"VIEWPRINTER_CONTENT_MEMORY": str(second)}):
            self.assertEqual(memory.locate(self.project), second)
        for override in (str(first / "missing"), ""):
            with self.subTest(override=override), patch.dict(os.environ, {"VIEWPRINTER_CONTENT_MEMORY": override}):
                with self.assertRaises(memory.MemoryError):
                    memory.locate(self.project)

    def test_init_and_locate_honor_custom_external_override(self):
        custom = self.project.parent / "shared-context" / "custom-memory"
        with patch.dict(os.environ, {"VIEWPRINTER_CONTENT_MEMORY": str(custom)}):
            self.assertEqual(memory.initialize(self.project, "External memory"), custom)
            self.assertEqual(memory.locate(self.project), custom)
            self.assertEqual(memory.locate(self.project.parent), custom)
            self.assertNotIn("projectRoot", memory.read_object(custom / "config.json"))
            self.assertEqual(memory.initialize(self.project), custom)
            self.assertFalse((self.project / ".viewprinter").exists())
        with self.assertRaises(memory.MemoryError):
            memory.locate(self.project)

    def test_external_override_serves_any_project_without_rewriting(self):
        custom = self.project.parent / "custom-memory"
        other = self.project.parent / "other-project"
        other.mkdir()
        with patch.dict(os.environ, {"VIEWPRINTER_CONTENT_MEMORY": str(custom)}):
            memory.initialize(self.project)
            original = (custom / "config.json").read_bytes()
            self.assertEqual(memory.initialize(other, "Other"), custom)
            self.assertEqual((custom / "config.json").read_bytes(), original)
        self.assertFalse((other / ".viewprinter").exists())

    def test_moved_project_keeps_its_memory(self):
        memory.initialize(self.project, "Example")
        moved = self.project.parent / "renamed"
        self.project.rename(moved)
        location = moved / memory.MEMORY_RELATIVE
        (moved / "src").mkdir()
        self.assertEqual(memory.locate(moved / "src"), location)
        self.assertEqual(memory.initialize(moved), location)
        self.assertTrue(memory.append(location, "feedback", self.event()).is_file())

    def test_clone_or_worktree_copy_uses_its_own_memory(self):
        original = memory.initialize(self.project, "Example")
        self.assertNotIn(str(self.project.parent), (original / "config.json").read_text(encoding="utf-8"))
        clone = self.project.parent / "worktree"
        shutil.copytree(self.project, clone, symlinks=True)
        location = clone / memory.MEMORY_RELATIVE
        self.assertEqual(memory.locate(clone), location)
        self.assertEqual(memory.initialize(clone), location)
        memory.append(location, "findings", self.event())
        self.assertEqual(list((original / "history" / "findings").iterdir()), [])

    def test_legacy_absolute_project_root_is_ignored_and_preserved(self):
        location = memory.initialize(self.project)
        config_path = location / "config.json"
        for root in (str(self.project), "/elsewhere/old-checkout"):
            with self.subTest(root=root):
                config_path.write_text(json.dumps({
                    "schemaVersion": 1, "projectName": "Example", "projectRoot": root,
                    "defaults": {"phoneMountPreset": "assets/phone-mounts/p/v1/preset.json"}}), encoding="utf-8")
                original = config_path.read_bytes()
                self.assertEqual(memory.locate(self.project), location)
                self.assertEqual(memory.initialize(self.project, "Renamed"), location)
                self.assertTrue(memory.append(location, "changes", self.event("change-" + str(len(root)))).is_file())
                self.assertEqual(config_path.read_bytes(), original)

    def test_symlinked_ancestors_resolve_for_init_locate_and_append(self):
        through_alias = self.alias() / "project"
        location = memory.initialize(through_alias)
        self.assertEqual(location, self.project / memory.MEMORY_RELATIVE)
        self.assertEqual(memory.locate(through_alias), location)
        self.assertEqual(memory.locate(Path(self.temporary.name) / "project"), location)
        destination = memory.append(through_alias / memory.MEMORY_RELATIVE, "feedback", self.event())
        self.assertEqual(destination, location / "history" / "feedback" / "feedback-001.json")

    def test_init_refuses_invalid_environment_override(self):
        for override in ("", str(memory.SKILL_ROOT / "memory")):
            with self.subTest(override=override), patch.dict(os.environ, {"VIEWPRINTER_CONTENT_MEMORY": override}):
                with self.assertRaises(memory.MemoryError):
                    memory.initialize(self.project)
        self.assertFalse((self.project / ".viewprinter").exists())

    def test_discovery_refuses_partial_nearer_project(self):
        memory.initialize(self.project)
        nested = self.project / "nested"
        (nested / memory.MEMORY_RELATIVE).mkdir(parents=True)
        with self.assertRaises(memory.MemoryError):
            memory.locate(nested)

    def test_symlink_boundary_and_existing_record_are_refused(self):
        external = self.project.parent / "external"
        external.mkdir()
        link = self.project / ".viewprinter"
        link.symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(memory.MemoryError, "Symlink"):
            memory.initialize(self.project)
        self.assertEqual(list(external.iterdir()), [])
        link.unlink()
        location = memory.initialize(self.project)
        record_target = external / "record.json"
        record_target.write_text(json.dumps(self.event()), encoding="utf-8")
        destination = location / "history" / "feedback" / "feedback-001.json"
        destination.symlink_to(record_target)
        original = record_target.read_bytes()
        with self.assertRaisesRegex(memory.MemoryError, "Symlink"):
            memory.append(location, "feedback", self.event())
        self.assertEqual(record_target.read_bytes(), original)
        collection = location / "history" / "changes"
        collection.rmdir()
        collection.symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(memory.MemoryError, "Symlink"):
            memory.append(location, "changes", self.event())
        self.assertEqual(list(external.iterdir()), [record_target])

    def test_skill_directory_cannot_be_used_for_memory_or_discovery(self):
        with patch.object(memory, "SKILL_ROOT", self.project):
            with self.assertRaisesRegex(memory.MemoryError, "installed skill"):
                memory.initialize(self.project)
            with self.assertRaisesRegex(memory.MemoryError, "installed skill"):
                memory.locate(self.project)
        self.assertFalse((self.project / ".viewprinter").exists())

    def test_record_validation_and_collection_traversal(self):
        location = memory.initialize(self.project)
        for identifier in ("../escape", "a/b", "..", "", "x" * 129):
            with self.subTest(identifier=identifier), self.assertRaises(memory.MemoryError):
                memory.append(location, "changes", self.event(identifier))
        for timestamp in (None, "", "  ", 123):
            with self.subTest(timestamp=timestamp), self.assertRaises(memory.MemoryError):
                memory.append(location, "changes", dict(self.event(), createdAt=timestamp))
        with self.assertRaises(memory.MemoryError):
            memory.append(location, "../escape", self.event())
        self.assertFalse(any((location / "history").glob("*/*.json")))

    def test_cli_init_locate_append_and_conflict_exit_status(self):
        run = self.cli
        result = run("init", "--project", self.project, "--name", "CLI example")
        self.assertEqual(result.returncode, 0, result.stderr)
        location = Path(result.stdout.strip())
        self.assertEqual(run("locate", "--start", self.project).stdout.strip(), str(location))
        payload = self.project / "input.json"
        payload.write_text(json.dumps(self.event()), encoding="utf-8")
        result = run("append", "--memory", location, "--collection", "feedback", "--file", payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(memory.read_object(Path(result.stdout.strip())), self.event())
        payload.write_text(json.dumps(dict(self.event(), rawMessage="Conflict")), encoding="utf-8")
        result = run("append", "--memory", location, "--collection", "feedback", "--file", payload)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Conflicting immutable record", result.stderr)

    def test_cli_accepts_temp_paths_and_event_files_from_anywhere(self):
        alias = self.alias()
        result = self.cli("init", "--project", alias / "project")
        self.assertEqual(result.returncode, 0, result.stderr)
        location = Path(result.stdout.strip())
        self.assertEqual(location, self.project / memory.MEMORY_RELATIVE)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as stream:
            json.dump(self.event("temp-file"), stream)
        self.addCleanup(os.unlink, stream.name)
        linked = alias / "linked-event.json"
        linked.symlink_to(stream.name)
        for source in (stream.name, linked):
            with self.subTest(source=str(source)):
                result = self.cli("append", "--memory", alias / "project" / memory.MEMORY_RELATIVE,
                                  "--collection", "feedback", "--file", source)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(Path(result.stdout.strip()), location / "history" / "feedback" / "temp-file.json")


if __name__ == "__main__":
    unittest.main()
