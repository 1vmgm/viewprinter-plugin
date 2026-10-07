"""shelf.py: every shelved project comes back byte for byte, and nothing is lost when
something goes wrong."""
import hashlib
import io
import json
import os
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import shelf

OLD = time.time() - 10 * 86400


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Unseekable(io.RawIOBase):
    """A stream zipfile cannot seek, so it writes data descriptors after each member."""

    def __init__(self):
        self.data = bytearray()

    def writable(self):
        return True

    def write(self, b):
        self.data += b
        return len(b)

    def seekable(self):
        return False

    def tell(self):
        raise OSError("unseekable")

    def seek(self, *args):
        raise OSError("unseekable")


class ShelfTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        patcher = mock.patch.dict(os.environ, {"VIEWPRINTER_SHELF": str(self.root / "store")})
        patcher.start()
        self.addCleanup(patcher.stop)
        (self.root / "store").mkdir()
        self.shared = os.urandom(500_000)

    def tearDown(self):
        for path in self.root.rglob("*"):
            if path.is_file():
                path.chmod(0o644)   # stored pieces are read-only, which Windows won't delete
        self.temp.cleanup()

    def project(self, name, extra=b"", streaming=False, age=OLD):
        path = self.root / name
        stream = Unseekable() if streaming else open(path, "wb")
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("document.json", json.dumps({"name": name}))
            archive.writestr(zipfile.ZipInfo("media/shared.mp4"), self.shared)            # stored
            archive.writestr("media/own.wav", os.urandom(200_000) + extra)             # stored
            archive.writestr("fonts/small.ttf", b"font" * 100)                        # small
            archive.writestr("media/noise.bin", os.urandom(300_000), compress_type=zipfile.ZIP_DEFLATED)
            archive.comment = b"made in a test"
        if streaming:
            path.write_bytes(bytes(stream.data))
        else:
            stream.close()
        os.utime(path, (age, age))
        return path

    def shelve(self, path, busy=()):
        return shelf.shelve_one(path, 3, set(busy), False, set())

    def manifest(self, path):
        return path.with_name(path.name + shelf.SUFFIX)

    def test_round_trip_is_byte_exact(self):
        for name, streaming in (("plain.tsrct", False), ("descriptors.tsrct", True)):
            path = self.project(name, streaming=streaming)
            original, digest = path.read_bytes(), sha(path)
            self.assertEqual(self.shelve(path)[0], "shelved")
            self.assertFalse(path.exists())
            self.assertTrue(self.manifest(path).exists())
            shelf.unshelve_one(self.manifest(path))
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(sha(path), digest)
            self.assertFalse(self.manifest(path).exists())
            with zipfile.ZipFile(path) as archive:
                self.assertIsNone(archive.testzip())

    def test_shared_footage_is_stored_once(self):
        first, second = self.project("one.tsrct"), self.project("two.tsrct", extra=b"different")
        _, _, size1, new1 = self.shelve(first)
        _, _, size2, new2 = self.shelve(second)
        self.assertEqual(new1, size1)                        # the first project stores everything
        self.assertLess(new2, size2 - len(self.shared) + 1)  # the second reuses the shared clip
        shelf.unshelve_one(self.manifest(second))
        self.assertTrue(second.exists())

    def test_damaged_store_never_produces_a_wrong_project(self):
        path = self.project("damaged.tsrct")
        self.shelve(path)
        biggest = max(json.loads(self.manifest(path).read_text(encoding="utf-8"))["pieces"], key=lambda p: p[1])[0]
        stored = shelf.object_path(biggest)
        stored.chmod(0o644)
        data = bytearray(stored.read_bytes())
        data[100] ^= 0xFF
        stored.write_bytes(bytes(data))
        with self.assertRaises(shelf.ShelfError):
            shelf.unshelve_one(self.manifest(path))
        self.assertFalse(path.exists())
        self.assertTrue(self.manifest(path).exists())
        self.assertEqual([p.name for p in self.root.iterdir() if p.name.startswith(".")], [])

    def test_recent_open_and_unusual_files_are_left_alone(self):
        recent = self.project("recent.tsrct", age=time.time())
        self.assertEqual(self.shelve(recent)[0], "skipped")
        busy = self.project("busy.tsrct")
        self.assertEqual(self.shelve(busy, busy=[str(busy)])[0], "skipped")
        broken = self.root / "broken.tsrct"
        broken.write_bytes(b"not a zip" * 10_000)
        os.utime(broken, (OLD, OLD))
        self.assertEqual(self.shelve(broken)[0], "skipped")
        tiny = self.root / "tiny.tsrct"
        with zipfile.ZipFile(tiny, "w") as archive:
            archive.writestr("document.json", "{}")
        os.utime(tiny, (OLD, OLD))
        self.assertEqual(self.shelve(tiny)[0], "skipped")
        for path in (recent, busy, broken, tiny):
            self.assertTrue(path.exists())

    def test_a_project_that_cannot_be_removed_stays_as_it_was(self):
        path = self.project("locked.tsrct")
        digest = sha(path)
        real_unlink = os.unlink

        def refuse(target, *args, **kwargs):
            if Path(target) == path:
                raise PermissionError("in use")
            return real_unlink(target, *args, **kwargs)

        with mock.patch("shelf.os.unlink", side_effect=refuse):
            outcome, reason, _, _ = self.shelve(path)
        self.assertEqual(outcome, "skipped")
        self.assertIn("in use", reason)
        self.assertEqual(sha(path), digest)
        self.assertFalse(self.manifest(path).exists())

    def test_unshelve_never_replaces_an_existing_file_and_can_rebuild_a_copy(self):
        path = self.project("keep.tsrct")
        digest = sha(path)
        self.shelve(path)
        copy = self.root / "copy.tsrct"
        shelf.unshelve_one(self.manifest(path), to=copy)
        self.assertEqual(sha(copy), digest)
        self.assertTrue(self.manifest(path).exists())   # a copy keeps the project shelved
        path.write_bytes(b"someone made a new file here")
        with self.assertRaises(shelf.ShelfError):
            shelf.unshelve_one(self.manifest(path))
        self.assertEqual(path.read_bytes(), b"someone made a new file here")

    def test_command_line_shelves_verifies_and_explains_the_store(self):
        path = self.project("cli.tsrct")
        before = sha(path)
        with mock.patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(shelf.main(["shelve", str(self.root), "--dry-run"]), 0)
        self.assertEqual(sha(path), before)
        self.assertFalse(self.manifest(path).exists())
        with mock.patch("sys.stdout", new=io.StringIO()) as out:
            self.assertEqual(shelf.main(["shelve", str(self.root)]), 0)
            self.assertEqual(shelf.main(["verify", str(self.root)]), 0)
        self.assertIn('"verified": 1', out.getvalue())
        self.assertTrue((self.root / "store" / "README.md").exists())
        with mock.patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(shelf.main(["unshelve", str(path)]), 0)
        self.assertEqual(sha(path), before)


if __name__ == "__main__":
    unittest.main()
