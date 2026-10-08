#!/usr/bin/env python3
"""Write what each original in the source archive actually shows, with Gemini, so later work
can find it and ViewPrinter gets a real description when the original is saved there.

A summary is a few plain sentences about the file itself: who and what appears, the setting
and the action, on-screen text, and for audio its genre, mood, tempo and instruments. It is
recorded in the archive catalog as a note, with the tags Gemini suggests and a receipt: the
model, the tokens and what they cost. `archive.py find --text` searches summaries, and
`archive.py upload-list` uses one as the description it drafts for media_save.

Gemini gets a small copy of each original, made with ffmpeg: video at most 960 pixels on its
long side and audio as mono MP3, the first two minutes of either; an image as it is, or as a
JPEG at most 1600 pixels on its long side when the file is large. That copy goes to Google:
ask the user first.

  python3 describe.py estimate --price-in USD --price-out USD [filters]
  python3 describe.py run --model MODEL --price-in USD --price-out USD --cap USD [filters]
                          [--workers N]

Prices are USD per million input and output tokens, from the provider's current pricing page;
a model's price changes, and nothing here assumes one. `run` stops starting new requests once
this run has spent --cap; requests already under way finish. The filters are upload-list's:
--format, --batch, --status and --tag, or --id for named originals; --root and --project as
archive.py. By default an original already in ViewPrinter (--stored to include it) or
already described (--again to describe it anew) is left out.

The key is GEMINI_API_KEY, GOOGLE_API_KEY or GOOGLE_GENERATIVE_AI_API_KEY, from the
environment, a keys file named with `tools.py keys add`, or the project's .env or .env.local.
It goes only to the API, in a header, and is never printed or recorded.
VIEWPRINTER_GEMINI_BASE replaces the API address, for tests.
"""

import argparse
import base64
import concurrent.futures
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import archive
import tools

BASE_ENVIRONMENT = "VIEWPRINTER_GEMINI_BASE"
BASE = "https://generativelanguage.googleapis.com/v1beta"
KEY_NAMES = next(tool["keys"] for tool in tools.TOOLS if tool["id"] == "gemini")
SECONDS = 120  # how much of a video or audio file Gemini sees and hears
INLINE_LIMIT = 14 * 1024 * 1024  # a request carries at most 20 MB once the copy is encoded
IMAGE_AS_IS = 3500000
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
# For an estimate only; every reply reports the tokens actually counted. Gemini counts about
# 300 tokens a second of video with its sound, 32 a second of audio and 258 for each
# 768-pixel tile of an image; the prompt adds about 1,500 and a reply about 400.
VIDEO_TOKENS, AUDIO_TOKENS, TILE_TOKENS, PROMPT_TOKENS, REPLY_TOKENS = 300, 32, 258, 1500, 400
ATTEMPTS = 4
RETRY_SECONDS = 5
SUMMARY_LIMIT = 1000
TAG_LIMIT = 8

GUIDE = {
    "video": "Describe who appears (how many, apparent age range, hair, clothing, expression), what they do in "
             "order, the setting, camera framing and movement, any on-screen text quoted exactly, and the sound "
             "(speech in a few words, music, effects or silence).",
    "image": "Describe the subject, the scene, the composition and any text quoted exactly. If it is a "
             "recognizable meme template, give its common name and how the joke works, and note empty space "
             "meant for captions. For a product photo, name the product and quote the packaging text.",
    "audio": "For music: genre, mood, approximate tempo in BPM, energy, main instruments, vocals (none, male or "
             "female, language), and how this excerpt opens and develops. Do not transcribe lyrics. For a sound "
             "effect: what it sounds like, how long it is and what edit moment it suits. For speech: who speaks, "
             "in general terms, and what it is about.",
}

PROMPT = """You are cataloguing an original media file for a content team's asset library. People will search the
library later to reuse this file, so describe what is actually in this file, concretely and searchably.

How the file was made (context only; it may not match the file, and the file wins):
{context}

{guide}

Rules: do not identify anyone from their face or appearance; name a person only when the name is shown or
spoken in the file or appears in the context above. Never guess ethnicity; give ages as a range. Do not
mention prompts, generation or the context unless it is visible or audible in the file. Plain sentences, no
marketing language.

Return JSON only, with exactly these keys:
{{"description": "one to three sentences, at most 450 characters, starting with: {opening}",
  "tags": ["3 to 8 short lowercase hyphenated search tags about the content: subjects, setting, mood, genre, template name; not the project or format name"],
  "on_screen_text": "the exact visible text, or an empty string"}}"""


class DescribeError(Exception):
    """Nothing was sent for this original, or no key or copy could be made."""


def redact(text, key):
    text = str(text)
    return text.replace(key, "[key]") if key else text


# ---------------------------------------------------------------------------
# Which originals


def select(root, project, format_id=None, batch=None, status=None, tags=(), ids=(), stored=False, again=False):
    """The originals to describe, as (asset, path), and how many were left out for each reason."""
    project_dir = archive.project_directory(root, project, create=False)
    state = archive.assets(project_dir)
    chosen, skipped = [], {}
    for identifier in ids:
        if identifier not in state:
            skipped["no such original"] = skipped.get("no such original", 0) + 1
    for asset in state.values():
        if ids:
            if asset["id"] not in ids:
                continue
        elif ((format_id and asset.get("format") != format_id) or (batch and asset.get("batchId") != batch)
              or (status and asset.get("status") != status)
              or not set(tags) <= set(archive.strings(asset.get("tags")))):
            continue
        path = archive.inside(project_dir, asset["path"])
        if asset.get("kind") not in archive.UPLOAD_KINDS:
            reason = "only video, images and audio are described"
        elif asset.get("summary") and not again:
            reason = "already described (pass --again)"
        elif asset.get("viewprinterMedia") and not (stored or ids):
            reason = "already in ViewPrinter (pass --stored)"
        elif not archive.intact(path, asset):
            reason = "not on this disk: released, missing or changed"
        else:
            chosen.append((asset, path))
            continue
        skipped[reason] = skipped.get(reason, 0) + 1
    return chosen, skipped


def probe(path):
    """(seconds, width, height) from ffprobe; None for anything it can't tell, or without it."""
    program = shutil.which("ffprobe")
    if not program:
        return None, None, None
    try:
        result = subprocess.run([program, "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height",
                                 "-of", "json", str(path)], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=120)
        data = json.loads(result.stdout or "{}")
    except (OSError, ValueError, subprocess.SubprocessError):
        return None, None, None
    try:
        seconds = float((data.get("format") or {}).get("duration"))
    except (TypeError, ValueError):
        seconds = None
    video = [s for s in data.get("streams") or [] if s.get("codec_type") == "video"]
    width, height = (video[0].get("width"), video[0].get("height")) if video else (None, None)
    return seconds, width, height


def image_tiles(width, height, size):
    """How many 768-pixel tiles Gemini counts for an image, after a large file is shrunk."""
    width, height = width or 1024, height or 1024
    if size > IMAGE_AS_IS and max(width, height) > 1600:
        scale = 1600.0 / max(width, height)
        width, height = width * scale, height * scale
    if max(width, height) <= 384:
        return 1
    return math.ceil(width / 768.0) * math.ceil(height / 768.0)


def estimate(chosen, price_in, price_out, model=None):
    """What describing the chosen originals should cost, before anything is sent."""
    kinds, unknown, tokens_in = {}, 0, 0
    for asset, path in chosen:
        seconds, width, height = probe(path)
        entry = kinds.setdefault(asset["kind"], {"count": 0, "seconds": 0.0})
        entry["count"] += 1
        if asset["kind"] == "image":
            unknown += width is None
            tokens = TILE_TOKENS * image_tiles(width, height, path.stat().st_size)
        else:
            unknown += seconds is None
            used = min(seconds if seconds is not None else SECONDS, SECONDS)
            entry["seconds"] += used
            tokens = (VIDEO_TOKENS if asset["kind"] == "video" else AUDIO_TOKENS) * used
        tokens_in += tokens + PROMPT_TOKENS
    tokens_out = REPLY_TOKENS * len(chosen)
    report = {"originals": len(chosen),
              "byKind": {k: {"count": v["count"], "seconds": round(v["seconds"], 1)} for k, v in sorted(kinds.items())},
              "inputTokens": int(tokens_in), "outputTokens": tokens_out,
              "estimatedUsd": round((tokens_in * price_in + tokens_out * price_out) / 1e6, 4),
              "prices": {"inputPerMillion": price_in, "outputPerMillion": price_out}}
    if model:
        report["model"] = model
    if unknown:
        report["note"] = ("{} originals couldn't be measured (ffprobe missing or unreadable), so they are counted "
                          "at the most Gemini would see.".format(unknown))
    return report


# ---------------------------------------------------------------------------
# Describing one original


def proxy(asset, path, folder):
    """The bytes Gemini sees and their type: a small copy made with ffmpeg, or a small image as it is."""
    kind, suffix = asset["kind"], path.suffix.lower()
    if kind == "image" and path.stat().st_size <= IMAGE_AS_IS and suffix in IMAGE_TYPES:
        return path.read_bytes(), IMAGE_TYPES[suffix]
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise DescribeError("ffmpeg is needed to make the small copy Gemini gets of {}".format(
            "a large or unusual image" if kind == "image" else "video and audio"))
    out = Path(folder) / {"image": "copy.jpg", "video": "copy.mp4", "audio": "copy.mp3"}[kind]
    if kind == "image":
        scale = "scale='if(gte(iw,ih),min(1600,iw),-2)':'if(gte(iw,ih),-2,min(1600,ih))'"
        command = [ffmpeg, "-v", "error", "-y", "-i", str(path), "-vf", scale, "-frames:v", "1", "-q:v", "3", str(out)]
    elif kind == "video":
        scale = "scale='if(gte(iw,ih),min(960,iw),-2)':'if(gte(iw,ih),-2,min(960,ih))'"
        command = [ffmpeg, "-v", "error", "-y", "-i", str(path), "-t", str(SECONDS), "-vf", scale, "-c:v", "libx264",
                   "-preset", "veryfast", "-crf", "30", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "64k", "-ac", "1",
                   "-movflags", "+faststart", str(out)]
    else:
        command = [ffmpeg, "-v", "error", "-y", "-i", str(path), "-t", str(SECONDS), "-vn", "-ac", "1", "-ar", "32000",
                   "-b:a", "96k", str(out)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                timeout=900)
    except (OSError, subprocess.SubprocessError) as error:
        raise DescribeError("ffmpeg could not make the small copy: {}".format(error))
    if result.returncode != 0 or not out.is_file():
        raise DescribeError("ffmpeg could not make the small copy: " + (result.stderr or "").strip()[-300:])
    return out.read_bytes(), {"image": "image/jpeg", "video": "video/mp4", "audio": "audio/mpeg"}[kind]


def shape(width, height):
    if not (width and height):
        return None
    return "vertical" if height > width else "horizontal" if width > height else "square"


def context(project, asset, seconds, width, height):
    lines = ["- Project: {}; format: {}; kind: {}; status: {}".format(
        project, asset.get("format"), asset.get("kind"), asset.get("status"))]
    made = " ".join(str(asset[k]) for k in ("origin", "tool", "model") if asset.get(k))
    if made:
        lines.append("- Made or found: " + made)
    for key, label in (("title", "Title"), ("artist", "Artist"), ("originalName", "Original file name")):
        if asset.get(key):
            lines.append("- {}: {}".format(label, asset[key]))
    if isinstance(asset.get("prompt"), str) and asset["prompt"].strip():
        lines.append("- Generation prompt (excerpt): " + asset["prompt"].strip()[:1500])
    tags = archive.strings(asset.get("tags"))
    if tags:
        lines.append("- Existing tags: " + ", ".join(tags))
    if seconds:
        lines.append("- Duration: {:.1f} s".format(seconds))
    if width and height:
        lines.append("- Frame: {}x{} ({})".format(width, height, shape(width, height)))
    return "\n".join(lines)


def opening(asset, seconds, width, height):
    label = {"video": "Video", "image": "Image", "audio": "Audio"}[asset["kind"]]
    if asset["kind"] == "image":
        return '"{}{}: ..."'.format(label, " ({}x{})".format(width, height) if width and height else "")
    parts = [label]
    if seconds:
        parts.append("{:.0f} s".format(seconds) if seconds >= 1 else "{:.0f} ms".format(seconds * 1000))
    if asset["kind"] == "video" and shape(width, height) in ("vertical", "horizontal"):
        parts.append(shape(width, height))
    return '"{}: ..."'.format(", ".join(parts))


def call(base, model, key, body):
    url = "{}/models/{}:generateContent".format(base.rstrip("/"), urllib.parse.quote(model, safe="-._"))
    request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                     headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.loads(response.read().decode("utf-8"))


def parse(answer):
    """The summary, slugged tags and on-screen text in a reply, or None when it has no usable JSON."""
    candidate = (answer.get("candidates") or [{}])[0] if isinstance(answer, dict) else {}
    parts = ((candidate or {}).get("content") or {}).get("parts") or []
    text = "".join(str(p.get("text", "")) for p in parts if isinstance(p, dict) and not p.get("thought")).strip()
    if text.startswith("```"):  # a fenced reply: drop the fence lines
        lines = text.split("\n")[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        reply = json.loads(text)
    except ValueError:
        return None
    if not (isinstance(reply, dict) and isinstance(reply.get("description"), str) and reply["description"].strip()):
        return None
    suggested = reply.get("tags") if isinstance(reply.get("tags"), list) else []
    tags = []
    for value in suggested:
        label = archive.tag(value) if isinstance(value, (str, int)) and not isinstance(value, bool) else None
        if label and label not in tags:
            tags.append(label)
    return {"summary": archive.fit(reply["description"], SUMMARY_LIMIT), "tags": tags[:TAG_LIMIT],
            "onScreenText": str(reply.get("on_screen_text") or "").strip()[:2000]}


def count(value):
    """A token count from a reply, or 0 when it isn't a whole number."""
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def describe_one(project, asset, path, model, price_in, price_out, key, base):
    """Ask Gemini about one original. Returns the reply's summary (or None) and what was spent."""
    seconds, width, height = probe(path)
    with tempfile.TemporaryDirectory(prefix="viewprinter-describe-") as folder:
        data, mime = proxy(asset, path, folder)
    if len(data) > INLINE_LIMIT:
        raise DescribeError("its copy is {:.1f} MB, more than one request carries".format(len(data) / 1e6))
    prompt = PROMPT.format(context=context(project, asset, seconds, width, height), guide=GUIDE[asset["kind"]],
                           opening=opening(asset, seconds, width, height))
    body = {"contents": [{"role": "user", "parts": [
                {"text": prompt}, {"inlineData": {"mimeType": mime, "data": base64.b64encode(data).decode("ascii")}}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json", "maxOutputTokens": 2048}}
    spent = {"inputTokens": 0, "outputTokens": 0, "costUsd": 0.0, "replies": 0, "model": model}
    problem = None
    for attempt in range(ATTEMPTS):
        last = attempt == ATTEMPTS - 1
        try:
            answer = call(base, model, key, body)
        except urllib.error.HTTPError as error:
            try:
                detail = error.read().decode("utf-8", "replace")[:300]
            except OSError:
                detail = ""
            problem = redact("HTTP {}: {}".format(error.code, detail.strip()), key)
            if error.code in (429, 500, 502, 503, 504) and not last:
                time.sleep(RETRY_SECONDS * (attempt + 1))
                continue
            break
        except (urllib.error.URLError, OSError, ValueError) as error:
            problem = redact(error, key)
            if not last:
                time.sleep(RETRY_SECONDS * (attempt + 1))
                continue
            break
        answer = answer if isinstance(answer, dict) else {}
        usage = answer.get("usageMetadata") if isinstance(answer.get("usageMetadata"), dict) else {}
        tokens_in = count(usage.get("promptTokenCount"))
        tokens_out = count(usage.get("candidatesTokenCount")) + count(usage.get("thoughtsTokenCount"))
        spent["inputTokens"] += tokens_in
        spent["outputTokens"] += tokens_out
        spent["costUsd"] += (tokens_in * price_in + tokens_out * price_out) / 1e6
        spent["replies"] += 1
        spent["model"] = answer.get("modelVersion") or model
        reply = parse(answer)
        if reply:
            return reply, spent
        problem = "the reply had no usable description"
    spent["failed"] = problem or "no reply"
    return None, spent


# ---------------------------------------------------------------------------
# Runs


def gemini_key(env=None, cwd=None):
    """The value of the first Gemini key set; raises when none is. Never print it."""
    env = os.environ if env is None else env
    files = tools.key_files(tools.read_state(tools.state_path()), cwd)
    found = tools.key_value(KEY_NAMES, env, files)
    if not found:
        raise DescribeError("No Gemini key: set GEMINI_API_KEY, or name the file the user keeps keys in with "
                            "tools.py keys add <file>")
    return found[1]


def spent_ever(root, project):
    """Everything describing this project's originals has cost, from the catalog's receipts."""
    total = 0.0
    for event in archive.read_log(archive.catalog(archive.project_directory(root, project, create=False))):
        receipt = event.get("summaryBy") if event.get("event") == "note" else None
        cost = receipt.get("costUsd") if isinstance(receipt, dict) else None
        if isinstance(cost, (int, float)) and not isinstance(cost, bool):
            total += cost
    return total


def receipt(spent, price_in, price_out):
    entry = {"tool": "gemini", "model": spent["model"], "inputTokens": spent["inputTokens"],
             "outputTokens": spent["outputTokens"], "costUsd": round(spent["costUsd"], 6),
             "pricePerMillion": {"input": price_in, "output": price_out}, "replies": spent["replies"],
             "at": archive.utc_now()}
    if spent.get("failed"):
        entry["failed"] = spent["failed"]
    return entry


def run(root, project, chosen, model, price_in, price_out, cap, workers=4, key=None, base=None, out=None):
    """Describe the chosen originals, recording each summary and receipt in the catalog."""
    out = out or sys.stdout
    key = key if key is not None else gemini_key()
    base = base or os.environ.get(BASE_ENVIRONMENT) or BASE
    lock, stop = threading.Lock(), threading.Event()
    totals = {"described": 0, "failed": 0, "skipped": {}, "runUsd": 0.0}

    def one(item):
        asset, path = item
        if stop.is_set():
            return asset["id"], "skipped", "the spending cap for this run was reached", 0.0
        try:
            reply, spent = describe_one(project, asset, path, model, price_in, price_out, key, base)
        except DescribeError as error:
            return asset["id"], "skipped", redact(error, key), 0.0
        record = {"summaryBy": receipt(spent, price_in, price_out)}
        if reply:
            record["summary"] = reply["summary"]
            if reply["tags"]:
                record["tags"] = reply["tags"]
            if reply["onScreenText"]:
                record["onScreenText"] = reply["onScreenText"]
        with lock:
            if reply or spent["replies"]:  # a reply that couldn't be used was still paid for
                archive.note(root, project, asset["id"], record)
            totals["runUsd"] += spent["costUsd"]
            if totals["runUsd"] >= cap:
                stop.set()
        if reply:
            return asset["id"], "described", reply["summary"], spent["costUsd"]
        return asset["id"], "failed", redact(spent["failed"], key), spent["costUsd"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for identifier, outcome, text, cost in pool.map(one, chosen):
            if outcome == "skipped":
                totals["skipped"][text] = totals["skipped"].get(text, 0) + 1
            else:
                totals[outcome] += 1
            print("{:9} {}  ${:.4f}  {}".format(outcome, identifier, cost, " ".join(text.split())[:120]), file=out)
    totals["runUsd"] = round(totals["runUsd"], 6)
    totals["capUsd"] = cap
    totals["allTimeUsd"] = round(spent_ever(root, project), 6)
    return totals


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    def command(name, help_text):
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument("--root", help="Archive root (default: as archive.py)")
        sub.add_argument("--project", help="Project ID (default: from project memory)")
        sub.add_argument("--format")
        sub.add_argument("--batch")
        sub.add_argument("--status", choices=archive.STATUSES)
        sub.add_argument("--tag", action="append", default=[])
        sub.add_argument("--id", action="append", default=[], help="Describe this original, whatever the filters")
        sub.add_argument("--stored", action="store_true", help="Include originals ViewPrinter already keeps")
        sub.add_argument("--again", action="store_true", help="Describe originals that already have a summary")
        sub.add_argument("--price-in", type=float, required=True,
                         help="USD per million input tokens, from the provider's current pricing")
        sub.add_argument("--price-out", type=float, required=True,
                         help="USD per million output tokens, from the provider's current pricing")
        return sub

    command("estimate", "What describing the chosen originals should cost").add_argument("--model")
    sub = command("run", "Describe the chosen originals and record each summary in the catalog")
    sub.add_argument("--model", required=True, help="The Gemini model, as its API names it")
    sub.add_argument("--cap", type=float, required=True, help="Stop starting requests once this run has spent this, in USD")
    sub.add_argument("--workers", type=int, default=4, help="Requests at a time")
    arguments = parser.parse_args(argv)
    if min(arguments.price_in, arguments.price_out) < 0 or (arguments.command == "run" and arguments.cap <= 0):
        parser.error("prices can't be negative, and the cap must be more than zero")
    try:
        root, project = archive.resolve(arguments.root, arguments.project)
        chosen, skipped = select(root, project, arguments.format, arguments.batch, arguments.status, arguments.tag,
                                 arguments.id, arguments.stored, arguments.again)
        if arguments.command == "estimate":
            print(json.dumps(dict(estimate(chosen, arguments.price_in, arguments.price_out, arguments.model),
                                  project=project, leftOut=skipped), indent=2, ensure_ascii=False))
            return 0
        totals = run(root, project, chosen, arguments.model, arguments.price_in, arguments.price_out, arguments.cap,
                     arguments.workers)
        totals["leftOut"] = skipped
        print(json.dumps(totals, indent=2, ensure_ascii=False))
        return 1 if totals["failed"] else 0
    except (archive.ArchiveError, DescribeError) as error:
        print("describe: {}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors=stream.errors)
    sys.exit(main())
