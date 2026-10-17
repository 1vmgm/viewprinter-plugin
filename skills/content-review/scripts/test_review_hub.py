"""Run: python -m unittest discover -s scripts -p 'test_review_hub.py'."""

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
from urllib.parse import quote
import urllib.request

SCRIPTS = Path(__file__).resolve().parent
HUB = SCRIPTS / "review_hub.py"
GALLERY = SCRIPTS / "review_gallery.py"
from review_workspace import file_url, served_root, url_path  # noqa: E402

DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def chrome_available():
    try:
        import review_hub
        return bool(review_hub.find_chrome())
    except RuntimeError:
        return False


class ReviewHubTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(os.path.realpath(self.temp.name))
        self.project = base / "project"
        (self.project / ".viewprinter" / "content-memory").mkdir(parents=True)
        self.batch = self.project / "branding" / "batch-one"
        self.batch.mkdir(parents=True)
        (self.batch / "clip.mp4").write_bytes(bytes(range(64)))
        (self.batch / "secret.env").write_text("TOKEN=1\n", encoding="utf-8")
        (self.batch / "review.html").write_text(
            "<title>THIS SESSION — Project: Batch one / round 2</title>"
            '<article data-status="needs-review"></article><article data-status="approved"></article>',
            encoding="utf-8")
        (self.batch / 'review.json').write_text(json.dumps({
            'title':'THIS SESSION — Project: Batch one / round 2','round':2,
            'reviewHub':{'kind':'social-content','formatId':'batch-one'},
            'items':[{'id':'A','version':1,'title':'A','format':'portrait','status':'needs-review','src':'clip.mp4','kind':'video'},
                     {'id':'B','version':1,'title':'B','format':'portrait','status':'approved','src':'clip.mp4','kind':'video'}]}), encoding="utf-8")
        self.outside = base / "outside"
        self.outside.mkdir()
        (self.outside / "other.mp4").write_bytes(b"x" * 10)
        self.hub_root = base / "hub"
        self.port = free_port()
        self.env = dict(os.environ, VIEWPRINTER_REVIEW_ROOT=str(self.hub_root),
                        VIEWPRINTER_REVIEW_PORT=str(self.port), VIEWPRINTER_REVIEW_AUTOSTART="0")

    def hub(self, *args):
        result = subprocess.run([sys.executable, str(HUB), *args], env=self.env,
                                capture_output=True, text=True, timeout=30, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def entries(self):
        folder = self.hub_root / "in-review"
        return sorted(path.name for path in folder.iterdir()) if folder.exists() else []

    def start_server(self):
        server = subprocess.Popen([sys.executable, str(HUB), "serve"], env=self.env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(server.wait, 10)
        self.addCleanup(server.terminate)
        for _ in range(200):
            try:
                with DIRECT.open(f"http://127.0.0.1:{self.port}/api/ping", timeout=1) as response:
                    return json.load(response)
            except OSError:
                time.sleep(0.05)
        self.fail("the hub did not start")

    def get(self, path, **headers):
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", headers=headers)
        try:
            with DIRECT.open(request, timeout=5) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            error.close()
            return error.code, b""

    def test_presence_is_authenticated_and_background_tab_counts_without_stream(self):
        self.start_server()
        _,page=self.get('/')
        token=re.search(b'name="vp-token" content="([^"]+)"',page).group(1).decode()
        headers={'Origin':f'http://127.0.0.1:{self.port}','X-ViewPrinter-Token':token}
        def presence(opened,request_headers):
            request=urllib.request.Request(f'http://127.0.0.1:{self.port}/api/presence',
                data=json.dumps({'tab':'test-tab','open':opened}).encode(),headers=request_headers)
            try:
                with DIRECT.open(request,timeout=5) as response:return response.status
            except urllib.error.HTTPError as error:
                error.close();return error.code
        self.assertEqual(presence(True,{}),403)
        self.assertEqual(presence(True,headers),200)
        _,raw=self.get('/api/ping');state=json.loads(raw)
        self.assertEqual((state['clients'],state['tabs']),(0,1))
        self.assertEqual(presence(False,headers),200)
        _,raw=self.get('/api/ping');self.assertEqual(json.loads(raw)['tabs'],0)

    def test_add_links_the_batch_once(self):
        self.hub("add", str(self.batch / "review.html"), "--no-server")
        self.hub("add", str(self.batch), "--no-server")
        self.assertEqual(self.entries(), ["project--batch-one"])
        link = self.hub_root / "in-review" / "project--batch-one"
        self.assertTrue(link.is_symlink())
        record=json.loads((self.hub_root/".hub/entries/project--batch-one.json").read_text(encoding="utf-8"))
        self.assertEqual(os.path.realpath(link), str(Path(record["gallery"]).parent))
        self.assertEqual(record["sources"][0]["manifest"], str(self.batch/"review.json"))

    def test_archive_freezes_review_and_restores_same_id(self):
        self.hub("add", str(self.batch), "--no-server")
        self.hub("archive", "project--batch-one", "--reason", "Finished review")
        self.assertEqual(self.entries(), [])
        record = json.loads((self.hub_root/'.hub/entries/project--batch-one.json').read_text(encoding="utf-8"))
        original = Path(record['snapshotGallery']).read_text(encoding="utf-8")
        (self.batch/'review.html').write_text('New version', encoding="utf-8")
        self.assertEqual(Path(record['snapshotGallery']).read_text(encoding="utf-8"), original)
        self.assertEqual(record['lifecycle'], 'archived')
        self.hub('restore', 'project--batch-one')
        self.assertEqual(self.entries(), ['project--batch-one'])

    def test_remove_unlinks_and_keeps_the_folder(self):
        self.hub("add", str(self.batch), "--no-server")
        self.hub("remove", str(self.batch))
        self.assertEqual(self.entries(), [])
        self.assertTrue((self.batch / "clip.mp4").is_file())

    def test_renderer_adds_only_galleries_inside_a_project(self):
        manifest = {"reviewHub":{"kind":"social-content","formatId":"pending"},"title": "THIS SESSION — Project: Pending", "round": 1, "items": [
            {"id": "P01", "version": 1, "title": "Idea", "format": "Portrait", "status": "planned"}]}
        notes = []
        for folder in (self.batch, self.outside):
            (folder / "review.json").write_text(json.dumps(manifest), encoding="utf-8")
            result = subprocess.run([sys.executable, str(GALLERY), "--manifest", str(folder / "review.json"),
                                     "--output", str(folder / "review.html")],
                                    env=self.env, capture_output=True, text=True, timeout=30, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), str(folder / "review.html"))
            notes.append(result.stderr)
        self.assertEqual(self.entries(), ["project--pending"])
        self.assertIn("review hub", notes[0])
        # Outside a project the gallery is still written, and the agent is told why it isn't in the hub.
        self.assertIn("not inside a ViewPrinter project", notes[1])
        self.assertIn("memory.py init --project", notes[1])

    def test_server_lists_entries_and_serves_only_review_files(self):
        self.hub("add", str(self.batch), "--no-server")
        sibling = self.project / "sibling"
        sibling.mkdir()
        (sibling / "shared.mp4").write_bytes(b"s" * 8)
        (sibling / "page.html").write_text("<p>not an entry</p>", encoding="utf-8")
        self.start_server()
        status, body = self.get("/api/queue")
        [entry] = json.loads(body)["entries"]
        self.assertEqual((entry["project"], entry["label"]), ("Project", "Batch one / round 2"))
        self.assertEqual(entry["summary"], {"items": 2, "review": 1, "progress": 0, "approved": 1})
        batch = file_url(self.batch)
        self.assertEqual(self.get(entry["url"])[0], 200)
        self.assertEqual(self.get(batch + "/clip.mp4", Range="bytes=2-5"), (206, bytes([2, 3, 4, 5])))
        self.assertEqual(self.get(batch + "/clip.mp4", Range="bytes=-3"), (206, bytes([61, 62, 63])))
        self.assertEqual(self.get(file_url(sibling / "shared.mp4"))[0], 200)
        self.assertEqual(self.get(file_url(sibling / "page.html"))[0], 404)
        self.assertEqual(self.get(batch + "/secret.env")[0], 404)
        self.assertEqual(self.get(file_url(self.outside / "other.mp4"))[0], 404)
        self.assertEqual(self.get(batch + "/../../../outside/other.mp4")[0], 404)
        self.assertEqual(self.get("/api/queue", Host="attacker.example")[0], 403)

    def head(self, path, **headers):
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", headers=headers, method="HEAD")
        with DIRECT.open(request, timeout=5) as response:
            return response.headers

    def media_link(self, data):
        """A stand-in for ViewPrinter's media link: serves data with byte ranges, as its CDN does."""
        hits = []

        class Media(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_HEAD(self):
                self.answer(head=True)

            def do_GET(self):
                self.answer(head=False)

            def answer(self, head):
                hits.append(self.headers.get("Range"))
                wanted = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range") or "")
                start, end, status = 0, len(data) - 1, 200
                if wanted:
                    start = int(wanted.group(1)) if wanted.group(1) else len(data) - int(wanted.group(2))
                    end = min(int(wanted.group(2)), len(data) - 1) if wanted.group(1) and wanted.group(2) else len(data) - 1
                    if start >= len(data):
                        self.send_response(416)
                        self.send_header("Content-Range", f"bytes */{len(data)}")
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                    status = 206
                body = data[start:end + 1]
                self.send_response(status)
                self.send_header("Content-Type", "binary/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                if status == 206:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
                self.end_headers()
                if not head:
                    self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Media)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}/media/m-1", hits

    def test_a_copy_let_go_to_viewprinter_streams_through_the_hub(self):
        self.hub("add", str(self.batch), "--no-server")
        data = bytes(range(64))
        kept = self.project / ".viewprinter/content-memory/reviews/.media" / hashlib.sha256(data).hexdigest() / "clip.mp4"
        self.assertTrue(kept.is_file())
        url, hits = self.media_link(data)
        note = {"mediaId": "m-1", "url": url, "name": "clip.mp4", "bytes": 64}
        (kept.parent / "kept.json").write_text(json.dumps(note), encoding="utf-8")
        kept.unlink()
        self.start_server()
        link = file_url(kept)
        self.assertEqual(self.get(link, Range="bytes=2-5"), (206, bytes([2, 3, 4, 5])))
        self.assertEqual(self.get(link), (200, data))
        self.assertEqual(hits[-2:], ["bytes=2-5", None])  # the player's range went through
        headers = self.head(link)
        # Served like any review file: its own type, this hub's protections and a stable tag.
        self.assertEqual((headers["Content-Type"], headers["Content-Security-Policy"],
                          headers["Cross-Origin-Resource-Policy"], headers["Content-Length"]),
                         ("video/mp4", "sandbox", "same-origin", "64"))
        self.assertEqual(self.get(link, **{"If-None-Match": headers["ETag"]})[0], 304)
        self.assertEqual(self.get(link, Range="bytes=99-")[0], 416)
        # Only a secure link is followed (plain http only on this machine); a dead one is a gateway error.
        (kept.parent / "kept.json").write_text(json.dumps(dict(note, url="http://example.com/media/m-1")), encoding="utf-8")
        self.assertEqual(self.get(link)[0], 404)
        (kept.parent / "kept.json").write_text(json.dumps(dict(note, url="http://127.0.0.1:9/media/m-1")), encoding="utf-8")
        self.assertEqual(self.get(link)[0], 502)
        # Without ViewPrinter's note, or with a note naming another file, the copy is simply gone.
        (kept.parent / "kept.json").write_text(json.dumps(dict(note, name="other.mp4")), encoding="utf-8")
        self.assertEqual(self.get(link)[0], 404)
        (kept.parent / "kept.json").unlink()
        self.assertEqual(self.get(link)[0], 404)

    def test_other_sites_cannot_embed_or_script_what_the_hub_serves(self):
        self.hub("add", str(self.batch), "--no-server")
        (self.batch / "badge.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', encoding="utf-8")
        self.start_server()
        clip = file_url(self.batch / "clip.mp4")
        embedded = {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "no-cors", "Sec-Fetch-Dest": "video"}
        self.assertEqual(self.get(clip, **embedded)[0], 403)
        self.assertEqual(self.get(clip, **dict(embedded, **{"Sec-Fetch-Site": "same-site"}))[0], 403)
        self.assertEqual(self.get(clip, **{"Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "no-cors"})[0], 200)
        # Following a link from elsewhere still opens it; what opens is sandboxed. Framing it is refused.
        link = {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"}
        self.assertEqual(self.get(clip, **link)[0], 200)
        self.assertEqual(self.get("/", **dict(link, **{"Sec-Fetch-Dest": "iframe"}))[0], 403)
        svg = self.head(file_url(self.batch / "badge.svg"))
        self.assertEqual((svg["Content-Security-Policy"], svg["Cross-Origin-Resource-Policy"]), ("sandbox", "same-origin"))
        self.assertEqual(self.head(file_url(self.batch / "review.html"))["Content-Security-Policy"], "frame-ancestors 'self'")
        self.assertEqual(self.head("/")["Content-Security-Policy"], "frame-ancestors 'self'")
        self.assertEqual(self.head("/api/queue")["Cross-Origin-Resource-Policy"], "same-origin")

    def test_a_group_outside_a_project_serves_only_its_own_folder(self):
        group = self.outside / "launch-accounts"
        group.mkdir()
        (group / "group.json").write_text(json.dumps({"id": "launch-accounts", "reviewHub": {"kind": "account-group"},
                                                      "accounts": [{"accountId": "acct-1", "platform": "instagram"}]}),
                                          encoding="utf-8")
        (group / "review.html").write_text("<title>Launch accounts</title>", encoding="utf-8")
        (group / "avatar.png").write_bytes(b"png")
        self.hub("add", str(group), "--kind", "account-group", "--no-server")
        record = json.loads((self.hub_root / ".hub/entries/outside--launch-accounts.json").read_text(encoding="utf-8"))
        self.assertEqual(record["projectRoot"], str(group))
        self.start_server()
        self.assertEqual(self.get(file_url(group / "avatar.png"))[0], 200)
        # The folder around it: its parent used to be served, which could be a home directory.
        self.assertEqual(self.get(file_url(self.outside / "other.mp4"))[0], 404)

    def test_a_stored_root_counts_only_if_it_is_a_project(self):
        # Records from older versions stored a group's parent folder as its root.
        self.assertEqual(served_root({"projectRoot": str(self.outside.parent), "target": str(self.outside)}),
                         str(self.outside))
        self.assertEqual(served_root({"projectRoot": str(self.project), "target": str(self.batch)}), str(self.project))

    def test_a_home_folder_holding_memory_is_still_not_a_project(self):
        # An agent once ran a memory command from a home folder; that must not serve the home folder.
        from unittest.mock import patch
        import review_workspace
        home = self.outside
        (home / ".viewprinter" / "content-memory").mkdir(parents=True)
        with patch("pathlib.Path.home", return_value=home):
            self.assertIsNone(review_workspace.project_root(home / "launch"))
            self.assertEqual(served_root({"projectRoot": str(home), "target": str(home / "launch")}), str(home / "launch"))

    def test_network_and_escaping_paths_are_refused_before_the_disk(self):
        from unittest.mock import patch
        import review_workspace
        self.assertIsNone(url_path("/etc/passwd"))  # /files//etc/passwd
        self.assertIsNone(url_path(quote("\\\\host\\share\\x.png")))
        with patch.object(review_workspace.os, "name", "nt"):
            for network in ("%5C%5Chost%5Cshare%5Cx.png", "/host/share/x.png", "%5C%5C%3F%5CC%3A%5Cx.png", "C%3Ax.png"):
                self.assertIsNone(url_path(network), network)
            self.assertEqual(url_path("C%3A/Media/x.png"), os.path.normpath("C:/Media/x.png"))

    def test_pdf_preview_is_served_with_pdf_type_from_registered_project(self):
        document = self.project / "documents" / "complete.pdf"
        document.parent.mkdir()
        document.write_bytes(b"%PDF-1.4\nexample")
        self.hub("add", str(self.batch), "--no-server")
        self.start_server()
        with DIRECT.open(f"http://127.0.0.1:{self.port}" + file_url(document), timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertTrue(response.headers.get("Content-Type", "").startswith("application/pdf"))
            self.assertTrue(response.read().startswith(b"%PDF-"))
        outside = self.outside / "private.pdf"
        outside.write_bytes(b"%PDF-1.4\nprivate")
        self.assertNotEqual(self.get(file_url(outside))[0], 200)

    def test_file_urls_carry_windows_drive_paths(self):
        from pathlib import PureWindowsPath
        self.assertEqual(file_url(PureWindowsPath(r"D:\Media\Clips\a b.mp4")), "/files/D%3A/Media/Clips/a%20b.mp4")
        clip = self.batch / "clip.mp4"
        self.assertEqual(url_path(file_url(clip)[len("/files/"):]), str(clip))

    def test_http_writes_require_origin_token_and_current_revision(self):
        import re
        self.hub('add',str(self.batch),'--no-server');self.start_server()
        _,page=self.get('/');token=re.search(b'name="vp-token" content="([^"]+)"',page).group(1).decode()
        def post(headers,revision=1):
            payload=json.dumps({'entry':'project--batch-one','action':'archive','revision':revision}).encode()
            request=urllib.request.Request(f'http://127.0.0.1:{self.port}/api/lifecycle',data=payload,headers=headers)
            try:
                with DIRECT.open(request,timeout=10) as response:return response.status
            except urllib.error.HTTPError as e:return e.code
        self.assertEqual(post({}),403)
        headers={'Origin':f'http://127.0.0.1:{self.port}','X-ViewPrinter-Token':token}
        self.assertEqual(post(headers,99),409);self.assertEqual(post(headers),200)
        self.assertEqual(self.entries(),[])

    def test_pdf_checker_verifies_attachment_and_rejects_other_origins(self):
        from review_hub import check_pdf_attachment
        document = self.project / "complete.pdf"
        document.write_bytes(b"%PDF-1.4\nexample")
        self.hub("add", str(self.batch), "--no-server")
        self.start_server()
        gallery = f"http://127.0.0.1:{self.port}" + file_url(self.batch / "review.html")
        attachment = {"src": "complete.pdf", "url": f"http://127.0.0.1:{self.port}" + file_url(document)}
        self.assertTrue(check_pdf_attachment(attachment, gallery)["ok"])
        document.write_bytes(b"not a PDF")
        self.assertFalse(check_pdf_attachment(attachment, gallery)["ok"])
        attachment["url"] = "https://example.invalid/complete.pdf"
        self.assertIn("origin", check_pdf_attachment(attachment, gallery)["error"])

    def test_legacy_download_link_survives_a_source_namespace_only_if_unique(self):
        from review_hub import find_download
        first = {"id": "source-012345abcdef-brief", "path": "one.pdf"}
        second = {"id": "source-abcdef012345-brief", "path": "two.pdf"}
        self.assertEqual(find_download({"downloads": [first]}, "brief"), first)
        self.assertIsNone(find_download({"downloads": [first, second]}, "brief"))
        self.assertEqual(find_download({"downloads": [first, second]}, first["id"]), first)
        self.assertIsNone(find_download({"downloads": [first]}, "unknown"))

    def test_symlink_escape_and_explicit_download(self):
        manifest=self.batch/'review.json';data=json.loads(manifest.read_text(encoding="utf-8"));data['downloads']=[{'id':'brief','title':'Brief','path':'review.json'}];manifest.write_text(json.dumps(data), encoding="utf-8")
        (self.batch/'escape.mp4').symlink_to(self.outside/'other.mp4')
        self.hub('add',str(self.batch),'--no-server');self.start_server()
        self.assertEqual(self.get(file_url(self.batch/'escape.mp4'))[0],404)
        self.assertEqual(self.get(file_url(manifest))[0],404)
        self.assertEqual(self.get('/downloads/project--batch-one/brief')[0],200)
        self.assertEqual(self.get('/downloads/project--batch-one/unknown')[0],404)

    @unittest.skipUnless(shutil.which("ffmpeg") and chrome_available(), "needs ffmpeg and Chrome")
    def test_check_plays_a_gallery_headless(self):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=2",
                        "-pix_fmt", "yuv420p", "-c:v", "libx264", str(self.batch / "play.mp4")], check=True, timeout=60)
        (self.batch / "review.html").write_text(
            '<title>Play test</title><video src="play.mp4" preload="metadata"></video><button>Copy ID</button>',
            encoding="utf-8")
        data=json.loads((self.batch/'review.json').read_text(encoding="utf-8"))
        for item in data['items']:item['src']='play.mp4'
        if self._testMethodName=='test_check_plays_a_gallery_headless':data['items']=data['items'][:1]
        else:data['items'][0]['previous']={'kind':'video','src':'play.mp4','version':0}
        (self.batch/'review.json').write_text(json.dumps(data), encoding="utf-8")
        self.hub("add", str(self.batch), "--no-server")
        self.start_server()
        result = subprocess.run([sys.executable, str(HUB), "check", str(self.batch), "--seconds", "3", "--json"],
                                env=self.env, capture_output=True, text=True, timeout=120, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        record=json.loads((self.hub_root/".hub/entries/project--batch-one.json").read_text(encoding="utf-8"))
        self.assertEqual(report["url"], f"http://127.0.0.1:{self.port}" + file_url(record["gallery"]))
        self.assertEqual(report["problems"], [])
        self.assertGreater(report["playback"]["position"], 1.5)
        self.assertEqual((len(report["media"]), report["copyIds"]), (1, 1))

    @unittest.skipUnless(shutil.which("ffmpeg") and chrome_available(), "needs ffmpeg and Chrome")
    def test_check_all_current_uses_served_gallery_and_excludes_history(self):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=blue:size=160x240:rate=10:duration=1",
                        "-pix_fmt", "yuv420p", "-c:v", "libx264", str(self.batch / "play.mp4")], check=True, timeout=60)
        (self.batch / "review.html").write_text(
            '<title>All current</title>'
            '<article><button class="copy-reference" data-copy-reference="A / v1">Copy ID</button>'
            '<div class="previews"><video src="play.mp4"></video></div>'
            '<details><video src="play.mp4"></video></details></article>'
            '<article><button class="copy-reference" data-copy-reference="B / v1">Copy ID</button>'
            '<div class="previews"><video src="play.mp4"></video></div></article>', encoding="utf-8")
        data=json.loads((self.batch/'review.json').read_text(encoding="utf-8"))
        for item in data['items']:item['src']='play.mp4'
        if self._testMethodName=='test_check_plays_a_gallery_headless':data['items']=data['items'][:1]
        else:data['items'][0]['previous']={'kind':'video','src':'play.mp4','version':0}
        (self.batch/'review.json').write_text(json.dumps(data), encoding="utf-8")
        self.hub("add", str(self.batch), "--no-server")
        self.start_server()
        result = subprocess.run([sys.executable, str(HUB), "check", str(self.batch), "--all-current", "--seconds", "1", "--json"],
                                env=self.env, capture_output=True, text=True, timeout=120, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["servedOverHttp"])
        self.assertTrue(report["checkedAllCurrent"])
        self.assertEqual(report["currentPreviews"], 2)
        self.assertEqual(len(report["media"]), 3)
        self.assertEqual([p["reference"] for p in report["playbacks"]], ["A / v1", "B / v1"])
        self.assertTrue(all(p["ok"] for p in report["playbacks"]))
        self.assertEqual(report["problems"], [])

    def test_page_follows_the_folder_live(self):
        self.start_server()
        with DIRECT.open(f"http://127.0.0.1:{self.port}/api/events", timeout=8) as stream:
            def next_queue():
                for line in stream:
                    if line.startswith(b"data: "):
                        return json.loads(line[6:])
                self.fail("event stream ended")
            self.assertEqual(next_queue()["entries"], [])
            self.hub("add", str(self.batch), "--no-server")
            self.assertEqual([entry["name"] for entry in next_queue()["entries"]], ["project--batch-one"])
            self.hub("archive", "project--batch-one")
            update = next_queue()
            self.assertEqual((update["entries"], len(update["posted"])), ([], 1))


class HubEfficiencyTests(unittest.TestCase):
    def make_hub(self):
        import review_hub
        from unittest.mock import patch
        with patch.object(review_hub,'scan',return_value=({'entries':[]},set(),set())):
            return review_hub.Hub()

    def test_background_tab_is_reused_but_does_not_trigger_fast_polling(self):
        import review_hub
        from unittest.mock import patch
        hub=self.make_hub()
        with patch.object(review_hub.time,'monotonic',return_value=10):hub.presence('hidden')
        with patch.object(review_hub.time,'monotonic',return_value=70):
            self.assertEqual(hub.tab_count(),1)
            self.assertEqual(hub.poll_interval(),15)
            with patch.object(review_hub,'ensure_server',return_value='http://127.0.0.1:8765/'), patch.object(review_hub,'ping',return_value={'clients':0,'tabs':hub.tab_count()}), patch.object(review_hub.subprocess,'run') as launch, patch.object(review_hub.webbrowser,'open') as browser:
                self.assertFalse(review_hub.open_hub()[1]);launch.assert_not_called();browser.assert_not_called()
        with patch.object(review_hub.time,'monotonic',return_value=191):self.assertEqual(hub.tab_count(),0)

    @unittest.skipUnless(shutil.which("node"), "needs Node.js for the workspace lifecycle check")
    def test_hidden_workspace_pauses_media_releases_stream_and_keeps_presence(self):
        script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(process.argv[1],'utf8');
const source=html.slice(html.lastIndexOf("window.addEventListener('hashchange',route)"),html.lastIndexOf('</script>'));
const handlers={},nodes={},streams=[],requests=[];let paused=0,refreshes=0,heartbeat;
class Stream {constructor(){this.closed=false;streams.push(this)}addEventListener(){}close(){this.closed=true}}
const document={hidden:false,querySelector:()=>({content:'token'}),addEventListener:(name,fn)=>handlers[name]=fn};
vm.runInNewContext(source,{window:{addEventListener:(name,fn)=>handlers[name]=fn},document,EventSource:Stream,
crypto:{randomUUID:()=> 'test-tab'},state:{frames:new Map([['review',{}]])},pause:()=>paused++,route(){},apply(){},
refresh:()=>{refreshes++;return Promise.resolve()},toast(){},$:(id)=>nodes[id]||(nodes[id]={}),
fetch:(url,options)=>{requests.push({url,...options});return Promise.resolve({ok:true})},
setInterval:(fn,ms)=>{assert.equal(ms,60000);heartbeat=fn;return 1},clearInterval(){}});
const connected=()=>streams.filter(s=>!s.closed).length;
assert.equal(connected(),1);assert.equal(refreshes,1);
document.hidden=true;handlers.visibilitychange();assert.equal(connected(),0);assert.equal(paused,1);
heartbeat();assert.equal(JSON.parse(requests.at(-1).body).open,true);
document.hidden=false;handlers.visibilitychange();assert.equal(connected(),1);assert.equal(refreshes,2);
handlers.pagehide();assert.equal(connected(),0);assert.equal(JSON.parse(requests.at(-1).body).open,false);
handlers.pageshow({persisted:true});assert.equal(connected(),1);assert.equal(JSON.parse(requests.at(-1).body).open,true);
"""
        result=subprocess.run([shutil.which("node"),"-e",script,str(SCRIPTS.parent/'assets/review-workspace.html')],capture_output=True,text=True,timeout=10,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_connect_wakes_idle_watcher_and_slow_stream_keeps_only_latest_state(self):
        import queue
        hub=self.make_hub();listener=queue.Queue(maxsize=1)
        hub.join(listener)
        self.assertTrue(hub.wake.is_set());self.assertEqual(hub.poll_interval(),2)
        for number in range(1000):hub.offer(listener,str(number))
        self.assertEqual(listener.qsize(),1);self.assertEqual(listener.get_nowait(),'999')
        hub.leave(listener);self.assertEqual(hub.poll_interval(),15)


if __name__ == "__main__":
    unittest.main()
