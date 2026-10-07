#!/usr/bin/env python3
"""Run with: python3 -m unittest discover -s scripts -p 'test_tools.py'."""

import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

import tools

NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


def fake_program(folder, name, line):
    """A program that prints line for --version: a shell script, or a .cmd on Windows."""
    folder.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        path = folder / (name + ".cmd")
        path.write_text("@echo " + line + "\r\n", encoding="utf-8")
    else:
        path = folder / name
        path.write_text("#!/bin/sh\necho '" + line + "'\n", encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


class ToolsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name).resolve()
        self.state = self.home / "ViewPrinter/tools.json"
        self.browser_paths = tools.browser_paths
        # Nothing on PATH and no system browser folders: the machine running the tests is not the subject.
        for target, value in ((tools.shutil, "which"), (tools, "browser_paths")):
            patcher = patch.object(target, value, return_value=None if value == "which" else [])
            patcher.start()
            self.addCleanup(patcher.stop)

    def check(self, **kwargs):
        report = tools.check(self.state, kwargs.pop("now", NOW), kwargs.pop("platform", "linux"), kwargs.pop("env", {}),
                             self.home, kwargs.pop("cwd", self.home))
        return report, {tool["id"]: tool for tool in report["tools"]}

    def test_tesseract_is_found_where_its_installer_puts_it_on_each_system(self):
        self.assertEqual(tools.tesseract_paths("darwin", {}, self.home),
                         [self.home / "Library/Application Support/Tesseract/bin/tsrct"])
        self.assertEqual(tools.tesseract_paths("win32", {"LOCALAPPDATA": "D:/AppData/Local"}, self.home),
                         [Path("D:/AppData/Local/Tesseract/bin/tsrct.cmd")])
        self.assertEqual(tools.tesseract_paths("linux", {}, self.home), [self.home / ".local/share/Tesseract/bin/tsrct"])
        self.assertEqual(tools.tesseract_paths("linux", {"XDG_DATA_HOME": "/data"}, self.home),
                         [Path("/data/Tesseract/bin/tsrct")])

    def test_installed_tesseract_off_path_is_ready_with_its_version(self):
        platform = "win32" if os.name == "nt" else "linux"
        env = {"LOCALAPPDATA": str(self.home)} if os.name == "nt" else {"XDG_DATA_HOME": str(self.home)}
        program = fake_program(self.home / "Tesseract/bin", "tsrct", "tsrct 9.9.9")
        _, found = self.check(platform=platform, env=env)
        self.assertEqual((found["tesseract"]["ready"], found["tesseract"]["mention"]), (True, "ready"))
        self.assertEqual(found["tesseract"]["detail"], "tsrct 9.9.9 at " + str(program))
        self.assertEqual(found["tesseract"]["install"], "")

    def test_ocr_tesseract_is_not_mistaken_for_the_video_editor(self):
        on_path = {"tesseract": "/usr/local/bin/tesseract"}
        with patch.object(tools.shutil, "which", side_effect=on_path.get):
            _, found = self.check()
        self.assertFalse(found["tesseract"]["ready"])
        self.assertIn("npx skills add mirage-hq/Tesseract", found["tesseract"]["install"])
        self.assertIn("OCR", found["tesseract"]["note"])

    def test_every_missing_tool_says_what_it_unlocks_and_how_to_install_it(self):
        _, found = self.check(platform="darwin")
        for tool in found.values():
            self.assertTrue(tool["unlocks"] and tool["install"], tool["id"])
            self.assertEqual(tool["mention"], "offer")
        self.assertEqual(found["ffmpeg"]["install"], "brew install ffmpeg")
        self.assertEqual(tools.ffmpeg_install("win32"), "winget install Gyan.FFmpeg")
        # Accounts and connectors are the agent's to see.
        self.assertEqual({t["id"] for t in found.values() if t["ready"] is None},
                         {"higgsfield", "fal", "elevenlabs", "gemini", "scrape-creators", "memelord", "mobbin"})

    def test_argent_installed_in_the_project_counts_and_a_connector_is_mentioned(self):
        _, found = self.check()
        self.assertFalse(found["argent"]["ready"])
        self.assertIn("MCP", found["argent"]["note"])
        platform = "win32" if os.name == "nt" else "linux"
        project = self.home / "project"
        fake_program(project / "node_modules/.bin", "argent", "0.27.0")
        _, found = self.check(platform=platform, cwd=project)
        self.assertEqual((found["argent"]["ready"], found["argent"]["mention"]), (True, "ready"))
        self.assertTrue(found["argent"]["detail"].startswith("0.27.0 at "))

    def test_node_reports_its_own_version_not_npms(self):
        npx = fake_program(self.home / "bin", "npx", "11.0.0")
        node = fake_program(self.home / "bin", "node", "v24.0.0")
        with patch.object(tools.shutil, "which", side_effect={"npx": str(npx), "node": str(node)}.get):
            _, found = self.check()
        self.assertEqual(found["node"]["detail"], f"Node.js v24.0.0; npx at {npx}")

    def test_a_browser_is_located_but_never_run(self):
        browser = self.home / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        self.assertIn(browser, self.browser_paths("darwin", {}, self.home))
        browser.parent.mkdir(parents=True)
        browser.write_text("", encoding="utf-8")
        with patch.object(tools, "browser_paths", return_value=[browser]), patch.object(tools, "version") as probe:
            _, found = self.check(platform="darwin")
        self.assertEqual((found["browser"]["ready"], found["browser"]["detail"]), (True, str(browser)))
        self.assertFalse([c for c in probe.call_args_list if c.args[0] == str(browser)])

    def test_setup_summary_is_offered_once_per_machine(self):
        self.assertTrue(self.check()[0]["introduce"])
        tools.introduced(self.state, NOW)
        tools.introduced(self.state, NOW + timedelta(days=3))
        self.assertFalse(self.check()[0]["introduce"])
        self.assertEqual(json.loads(self.state.read_text(encoding="utf-8"))["introducedAt"], NOW.isoformat())

    def test_not_now_stays_quiet_for_longer_each_time(self):
        for times, days in enumerate((14, 30, 60, 60), start=1):
            asked = NOW + timedelta(days=200 * times)
            answer = tools.remember("tesseract", "not-now", self.state, asked)
            self.assertEqual((answer["times"], answer["until"]), (times, (asked + timedelta(days=days)).isoformat()))
            self.assertEqual(self.check(now=asked + timedelta(days=days - 1))[1]["tesseract"]["mention"], "quiet")
            self.assertEqual(self.check(now=asked + timedelta(days=days))[1]["tesseract"]["mention"], "offer")

    def test_never_and_reset_and_answers_for_accounts(self):
        tools.remember("scrape-creators", "never", self.state, NOW)
        tools.remember("gemini", "not-now", self.state, NOW)
        _, found = self.check(now=NOW + timedelta(days=365))
        self.assertEqual((found["scrape-creators"]["mention"], found["gemini"]["mention"]), ("never", "offer"))
        tools.remember("scrape-creators", "reset", self.state, NOW)
        self.assertEqual(self.check()[1]["scrape-creators"]["mention"], "offer")
        # A new "not now" after a reset starts again at the shortest pause.
        tools.remember("gemini", "reset", self.state, NOW)
        self.assertEqual(tools.remember("gemini", "not-now", self.state, NOW)["times"], 1)

    def test_a_damaged_answers_file_costs_at_most_one_extra_reminder(self):
        self.state.parent.mkdir(parents=True)
        self.state.write_text("{not json", encoding="utf-8")
        report, found = self.check()
        self.assertTrue(report["introduce"])
        self.assertEqual(found["argent"]["mention"], "offer")
        tools.remember("argent", "not-now", self.state, NOW)
        self.assertEqual(self.check()[1]["argent"]["mention"], "quiet")
        for damaged in ("2", None, 2.0, -5, True):
            self.state.write_text(json.dumps({"tools": {"argent": {"decision": "not-now", "times": damaged}}}), encoding="utf-8")
            self.assertEqual(tools.remember("argent", "not-now", self.state, NOW)["times"], 1, damaged)

    def test_command_line_reports_and_records(self):
        output = io.StringIO()
        # The command line looks at the real machine; keep this test off its programs.
        with contextlib.redirect_stdout(output), patch.object(tools, "locate", return_value={}):
            self.assertEqual(tools.main(["--state", str(self.state), "remember", "mobbin", "never"]), 0)
            self.assertEqual(tools.main(["--state", str(self.state), "check", "--json"]), 0)
        report = json.loads(output.getvalue().split("\n", 1)[1])
        self.assertEqual(len(report["tools"]), len(tools.TOOLS))
        self.assertEqual(next(t for t in report["tools"] if t["id"] == "mobbin")["mention"], "never")
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            tools.main(["remember", "light-reel", "never"])

    def test_the_reference_page_names_every_tool(self):
        page = (Path(tools.__file__).resolve().parents[1] / "references/tools.md").read_text(encoding="utf-8")
        for tool in tools.TOOLS:
            self.assertIn(tool["tool"].split()[0].strip(","), page)


if __name__ == "__main__":
    unittest.main()
