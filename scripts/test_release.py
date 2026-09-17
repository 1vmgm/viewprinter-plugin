"""Regression checks for release contents and coordinated version updates."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

import yaml

from release_files import PLUGIN_FILES
from set_version import JSON_FILES

SOURCE = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='viewprinter-regression-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'viewprinter'
        shutil.copytree(SOURCE, self.root,
                        ignore=shutil.ignore_patterns('.git', 'dist', '__pycache__', '.venv'))

    def run_script(self, name, *args, success=True):
        result = subprocess.run([sys.executable, str(self.root / 'scripts' / name), *args],
                                cwd=self.root, capture_output=True, text=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def versions(self):
        versions = [json.loads((self.root / name).read_text())['version'] for name in JSON_FILES]
        text = (self.root / 'clawhub/entry.md').read_text()
        versions.append(yaml.safe_load(text.split('---', 2)[1])['metadata']['version'])
        return versions

    def test_only_approved_files_are_archived(self):
        marker = b'LOCAL_ONLY_REGRESSION_MARKER'
        for name in ['scripts/.DS_Store', 'scripts/private.txt', 'docs/private-notes.md']:
            (self.root / name).write_bytes(marker)
        outside = self.base / 'outside.txt'
        outside.write_bytes(marker)
        (self.root / 'assets/unlisted-link.txt').symlink_to(outside)
        self.run_script('build.py')
        version = self.versions()[0]
        with zipfile.ZipFile(self.root / 'dist' / f'viewprinter-{version}.zip') as archive:
            self.assertEqual(set(archive.namelist()), {f'viewprinter/{name}' for name in PLUGIN_FILES})
            for name in archive.namelist():
                self.assertNotEqual(archive.read(name), marker)

    def test_declared_file_symlink_is_rejected(self):
        path = self.root / 'skills/viewprinter/references/rules/media-upload.md'
        outside = self.base / 'external-skill.md'
        outside.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(outside)
        result = self.run_script('build.py', success=False)
        self.assertIn('Symlink', result.stderr)
        self.assertFalse((self.root / 'dist').exists())
        self.assertFalse((self.root / 'clawhub/dist').exists())

    def test_declared_parent_symlink_is_rejected(self):
        outside = self.base / 'external-skills'
        shutil.move(self.root / 'skills', outside)
        (self.root / 'skills').symlink_to(outside, target_is_directory=True)
        result = self.run_script('build.py', success=False)
        self.assertIn('Symlink', result.stderr)

    def test_output_symlinks_do_not_write_outside(self):
        outside = self.base / 'external-output'
        outside.mkdir()
        for name in ['dist', 'clawhub/dist', 'dist/release.json',
                     f'dist/viewprinter-{self.versions()[0]}.zip']:
            with self.subTest(path=name):
                path = self.root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.symlink_to(outside, target_is_directory=True)
                result = self.run_script('build.py', success=False)
                self.assertIn('Symlink', result.stderr)
                self.assertEqual(list(outside.iterdir()), [])
                path.unlink()

    def test_release_version_updates_every_source(self):
        body_before = (self.root / 'clawhub/entry.md').read_text().split('---', 2)[2]
        self.run_script('set_version.py', '2.3.4-rc.1+build.2')
        self.assertEqual(self.versions(), ['2.3.4-rc.1+build.2'] * 5)
        self.assertEqual((self.root / 'clawhub/entry.md').read_text().split('---', 2)[2], body_before)
        self.run_script('validate.py')
        self.run_script('build.py')
        self.assertTrue((self.root / 'dist/viewprinter-2.3.4-rc.1+build.2.zip').is_file())

    def test_dev_version_replaces_suffix_and_keeps_all_sources_aligned(self):
        self.run_script('set_version.py', '1.2.0-rc.1+previous')
        self.run_script('set_version.py', '--dev')
        first = self.versions()[0]
        self.run_script('set_version.py', '--dev')
        second = self.versions()[0]
        self.assertNotEqual(first, second)
        self.assertRegex(second, r'^1\.2\.0-rc\.1\+codex\.[0-9]+$')
        self.assertEqual(self.versions(), [second] * 5)
        self.run_script('validate.py')

    def test_bad_input_never_partly_updates_versions(self):
        names = (*JSON_FILES, 'clawhub/frontmatter.md', 'clawhub/entry.md')
        before = {name: (self.root / name).read_bytes() for name in names}
        for version in ['../outside', '01.2.3', '1.2.3-01', '1.2', '1.2.3\n']:
            with self.subTest(version=version):
                self.run_script('set_version.py', version, success=False)
                self.assertEqual({name: (self.root / name).read_bytes() for name in names}, before)
        # Corrupt the AUTHORED frontmatter, not the generated SKILL.md. The
        # version lives in frontmatter.md now; SKILL.md is rebuilt from it, so
        # damaging the generated file proves nothing about aborting the write.
        (self.root / 'clawhub/frontmatter.md').write_text('Missing frontmatter\n')
        self.run_script('set_version.py', '2.0.0', success=False)
        self.assertEqual({name: (self.root / name).read_bytes() for name in JSON_FILES},
                         {name: before[name] for name in JSON_FILES})

    def test_extracted_package_reproduces_archives(self):
        self.run_script('build.py')
        first = json.loads((self.root / 'dist/release.json').read_text())['artifacts']
        self.run_script('build.py')
        self.assertEqual(json.loads((self.root / 'dist/release.json').read_text())['artifacts'], first)
        extracted = self.base / 'extracted'
        with zipfile.ZipFile(self.root / 'dist' / first[0]['file']) as archive:
            archive.extractall(extracted)
            # zipfile.extractall drops the stored mode; unzip(1) restores it.
            # Without this the extracted tree has a preflight it cannot run, and
            # the test would be asserting a property of Python rather than of
            # the package we ship.
            for info in archive.infolist():
                mode = info.external_attr >> 16
                if mode:
                    (extracted / info.filename).chmod(mode & 0o777)
        self.root = extracted / 'viewprinter'
        self.run_script('build.py')
        self.assertEqual(json.loads((self.root / 'dist/release.json').read_text())['artifacts'], first)


if __name__ == '__main__':
    unittest.main()
