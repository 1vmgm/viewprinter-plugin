#!/usr/bin/env python3
"""Which tools this machine has for each content task, and what the user decided about the
missing ones, so an agent can recommend a tool when a task needs it without repeating itself.

It runs each local program's --version and nothing else. Accounts and connectors are the
agent's to see in its own tools and the project's keys; see references/tools.md. Only
remember and introduced write anything: the user's answers, in ~/ViewPrinter/tools.json.

  python3 tools.py check [--json]               what is ready, and when to mention the rest
  python3 tools.py introduced                   the one-time setup summary has been given
  python3 tools.py remember <tool> not-now      quiet for 14 days, then 30, then 60
  python3 tools.py remember <tool> never        stop mentioning it until the user asks
  python3 tools.py remember <tool> reset        forget the answer
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

# Quiet periods after each "not now": a tool the user keeps declining is raised less often.
SNOOZE_DAYS = (14, 30, 60)

# Local programs are found on this machine; accounts and connectors only the agent can see.
TOOLS = [
    {"id": "tesseract", "task": "Video editing, motion graphics and sound design", "tool": "Tesseract by Mirage",
     "local": True, "unlocks": "cuts footage into finished videos with motion graphics and sound, as editable projects",
     "install": "npx skills add mirage-hq/Tesseract, then follow its installation guide to set up the matching tsrct CLI"},
    {"id": "ffmpeg", "task": "Converting and trimming media; covers and frames", "tool": "ffmpeg and ffprobe",
     "local": True, "unlocks": "converts, trims and inspects media and pulls covers and frames", "install": None},
    {"id": "argent", "task": "App demos and screen recordings", "tool": "Argent", "local": True,
     "unlocks": "records real app demos on an iOS Simulator, Android emulator or browser",
     "install": "npx @swmansion/argent@latest init -y (iOS needs Xcode; Android needs an emulator from Android Studio)"},
    {"id": "browser", "task": "Checking that review media plays", "tool": "Chrome, Chromium or Microsoft Edge",
     "local": True, "unlocks": "plays every review file before handoff", "install": "install Google Chrome, Chromium or Microsoft Edge"},
    {"id": "node", "task": "Installing Tesseract's skills and Argent", "tool": "Node.js (npx)", "local": True,
     "unlocks": "runs the installers for Tesseract and Argent", "install": "install Node.js from https://nodejs.org"},
    {"id": "higgsfield", "task": "Generating video and images", "tool": "Higgsfield", "local": False,
     "unlocks": "generates people, scenes, b-roll and motion transfer",
     "install": "a Higgsfield account with credits, connected as an MCP connector or with an API key"},
    {"id": "fal", "task": "Generating and upscaling images and video", "tool": "fal", "local": False,
     "unlocks": "generates and edits images and video, and upscales them",
     "install": "a fal account with credits and its API key (FAL_KEY)"},
    {"id": "elevenlabs", "task": "Voiceover and captions from speech", "tool": "ElevenLabs", "local": False,
     "unlocks": "records voiceover and transcribes speech for captions",
     "install": "an ElevenLabs API key, or fal's ElevenLabs models"},
    {"id": "gemini", "task": "Breaking down a video", "tool": "Gemini API", "local": False,
     "unlocks": "reports a video's hook, timing, on-screen text and when the product appears",
     "install": "a Gemini API key in GEMINI_API_KEY"},
    {"id": "scrape-creators", "task": "Research: creators, posts and transcripts", "tool": "Scrape Creators",
     "local": False, "unlocks": "pulls creators' posts, profiles and transcripts for research",
     "install": "a Scrape Creators account and API key"},
    {"id": "memelord", "task": "Meme templates", "tool": "Memelord", "local": False,
     "unlocks": "finds current meme templates", "install": "a Memelord account (memelord.com)"},
    {"id": "mobbin", "task": "App and UI design references", "tool": "Mobbin", "local": False,
     "unlocks": "finds real app screens and flows to reference", "install": "a Mobbin account and its MCP connector"},
]
IDS = [tool["id"] for tool in TOOLS]


def state_path():
    return Path.home() / "ViewPrinter" / "tools.json"


def tesseract_paths(platform=sys.platform, env=os.environ, home=None):
    """Where Tesseract's installer puts its CLI, before PATH. Its name is tsrct: the program
    called tesseract is an unrelated text-recognition (OCR) engine."""
    home = Path(home) if home else Path.home()
    if platform == "darwin":
        return [home / "Library/Application Support/Tesseract/bin/tsrct"]
    if platform.startswith("win"):
        return [Path(env["LOCALAPPDATA"]) / "Tesseract/bin/tsrct.cmd"] if env.get("LOCALAPPDATA") else []
    return [Path(env.get("XDG_DATA_HOME") or home / ".local/share") / "Tesseract/bin/tsrct"]


def browser_paths(platform=sys.platform, env=os.environ, home=None):
    home = Path(home) if home else Path.home()
    if platform == "darwin":
        apps = ["Google Chrome.app/Contents/MacOS/Google Chrome", "Chromium.app/Contents/MacOS/Chromium",
                "Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
        return [folder / app for folder in (Path("/Applications"), home / "Applications") for app in apps]
    if platform.startswith("win"):
        roots = [env.get(name) for name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        apps = ["Google/Chrome/Application/chrome.exe", "Chromium/Application/chrome.exe",
                "Microsoft/Edge/Application/msedge.exe"]
        return [Path(root) / app for root in roots if root for app in apps]
    return []


def found(paths, names):
    """The first existing path, else the first name on PATH."""
    for path in paths:
        if path.is_file():
            return str(path)
    for name in names:
        if shutil.which(name):
            return shutil.which(name)
    return None


def version(program):
    """The first line of a command-line program's --version, or "" if it gives none."""
    try:
        result = subprocess.run([program, "--version"], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=20)
    except (OSError, subprocess.SubprocessError):
        return ""
    text = (result.stdout or result.stderr).strip()
    return text.splitlines()[0].split(" Copyright")[0] if text else ""


def ffmpeg_install(platform=sys.platform):
    if platform == "darwin":
        return "brew install ffmpeg"
    if platform.startswith("win"):
        return "winget install Gyan.FFmpeg"
    return "install ffmpeg with the system package manager, such as: sudo apt install ffmpeg"


def argent_paths(cwd, platform=sys.platform):
    """A project-local Argent install, which its MCP config runs instead of a global one."""
    name = "argent.cmd" if platform.startswith("win") else "argent"
    return [Path(cwd) / "node_modules/.bin" / name]


def locate(platform=sys.platform, env=os.environ, home=None, cwd=None):
    """Each local program: (path or None, detail, note). A browser is located but never run:
    on Windows its --version can open a window."""
    tsrct = found(tesseract_paths(platform, env, home), ["tsrct"])
    ocr = not tsrct and shutil.which("tesseract")
    ffmpeg = shutil.which("ffmpeg") if shutil.which("ffprobe") else None
    browser = found(browser_paths(platform, env, home),
                    ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge"])
    places = {"tesseract": tsrct, "ffmpeg": ffmpeg, "argent": found(argent_paths(cwd or Path.cwd(), platform), ["argent"]),
              "browser": browser, "node": shutil.which("npx")}
    notes = {"tesseract": "The tesseract on PATH is an unrelated OCR engine, not the video editor." if ocr else "",
             "argent": "Argent's MCP tools in the agent's tool list also count as installed."}
    result = {}
    for tool, path in places.items():
        if tool == "node":  # npx --version is npm's version; say which Node.js it is
            named = path and version(shutil.which("node") or "")
            detail = f"Node.js {named}; npx at {path}" if named else path
        else:
            named = path and tool != "browser" and version(path)
            detail = f"{named} at {path}" if named else path
        result[tool] = (path, detail or "not found", notes.get(tool, ""))
    return result


def read_state(path):
    try:
        state = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def write_state(path, state):
    """Replace the file whole, so an interrupted write never leaves half a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
            handle.write("\n")
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def suggestion(ready, answer, now):
    """When to mention a tool: "ready", "offer" (when a task needs it), "quiet" or "never"."""
    if ready:
        return "ready"
    if answer.get("decision") == "never":
        return "never"
    if answer.get("decision") == "not-now":
        try:
            if now < datetime.fromisoformat(answer["until"]):
                return "quiet"
        except (KeyError, TypeError, ValueError):
            pass
    return "offer"


def check(state=None, now=None, platform=sys.platform, env=os.environ, home=None, cwd=None):
    """Every tool with whether it is ready (None when only the agent can tell), when to
    mention it, what it unlocks and how to install it."""
    state = read_state(state_path() if state is None else state)
    now = now or datetime.now(timezone.utc)
    places = locate(platform, env, home, cwd)
    answers = state.get("tools") if isinstance(state.get("tools"), dict) else {}
    tools = []
    for tool in TOOLS:
        path, detail, note = places.get(tool["id"], (None, "", ""))
        ready = bool(path) if tool["local"] else None
        answer = answers.get(tool["id"]) if isinstance(answers.get(tool["id"]), dict) else {}
        entry = {"id": tool["id"], "task": tool["task"], "tool": tool["tool"], "ready": ready,
                 "mention": suggestion(ready, answer, now), "unlocks": tool["unlocks"],
                 "install": "" if ready else (tool["install"] or ffmpeg_install(platform))}
        if tool["local"]:
            entry.update(detail=detail, note="" if ready else note)
        if answer.get("decision"):
            entry["answer"] = {k: answer[k] for k in ("decision", "at", "until") if k in answer}
        tools.append(entry)
    return {"introduce": not state.get("introducedAt"), "tools": tools}


def remember(tool, decision, state=None, now=None):
    """Record the user's answer about a missing tool."""
    path = state_path() if state is None else Path(state)
    now = now or datetime.now(timezone.utc)
    data = read_state(path)
    if not isinstance(data.get("tools"), dict):
        data["tools"] = {}
    answers = data["tools"]
    if decision == "reset":
        answers.pop(tool, None)
    elif decision == "never":
        answers[tool] = {"decision": "never", "at": now.isoformat()}
    else:
        previous = answers.get(tool) if isinstance(answers.get(tool), dict) else {}
        count = previous.get("times")
        # A damaged count must not stop the answer being recorded.
        valid = isinstance(count, int) and not isinstance(count, bool) and count > 0
        times = count + 1 if previous.get("decision") == "not-now" and valid else 1
        days = SNOOZE_DAYS[min(times, len(SNOOZE_DAYS)) - 1]
        answers[tool] = {"decision": "not-now", "at": now.isoformat(),
                         "until": (now + timedelta(days=days)).isoformat(), "times": times}
    write_state(path, data)
    return answers.get(tool)


def introduced(state=None, now=None):
    """Record that the one-time setup summary was given; the first time is kept."""
    path = state_path() if state is None else Path(state)
    data = read_state(path)
    data.setdefault("introducedAt", (now or datetime.now(timezone.utc)).isoformat())
    write_state(path, data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state", type=Path, help="the answers file (default ~/ViewPrinter/tools.json)")
    commands = parser.add_subparsers(dest="command", required=True)
    report = commands.add_parser("check", help="what is ready, and when to mention the rest")
    report.add_argument("--json", action="store_true", help="print JSON for an agent")
    commands.add_parser("introduced", help="record that the one-time setup summary was given")
    answer = commands.add_parser("remember", help="record the user's answer about a missing tool")
    answer.add_argument("tool", choices=IDS)
    answer.add_argument("decision", choices=("not-now", "never", "reset"))
    args = parser.parse_args(argv)
    if args.command == "introduced":
        introduced(args.state)
        return 0
    if args.command == "remember":
        print(json.dumps(remember(args.tool, args.decision, args.state) or {"decision": "reset"}))
        return 0
    report = check(args.state)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    for tool in report["tools"]:
        status = {True: "ready", False: "missing", None: "account"}[tool["ready"]]
        line = f"{status:8} {tool['task']}: {tool['tool']}"
        if tool.get("detail") and tool["ready"]:
            line += f" ({tool['detail']})"
        if tool["install"]:
            line += f"\n         unlocks: {tool['unlocks']}\n         install: {tool['install']}"
        if tool["mention"] in ("quiet", "never"):
            line += f"\n         answer: {tool['answer']['decision']}" + (f" until {tool['answer']['until'][:10]}" if tool["mention"] == "quiet" else "")
        if tool.get("note"):
            line += f"\n         note: {tool['note']}"
        print(line)
    print("\nAccounts and connectors can't be checked from here: look in your tools and the project's keys.")
    if report["introduce"]:
        print("The one-time setup summary hasn't been given on this machine yet.")
    return 0


if __name__ == "__main__":
    # Agents read this through a pipe, which on Windows defaults to the system code page.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors=stream.errors)
    sys.exit(main())
