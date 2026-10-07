#!/usr/bin/env python3
"""ViewPrinter local content workspace. Python 3.9+, standard library only.

Typed social-content and account-group entries live in ~/ViewPrinter/.hub/entries.
One browser tab serves Content, Account Groups and reversible Archive views.
Use add with an explicit manifest/kind, migrate --apply for legacy shortcuts,
archive/restore for lifecycle, and check for headless media verification.
Archives never cancel schedules or establish publication. Import delivery receipts
with review_delivery.py. Run --help for commands.
"""

import argparse
import base64
from datetime import date, datetime, timezone
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import re
import shutil
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
from urllib.parse import quote, unquote, urlsplit
import urllib.request
import webbrowser
import secrets
import mimetypes
import review_workspace as workspace

try:
    from review_gallery import PENDING_STATUSES, REVIEW_STATUSES
except ImportError:  # copied without its sibling; keep in step with review_gallery.py
    REVIEW_STATUSES = {"new", "draft", "needs-review", "revised", "changes-requested"}
    PENDING_STATUSES = {"planned", "generating", "in-progress", "blocked", "held"}

APP = "viewprinter-review-hub"
VERSION = 5
ASSETS = Path(__file__).resolve().parent.parent / "assets"
HUB_NOTE = ("The hub tab updates itself. Don't open another browser tab or window; "
            "if nobody has the hub open, `review_hub.py open` opens exactly one.")
TITLE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
CARD_STATUS = re.compile(r'data-status="([^"]+)"')
MEDIA_TYPES = {
    ".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
    ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".aac": "audio/aac", ".wav": "audio/wav",
    ".ogg": "audio/ogg", ".flac": "audio/flac", ".png": "image/png", ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp", ".avif": "image/avif",
    ".svg": "image/svg+xml", ".woff": "font/woff", ".woff2": "font/woff2", ".ttf": "font/ttf",
    ".otf": "font/otf", ".vtt": "text/vtt",
}
# Pages, styles and scripts are served only from inside an entry's own folder. Media may also
# come from elsewhere in the same project (a combined gallery points at sibling batches).
# Anything else, such as .env or .json, is never served.
PAGE_TYPES = dict(MEDIA_TYPES, **{
    ".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8",
    ".css": "text/css", ".js": "text/javascript", ".pdf": "application/pdf",
})


def review_root():
    return Path(os.environ.get("VIEWPRINTER_REVIEW_ROOT") or Path.home() / "ViewPrinter").expanduser()


def port():
    raw = os.environ.get("VIEWPRINTER_REVIEW_PORT") or "8765"
    if not raw.isdigit() or not 1 <= int(raw) <= 65535:
        raise ValueError(f"VIEWPRINTER_REVIEW_PORT must be a port number from 1 to 65535, not {raw!r}")
    return int(raw)


def hub_url(entry=None):
    url = f"http://127.0.0.1:{port()}/"
    return url + "#" + quote(entry, safe="") if entry else url


def entries_dir():
    return review_root() / "in-review"


def posted_dir():
    return review_root() / "posted"


def visible_children(folder):
    try:
        return sorted(child for child in folder.iterdir() if not child.name.startswith("."))
    except (FileNotFoundError, NotADirectoryError):
        return []


def project_root(path):
    """The nearest ancestor holding ViewPrinter content memory, which marks a project."""
    for folder in (path, *path.parents):
        if workspace.broad(folder):  # a home folder is never a project
            return None
        if (folder / ".viewprinter" / "content-memory").is_dir():
            return folder
    return None


def find_gallery(target):
    if target.is_file():
        return target if target.suffix.lower() in (".html", ".htm") else None
    pages = [p for p in visible_children(target) if p.is_file() and p.suffix.lower() in (".html", ".htm")]
    named = [p for p in pages if p.name.lower() == "review.html"]
    if named:
        return named[0]
    return max(pages, key=lambda p: p.stat().st_mtime, default=None)


_facts = {}


def page_facts(gallery):
    """Title and card statuses of a gallery page, re-read only when the file changes."""
    info = gallery.stat()
    key = (info.st_mtime_ns, info.st_size)
    cached = _facts.get(str(gallery))
    if cached and cached[0] == key:
        return cached[1]
    text = gallery.read_text(encoding="utf-8", errors="replace")
    title = TITLE.search(text)
    facts = {
        "title": html.unescape(" ".join(title.group(1).split())) if title else "",
        "statuses": [status.lower() for status in CARD_STATUS.findall(text)],
        "updated": info.st_mtime,
    }
    _facts[str(gallery)] = (key, facts)
    return facts


def summarize(statuses):
    if not statuses:
        return None
    return {
        "items": len(statuses),
        "review": sum(status in REVIEW_STATUSES for status in statuses),
        "progress": sum(status in PENDING_STATUSES for status in statuses),
        "approved": statuses.count("approved"),
    }


def status_text(entry):
    if not entry["exists"]:
        return "missing"
    if not entry["url"]:
        return "no page yet"
    summary = entry["summary"]
    if not summary:
        return ""
    if summary["review"]:
        return f"{summary['review']} to review"
    if summary["progress"]:
        return "in progress"
    return "approved" if summary["approved"] == summary["items"] else ""


def display_project(folder):
    words = [word for word in re.split(r"[-_\s]+", folder.name if folder else "") if word]
    return " ".join(word.capitalize() for word in words) or "Other"


def tab_label(title, project, fallback):
    label = re.sub(r"^\s*THIS SESSION\s*[—–-]\s*", "", title or "", flags=re.I)
    if label.lower().startswith(project.lower() + ":"):
        label = label[len(project) + 1:].strip()
    return label or fallback


def describe(path, posted_day=None):
    """One tab: what the link points at, its gallery, and which folders it may serve."""
    target = Path(os.path.realpath(path))
    exists = target.exists()
    gallery = find_gallery(target) if exists else None
    project_folder = project_root(target) if exists else None
    project = display_project(project_folder or (target.parent if exists else None))
    facts = page_facts(gallery) if gallery else {"title": "", "statuses": [], "updated": None}
    try:
        added = os.lstat(path).st_mtime
    except OSError:
        added = 0.0
    entry = {
        "id": f"posted/{posted_day}/{path.name}" if posted_day else path.name,
        "name": path.name,
        "project": project,
        "label": tab_label(facts["title"], project, path.name),
        "title": facts["title"] or path.name,
        "target": str(target),
        "exists": exists,
        "url": workspace.file_url(gallery) if gallery else None,
        "summary": summarize(facts["statuses"]),
        "updated": facts["updated"] or (target.stat().st_mtime if exists else added),
        "added": added,
    }
    if posted_day:
        sidecar = path.parent / (path.name + ".post.json")
        try:
            record = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            record = {}
        entry["posted"] = {"date": posted_day, "url": record.get("url"), "note": record.get("note")}
        entry["added"] = record.get("postedEpoch", added)
    own = str(gallery.parent if gallery else target if target.is_dir() else target.parent) if exists else None
    return entry, own, str(project_folder) if project_folder else own


def scan():
    return workspace.scan()


def register(target, name=None, require_project=False, **kwargs):
    return workspace.register(target, name, require_project=require_project, **kwargs)


def resolve_entry(reference):
    try:
        return workspace.get(reference)
    except ValueError:
        path = Path(reference).expanduser().resolve()
        for record in workspace.records():
            if str(path) in (record.get("gallery"), record.get("target")) or any(str(path) in (s["gallery"],str(Path(s["gallery"]).parent),s["manifest"]) for s in record.get("sources",[])):
                return workspace.get(record["id"])
        raise ValueError("Unknown review: " + reference)


def mark_posted(reference, url=None, note=None):
    raise ValueError("The posted command is retired. Import delivery receipts for publication status; use archive to remove a format from active review.")


def remove(reference):
    with workspace.lock():
        record = resolve_entry(reference)
        record.update(lifecycle="excluded", revision=record["revision"]+1, updatedAt=workspace.now())
        workspace.atomic(workspace.registry()/(record["id"]+".json"), record)
        link = entries_dir()/record["id"]
        if link.is_symlink(): workspace.drop_shortcut(link)
        return record["id"]


_direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def ping(timeout=0.6):
    """The running hub's state, "foreign" when another program holds the port, else None."""
    try:
        with _direct.open(f"http://127.0.0.1:{port()}/api/ping", timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError:
        return "foreign"
    except (urllib.error.URLError, OSError):
        return None
    except ValueError:
        return "foreign"
    return data if isinstance(data, dict) and data.get("app") == APP else "foreign"


def ensure_server():
    state = ping()
    if isinstance(state, dict):
        if state.get("version") != VERSION or state.get("runtime") != runtime_signature():
            raise RuntimeError("An older review runtime is still running. Finish active checks, then run review_hub.py stop and review_hub.py ensure; existing links and registry are preserved.")
        if state.get("root") != str(review_root()):
            raise RuntimeError("A review hub for another root owns this port; use its root or select another port.")
        return hub_url()
    if state == "foreign":
        raise RuntimeError(f"127.0.0.1:{port()} is used by another program; set VIEWPRINTER_REVIEW_PORT")
    folder = review_root() / ".hub"
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "hub.log", "ab") as log:
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "serve"], stdin=subprocess.DEVNULL,
                         stdout=log, stderr=log, start_new_session=True, close_fds=True)
    for _ in range(60):
        time.sleep(0.1)
        if isinstance(ping(), dict):
            return hub_url()
    raise RuntimeError(f"the review hub did not start; see {folder / 'hub.log'}")


def open_hub():
    """Open the hub only when no tab has it open; returns (url, opened)."""
    url = ensure_server()
    state = ping()
    if isinstance(state, dict) and state.get("clients"):
        return url, False
    browser = os.environ.get("VIEWPRINTER_REVIEW_BROWSER", "Google Chrome")
    if sys.platform == "darwin":
        app = Path("/Applications") / f"{browser}.app"
        subprocess.run(["open", "-a", browser, url] if browser and app.exists() else ["open", url], check=False)
    else:
        webbrowser.open(url)
    return url, True


def stop_server():
    state = ping()
    if not isinstance(state, dict):
        return False
    os.kill(int(state["pid"]), signal.SIGTERM)
    for _ in range(40):
        time.sleep(0.1)
        if ping() is None:
            return True
    return False


class Hub:
    def __init__(self):
        self.lock = threading.Lock()
        self.listeners = []
        self.token = secrets.token_urlsafe(32)
        self.snapshot, self.own_roots, self.project_roots = scan()

    def watch(self):
        last = json.dumps(self.snapshot, sort_keys=True)
        while True:
            time.sleep(1.0)
            try:
                snapshot, own_roots, project_roots = scan()
            except Exception as exc:  # keep serving the last good view
                print(f"review_hub: scan failed: {exc}", file=sys.stderr, flush=True)
                continue
            text = json.dumps(snapshot, sort_keys=True)
            with self.lock:
                self.own_roots, self.project_roots = own_roots, project_roots
                if text != last:
                    self.snapshot, last = snapshot, text
                    for listener in self.listeners:
                        listener.put(text)

    def join(self, listener):
        with self.lock:
            self.listeners.append(listener)

    def leave(self, listener):
        with self.lock:
            if listener in self.listeners:
                self.listeners.remove(listener)

    def clients(self):
        with self.lock:
            return len(self.listeners)

    def content_type(self, path):
        """The type to serve path as, or None when it must not be served."""
        def within(roots):
            # normcase: Windows paths compare without regard to case.
            target = os.path.normcase(path)
            return any(target == os.path.normcase(root) or target.startswith(os.path.normcase(root).rstrip(os.sep) + os.sep)
                       for root in roots)
        extension = os.path.splitext(path)[1].lower()
        with self.lock:
            if within(self.own_roots):
                return PAGE_TYPES.get(extension)
            if within(self.project_roots):
                return MEDIA_TYPES.get(extension)
        return None


class Handler(BaseHTTPRequestHandler):
    server_version = "ViewPrinterReviewHub/5"
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass

    def do_HEAD(self):
        self.route(head=True)

    def do_GET(self):
        self.route(head=False)

    def do_POST(self):
        host = (self.headers.get("Host") or "").lower()
        origin = self.headers.get("Origin")
        if (host not in self.server.hosts or origin not in {"http://"+h for h in self.server.hosts}
                or not secrets.compare_digest(self.headers.get("X-ViewPrinter-Token", ""), self.server.hub.token)):
            self.close_connection = True
            return self.reply(403, b"Forbidden local write", "text/plain", False)
        if self.path != "/api/lifecycle":
            return self.reply(404, b"Not found", "text/plain", False)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 8192: raise ValueError("Invalid request size")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict) or not isinstance(data.get("entry"), str): raise ValueError("Entry required")
            if not isinstance(data.get("revision"), int): raise ValueError("Review revision required")
            if not isinstance(data.get("reason", ""), str): raise ValueError("Reason must be text")
            result = workspace.lifecycle(data["entry"], data.get("action"), data["revision"], data.get("reason", ""), batch=data.get("batch"))
            return self.reply_json({"ok":True, "entry":result["id"]}, False)
        except (ValueError, KeyError, TypeError) as exc:
            return self.reply(409 if "refresh" in str(exc) else 400, str(exc).encode(), "text/plain", False)
        except OSError as exc:
            return self.reply(500, str(exc).encode(), "text/plain", False)

    def route(self, head):
        hub = self.server.hub
        if (self.headers.get("Host") or "").lower() not in self.server.hosts:
            return self.reply(403, b"Forbidden host\n", "text/plain; charset=utf-8", head)
        if self.foreign():
            return self.reply(403, b"Forbidden cross-site request\n", "text/plain; charset=utf-8", head)
        path = urlsplit(self.path).path
        if path in ("/", "/index.html"):
            return self.reply(200, PAGE.replace("__TOKEN__", hub.token).replace("__VERSION__", str(VERSION)).encode("utf-8"), "text/html; charset=utf-8", head)
        if path == "/api/ping":
            return self.reply_json({"app": APP, "version": VERSION, "runtime": runtime_signature(), "pid": os.getpid(), "port": port(),
                                    "root": str(review_root()), "clients": hub.clients(),
                                    "inReview": len(hub.snapshot["entries"])}, head)
        if path == "/api/queue":
            return self.reply_json(dict(hub.snapshot, clients=hub.clients()), head)
        if path == "/api/events" and not head:
            return self.events()
        if path == "/workspace/viewprinter-mark.svg":
            return self.reply(200, (ASSETS/"viewprinter-mark.svg").read_bytes(), "image/svg+xml", head)
        if path.startswith("/guidance/"):
            parts = path.split("/")
            if len(parts) != 4: return self.reply(404, b"Not found", "text/plain", head)
            try: refs = workspace.guidance(workspace.get(parts[2]))
            except ValueError: refs = []
            ref = next((r for r in refs if r['id'] == parts[3]), None)
            if not ref: return self.reply(404, b"Not found", "text/plain", head)
            text = Path(ref['path']).read_text(encoding="utf-8")
            page = '<!doctype html><meta name="viewport" content="width=device-width"><title>'+html.escape(ref['label'])+'</title><style>body{margin:32px auto;max-width:900px;padding:0 20px;color:#eceaf6;background:#101018;;font:15px/1.6 system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>'+html.escape(ref['label'])+'</h1><pre>'+html.escape(text)+'</pre>'
            return self.reply(200, page.encode(), "text/html; charset=utf-8", head)
        if path.startswith("/downloads/"):
            parts = path.split("/")
            if len(parts) != 4: return self.reply(404, b"Not found", "text/plain", head)
            entry = next((e for e in hub.snapshot["entries"]+hub.snapshot["archived"] if e["id"]==parts[2]), None)
            download = next((d for d in (entry or {}).get("downloads",[]) if d["id"]==parts[3]), None)
            if not download: return self.reply(404, b"Not found", "text/plain", head)
            # Re-resolve the manifest allowlist on each request (symlinks can change).
            fresh = workspace.describe(workspace.get(entry["id"]))
            download = next((d for d in fresh["downloads"] if d["id"]==parts[3]), None)
            if not download: return self.reply(404, b"Not found", "text/plain", head)
            return self.file(download["path"], head, download=True)
        if path.startswith("/files/"):
            return self.file(workspace.url_path(path[len("/files/"):]), head)
        self.send_response(302)
        self.send_header("Location", "/")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def foreign(self):
        """A request another site started: an image, video or fetch from a page that is not this hub.
        Browsers say so in Sec-Fetch-Site. Following a link here is a navigation and stays allowed;
        a file it opens is sandboxed (see file)."""
        return (self.headers.get("Sec-Fetch-Site") in ("cross-site", "same-site")
                and (self.headers.get("Sec-Fetch-Mode"), self.headers.get("Sec-Fetch-Dest")) != ("navigate", "document"))

    def reply(self, status, body, content_type, head):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        if content_type.startswith("text/html"):
            self.send_header("Content-Security-Policy", "frame-ancestors 'self'")
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def reply_json(self, data, head):
        self.reply(200, json.dumps(data).encode("utf-8"), "application/json", head)

    def events(self):
        hub, listener = self.server.hub, queue.Queue()
        hub.join(listener)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b"retry: 2000\n\n")
            self.send_event(json.dumps(hub.snapshot))
            while True:
                try:
                    self.send_event(listener.get(timeout=15))
                except queue.Empty:
                    self.wfile.write(b": keep-alive\n\n")
        except OSError:  # the tab closed or reloaded
            pass
        finally:
            hub.leave(listener)
            self.close_connection = True

    def send_event(self, text):
        self.wfile.write(b"event: queue\ndata: " + text.encode("utf-8") + b"\n\n")

    def file(self, path, head, download=False):
        # Check the plain path before touching the file system, then again once resolved, so a
        # link inside a served folder cannot lead out of it.
        try:
            if path is None or not os.path.isabs(path) or not (download or self.server.hub.content_type(path)):
                raise ValueError("not a served path")
            path = os.path.realpath(path)
            content_type = (mimetypes.guess_type(path)[0] or "application/octet-stream") if download else self.server.hub.content_type(path)
            info = os.stat(path) if content_type else None
        except (OSError, ValueError):
            info = None
        if not info or not stat.S_ISREG(info.st_mode):
            return self.reply(404, b"Not found\n", "text/plain; charset=utf-8", head)
        size, etag = info.st_size, '"%x-%x"' % (info.st_size, info.st_mtime_ns)
        start, end, status = 0, info.st_size - 1, 200
        wanted = re.fullmatch(r"bytes=(\d*)-(\d*)", (self.headers.get("Range") or "").strip())
        if wanted and any(wanted.groups()) and self.headers.get("If-Range", etag) == etag:
            if wanted.group(1):
                start = int(wanted.group(1))
                end = min(int(wanted.group(2)), size - 1) if wanted.group(2) else size - 1
            else:
                start = max(0, size - int(wanted.group(2)))
            if start >= size or start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            status = 206
        elif self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.end_headers()
            return
        length = end - start + 1 if size else 0
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        if download:
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(Path(path).name))
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        # Only this hub's pages may embed what it serves.
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        if content_type.startswith("text/html"):
            self.send_header("Content-Security-Policy", "frame-ancestors 'self'")
        elif not content_type.startswith("application/pdf"):
            # A file opened directly, such as an SVG, cannot run script in the hub's origin.
            self.send_header("Content-Security-Policy", "sandbox")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if head or not length:
            return
        try:
            with open(path, "rb") as stream:
                stream.seek(start)
                remaining = length
                while remaining:
                    chunk = stream.read(min(262144, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except OSError:  # players abandon ranges constantly
            self.close_connection = True


def runtime_signature():
    import hashlib
    # Keep the startup signature fixed: editing files must not make an old process look current.
    return RUNTIME_SIGNATURE


def serve():
    hub = Hub()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port()), Handler)
    except OSError as exc:
        print(f"review_hub: cannot listen on 127.0.0.1:{port()} ({exc})", file=sys.stderr)
        return 1
    server.daemon_threads = True
    server.hub = hub
    server.hosts = {f"127.0.0.1:{port()}", f"localhost:{port()}", f"[::1]:{port()}"}
    folder = review_root() / ".hub"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "hub.pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
    threading.Thread(target=hub.watch, daemon=True).start()
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    print(f"review hub: {review_root()} at {hub_url()}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


class DevTools:
    """Just enough of the Chrome DevTools Protocol, over a WebSocket, to drive one page."""

    def __init__(self, url, timeout):
        parts = urlsplit(url)
        self.socket = socket.create_connection((parts.hostname, parts.port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        self.socket.sendall((f"GET {parts.path} HTTP/1.1\r\nHost: {parts.netloc}\r\nUpgrade: websocket\r\n"
                             f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
                            .encode("ascii"))
        self.buffer = b""
        while b"\r\n\r\n" not in self.buffer:
            self.buffer += self.read_some()
        head, self.buffer = self.buffer.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise RuntimeError("Chrome refused the DevTools connection")
        self.last_id = 0

    def read_some(self):
        chunk = self.socket.recv(65536)
        if not chunk:
            raise RuntimeError("Chrome closed the DevTools connection")
        return chunk

    def exactly(self, size):
        while len(self.buffer) < size:
            self.buffer += self.read_some()
        data, self.buffer = self.buffer[:size], self.buffer[size:]
        return data

    def send(self, text, opcode=0x1):
        data = text.encode("utf-8") if isinstance(text, str) else text
        size = len(data)
        header = bytes([0x80 | opcode])
        if size < 126:
            header += bytes([0x80 | size])
        elif size < 65536:
            header += bytes([0x80 | 126]) + struct.pack(">H", size)
        else:
            header += bytes([0x80 | 127]) + struct.pack(">Q", size)
        mask = os.urandom(4)
        self.socket.sendall(header + mask + bytes(byte ^ mask[i % 4] for i, byte in enumerate(data)))

    def receive(self):
        message = b""
        while True:
            first, second = self.exactly(2)
            size = second & 0x7F
            if size == 126:
                size = struct.unpack(">H", self.exactly(2))[0]
            elif size == 127:
                size = struct.unpack(">Q", self.exactly(8))[0]
            payload = self.exactly(size)
            opcode = first & 0x0F
            if opcode == 0x8:
                raise RuntimeError("Chrome closed the DevTools connection")
            if opcode == 0x9:
                self.send(payload, opcode=0xA)
            elif opcode in (0x0, 0x1, 0x2):
                message += payload
                if first & 0x80:
                    return message.decode("utf-8")

    def call(self, method, params=None, session=None):
        self.last_id += 1
        request = {"id": self.last_id, "method": method, "params": params or {}}
        if session:
            request["sessionId"] = session
        self.send(json.dumps(request))
        while True:  # events arrive in between; only the reply matters
            reply = json.loads(self.receive())
            if reply.get("id") == self.last_id:
                if "error" in reply:
                    raise RuntimeError(f"{method}: {reply['error'].get('message')}")
                return reply.get("result", {})


PROBE = r"""async ({seconds, allCurrent}) => {
  const source = el => el.currentSrc || el.src || el.querySelector('source')?.src || '';
  const name = value => decodeURIComponent(value.split('/').pop());
  const once = (el, types, ms) => new Promise(resolve => {
    const finish = type => {clearTimeout(timer);types.forEach(t=>el.removeEventListener(t,done));resolve(type)};
    const done = event => finish(event.type);
    const timer = setTimeout(()=>finish('timeout'), ms);
    types.forEach(t=>el.addEventListener(t,done));
  });
  const media = [...document.querySelectorAll('video,audio')];
  const initialVisibleReferences = [...document.querySelectorAll('article.card:not([hidden]) [data-copy-reference]')].map(el=>el.dataset.copyReference);
  const current = [...document.querySelectorAll('article .previews video,article .previews audio')];
  const candidates = allCurrent ? (current.length ? current : media) : media.filter(el=>el.tagName==='VIDEO').slice(0,1);
  const tasks = media.map(el=>({el,src:source(el),reference:el.closest('article')?.querySelector('[data-copy-reference]')?.dataset.copyReference || name(source(el))}));
  // One reusable verification player, rather than hundreds of retained decoders.
  media.forEach(el=>{el.pause();el.removeAttribute('src');el.querySelectorAll('source').forEach(s=>s.removeAttribute('src'));el.preload='none';el.load()});
  const player = document.createElement('video');player.muted=true;player.playsInline=true;
  player.style.cssText='position:fixed;bottom:0;left:0;width:320px;height:240px;opacity:.01;pointer-events:none';
  document.body.append(player);
  async function load(src) {
    player.pause();player.removeAttribute('src');player.load();
    const ready=once(player,['loadedmetadata','error'],15000);
    player.preload='metadata';player.src=src;player.load();await ready;
    return {src:name(src),ok:player.readyState>=1&&!player.error,duration:Number.isFinite(player.duration)?Math.round(player.duration*1000)/1000:null,size:player.videoWidth?player.videoWidth+'x'+player.videoHeight:null};
  }
  const loaded=[], cache=new Map();
  for (const task of tasks) {if(!cache.has(task.src))cache.set(task.src,await load(task.src));loaded.push(cache.get(task.src))}
  const images=[];
  for (const img of document.images) {img.loading='eager';await img.decode().catch(()=>{});images.push({src:name(img.currentSrc||img.src||''),ok:img.complete&&img.naturalWidth>0})}
  if(allCurrent)document.querySelector('[data-batch-view=""]')?.click();
  const playbacks=[];
  for(const video of candidates) {
    const task=tasks.find(t=>t.el===video);const metadata=await load(task.src);let playback;
    const started=performance.now();let timer;
    try {
      if(!metadata.ok)throw Error('Media did not load');
      player.currentTime=0;
      await Promise.race([player.play(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Playback start timed out')),15000)})]);
      clearTimeout(timer);
      const sample=Math.min(seconds,player.duration||seconds);
      const end=await once(player,['ended','error'],sample*1000+(sample>=player.duration?1000:0));
      const quality=player.getVideoPlaybackQuality?.()||{totalVideoFrames:0,droppedVideoFrames:0};
      playback={src:name(task.src),end,seconds:Math.round((performance.now()-started)/10)/100,position:Math.round(player.currentTime*1000)/1000,duration:player.duration,frames:quality.totalVideoFrames,dropped:quality.droppedVideoFrames,audioBytes:player.webkitAudioDecodedByteCount||0};
    } catch(error) {playback={src:name(task.src),error:String(error)}}
    clearTimeout(timer);player.pause();playback.reference=task.reference;
    playback.ok=!playback.error&&playback.position>=Math.min(.5,player.duration*.8);playbacks.push(playback);
  }
  player.removeAttribute('src');player.load();player.remove();
  const buttons=[...document.querySelectorAll('button')].map(b=>b.textContent.trim());
  return {title:document.title,media:loaded,images,playback:playbacks[0]||null,playbacks,currentPreviews:current.length,initialVisibleReferences,copyIds:buttons.filter(t=>/copy id/i.test(t)).length,speeds:buttons.filter(t=>/^\d+(\.\d+)?×$/.test(t)).length};
}"""


def find_chrome():
    mac = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
           os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
           "/Applications/Chromium.app/Contents/MacOS/Chromium",
           "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    windows = [os.path.join(base, *tail)
               for base in filter(None, (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"),
                                         os.environ.get("LOCALAPPDATA")))
               for tail in (("Google", "Chrome", "Application", "chrome.exe"),
                            ("Microsoft", "Edge", "Application", "msedge.exe"))]
    linux = [shutil.which(name) for name in ("google-chrome", "google-chrome-stable", "chromium",
                                             "chromium-browser", "microsoft-edge", "chrome", "msedge")]
    for candidate in (os.environ.get("VIEWPRINTER_CHROME"), *mac, *windows, *linux):
        if candidate and os.path.exists(candidate):
            return candidate
    raise RuntimeError("no Chrome, Chromium or Edge found; set VIEWPRINTER_CHROME to its executable")


def gallery_url(reference):
    if re.match(r"https?://", reference):
        return reference
    registered = False
    try:
        record = resolve_entry(reference)
        target = Path(record.get("snapshotGallery") if record["lifecycle"]=="archived" and record.get("snapshotGallery") else record["gallery"])
        registered = True
    except ValueError:
        target = Path(os.path.realpath(Path(reference).expanduser()))
    gallery = find_gallery(target) if target.exists() else None
    if not gallery:
        raise ValueError(f"no review page found for {reference}")
    if registered:
        # Verify the same HTTP/media route the user sees, including server permissions.
        return ensure_server().rstrip("/") + workspace.file_url(gallery)
    return gallery.as_uri()


def check_gallery(reference, seconds=20, all_current=False):
    """Check registered galleries over HTTP; optionally play every current preview."""
    if seconds <= 0:
        raise ValueError("seconds must be greater than zero")
    url = gallery_url(reference)
    # A throwaway profile: no keychain prompt, no sync. Checking a local review, Chrome resolves
    # no other host, so its own background requests go nowhere.
    offline = [] if re.match(r"https?://(?!127\.0\.0\.1[:/])", url) else [
        "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1"]
    with tempfile.TemporaryDirectory(prefix="review-check-") as profile:
        chrome = subprocess.Popen(
            [find_chrome(), "--headless=new", "--remote-debugging-port=0", f"--user-data-dir={profile}",
             "--autoplay-policy=no-user-gesture-required", "--mute-audio", "--no-first-run",
             "--no-default-browser-check", "--window-size=1280,2000",
             "--use-mock-keychain", "--password-store=basic", "--disable-background-networking",
             "--disable-component-update", "--disable-sync", "--disable-extensions",
             "--disable-default-apps", "--no-pings", *offline, "about:blank"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            active = Path(profile) / "DevToolsActivePort"
            for _ in range(150):
                lines = active.read_text(encoding="utf-8").splitlines() if active.exists() else []
                if len(lines) >= 2:
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError("headless Chrome did not start")
            tools = DevTools(f"ws://127.0.0.1:{lines[0]}{lines[1]}", timeout=max(180, seconds * 200 + 120))
            target = tools.call("Target.createTarget", {"url": "about:blank"})["targetId"]
            session = tools.call("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
            tools.call("Page.navigate", {"url": url}, session)
            for _ in range(150):
                ready = tools.call("Runtime.evaluate", {"expression": "document.readyState", "returnByValue": True}, session)
                if ready["result"].get("value") == "complete":
                    break
                time.sleep(0.1)
            outcome = tools.call("Runtime.evaluate", {"expression": f"({PROBE})({json.dumps({'seconds': seconds, 'allCurrent': all_current})})",
                                                      "awaitPromise": True, "returnByValue": True}, session)
        finally:
            chrome.terminate()
            try:
                chrome.wait(10)
            except subprocess.TimeoutExpired:
                chrome.kill()
    if "exceptionDetails" in outcome:
        raise RuntimeError(outcome["exceptionDetails"].get("text", "the page probe failed"))
    report = outcome["result"]["value"]
    report["url"] = url
    playback = report["playback"]
    report["problems"] = ([f"{item['src']} did not load" for item in report["media"] if not item["ok"]]
                          + [f"{item['src']} did not decode" for item in report["images"] if not item["ok"]]
                          + [f"{item['src']} did not play: {item.get('error') or item.get('end')}"
                             for item in report["playbacks"] if not item["ok"]])
    report["servedOverHttp"] = url.startswith(("http://", "https://"))
    report["checkedAllCurrent"] = all_current
    return report


def print_check(report):
    print(f"checked {report['title'] or report['url']} in headless Chrome")
    print(f"  media {sum(item['ok'] for item in report['media'])}/{len(report['media'])} loaded, "
          f"images {sum(item['ok'] for item in report['images'])}/{len(report['images'])} decoded, "
          f"Copy ID buttons {report['copyIds']}, speed controls {report['speeds']}")
    playback = report["playback"]
    if playback and not playback.get("error"):
        print(f"  played {playback['src']}: {playback['position']} s of {playback['duration']} s in "
              f"{playback['seconds']} s ({playback['end']}), {playback['frames']} frames presented, "
              f"{playback['dropped']} dropped, audio decoded: {'yes' if playback['audioBytes'] else 'no'}")
    if report.get("checkedAllCurrent"):
        print(f"  current previews played: {sum(item['ok'] for item in report['playbacks'])}/{len(report['playbacks'])}")
    for problem in report["problems"]:
        print(f"  PROBLEM: {problem}")


def print_list():
    snapshot, _, _ = scan()
    state = ping()
    if isinstance(state, dict):
        print(f"hub: {hub_url()} ({state['clients']} tab(s) open)")
    elif state == "foreign":
        print(f"hub: 127.0.0.1:{port()} is used by another program")
    else:
        print("hub: not running (review_hub.py ensure starts it)")
    print(f"in review: {len(snapshot['entries'])} ({entries_dir()})")
    for entry in snapshot["entries"]:
        status = status_text(entry)
        print(f"  {entry['name']}  {entry['project']}: {entry['label']}" + (f"  [{status}]" if status else ""))
    if snapshot["posted"]:
        print(f"archived: {len(snapshot['archived'])}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="show a batch folder or gallery as a tab")
    add.add_argument("target")
    add.add_argument("--name", help="entry name (default <project>--<folder>)")
    add.add_argument("--no-server", action="store_true", help="link only; don't start the hub")
    add.add_argument("--kind", choices=sorted(workspace.KINDS))
    add.add_argument("--manifest")
    add.add_argument("--format-id")
    add.add_argument("--owner")
    add.add_argument("--group", action="append")
    add.add_argument("--source-revision", type=int, help="expected revision of this contributor source")
    add.add_argument("--revision", type=int, help="expected revision of the whole format")
    reconcile = commands.add_parser("reconcile-formats", help="map legacy entries to stable project format IDs")
    reconcile.add_argument("plan", type=Path)
    reconcile.add_argument("--apply", action="store_true")
    undo_formats = commands.add_parser("rollback-formats", help="restore an unchanged format migration")
    undo_formats.add_argument("receipt")
    influencer = commands.add_parser("manage-influencer", help="manage an existing review as an influencer")
    influencer.add_argument("entry")
    influencer.add_argument("--influencer-id", required=True)
    influencer.add_argument("--profile", required=True)
    influencer.add_argument("--guide")
    migration = commands.add_parser("migrate", help="preview or apply the legacy registry migration")
    migration.add_argument("--apply", action="store_true")
    migration.add_argument("--exclude", action="append", default=[])
    rollback = commands.add_parser("rollback-migration", help="undo an unchanged migration using its before receipt")
    rollback.add_argument("receipt")
    for action in ("archive", "restore"):
        operation = commands.add_parser(action, help=action+" a format or batch; schedules stay unchanged")
        operation.add_argument("entry")
        operation.add_argument("--revision", type=int)
        operation.add_argument("--reason", default="")
        operation.add_argument("--batch")
    posted = commands.add_parser("posted", help="retired: import delivery receipts, and archive a finished format")
    posted.add_argument("entry", help="entry name, batch folder or gallery path")
    posted.add_argument("--url", help="where it was posted or scheduled")
    posted.add_argument("--note")
    dropped = commands.add_parser("remove", help="drop an entry that won't be posted; its folder is untouched")
    dropped.add_argument("entry")
    check = commands.add_parser("check", help="play a gallery in headless Chrome; never opens a window")
    check.add_argument("entry", help="entry name, batch folder, gallery path or http URL")
    check.add_argument("--seconds", type=float, default=20, help="how long to play the first video (default 20)")
    check.add_argument("--json", action="store_true", help="print the full report as JSON")
    check.add_argument("--all-current", action="store_true", help="play each current video/audio preview; --seconds applies to each")
    for name, text in (("list", "show the entries and whether the hub runs"),
                       ("open", "open the hub in a browser unless a tab already has it"),
                       ("ensure", "start the hub if it is not running"),
                       ("stop", "stop the hub"), ("serve", "run the hub in the foreground")):
        commands.add_parser(name, help=text)
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            return serve()
        if args.command == "add":
            entry = register(args.target, args.name, kind=args.kind, manifest=args.manifest, format_id=args.format_id, owner=args.owner, groups=args.group, source_revision=args.source_revision, revision=args.revision)
            if not args.no_server:
                ensure_server()
            print(f"{entry} is a tab at {hub_url(entry)}\n{HUB_NOTE}")
        elif args.command == "reconcile-formats":
            from review_formats import reconcile
            print(json.dumps(reconcile(json.loads(args.plan.read_text(encoding="utf-8")), args.apply), indent=2))
        elif args.command == "rollback-formats":
            from review_formats import rollback
            print(json.dumps(rollback(args.receipt), indent=2))
        elif args.command == "manage-influencer":
            from review_formats import manage_influencer
            print(json.dumps(manage_influencer(args.entry,args.influencer_id,args.profile,args.guide),indent=2))
        elif args.command == "migrate":
            print(json.dumps(workspace.migrate(args.apply, args.exclude), indent=2))
        elif args.command == "rollback-migration":
            print(json.dumps(workspace.rollback(args.receipt), indent=2))
        elif args.command in {"archive", "restore"}:
            record = resolve_entry(args.entry)
            result = workspace.lifecycle(record["id"], args.command, args.revision, args.reason, batch=args.batch)
            print(f"{result['id']}: {result['lifecycle']}; schedules unchanged")
        elif args.command == "posted":
            print(f"moved to {mark_posted(args.entry, args.url, args.note)}")
        elif args.command == "remove":
            print(f"removed {remove(args.entry)}; its folder is untouched")
        elif args.command == "check":
            report = check_gallery(args.entry, args.seconds, args.all_current)
            if args.json:
                print(json.dumps(report, indent=1))
            else:
                print_check(report)
            return 1 if report["problems"] else 0
        elif args.command == "list":
            print_list()
        elif args.command == "open":
            url, opened = open_hub()
            print(f"opened {url}" if opened else f"{url} is already open in a tab; it updates itself")
        elif args.command == "ensure":
            print(ensure_server())
        elif args.command == "stop":
            print("stopped" if stop_server() else "the hub was not running")
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"review_hub: {exc}", file=sys.stderr)
        return 1
    return 0


PAGE = (ASSETS / "review-workspace.html").read_text(encoding="utf-8")
import hashlib
RUNTIME_SIGNATURE = hashlib.sha256(b"".join(p.read_bytes() for p in [Path(__file__), Path(workspace.__file__), Path(__file__).with_name("review_delivery.py"), Path(__file__).with_name("review_readiness.py"), Path(__file__).with_name("review_formats.py"), Path(__file__).with_name("review_gallery.py"), ASSETS/"review-workspace.html"])).hexdigest()[:16]


if __name__ == "__main__":
    # Agents read this through a pipe, which on Windows defaults to the system code page.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors=stream.errors)
    sys.exit(main())
