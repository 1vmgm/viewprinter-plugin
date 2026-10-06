"""Run: python -m unittest discover -s scripts -p 'test_review_hub.py'."""

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
from urllib.parse import quote
import urllib.request

SCRIPTS = Path(__file__).resolve().parent
HUB = SCRIPTS / "review_hub.py"
GALLERY = SCRIPTS / "review_gallery.py"
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
        (self.batch / "secret.env").write_text("TOKEN=1\n")
        (self.batch / "review.html").write_text(
            "<title>THIS SESSION — Project: Batch one / round 2</title>"
            '<article data-status="needs-review"></article><article data-status="approved"></article>',
            encoding="utf-8")
        (self.batch / 'review.json').write_text(json.dumps({
            'title':'THIS SESSION — Project: Batch one / round 2','round':2,
            'reviewHub':{'kind':'social-content','formatId':'batch-one'},
            'items':[{'id':'A','version':1,'title':'A','format':'portrait','status':'needs-review','src':'clip.mp4','kind':'video'},
                     {'id':'B','version':1,'title':'B','format':'portrait','status':'approved','src':'clip.mp4','kind':'video'}]}))
        self.outside = base / "outside"
        self.outside.mkdir()
        (self.outside / "other.mp4").write_bytes(b"x" * 10)
        self.hub_root = base / "hub"
        self.port = free_port()
        self.env = dict(os.environ, VIEWPRINTER_REVIEW_ROOT=str(self.hub_root),
                        VIEWPRINTER_REVIEW_PORT=str(self.port), VIEWPRINTER_REVIEW_AUTOSTART="0")

    def hub(self, *args):
        result = subprocess.run([sys.executable, str(HUB), *args], env=self.env,
                                capture_output=True, text=True, timeout=30)
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

    def test_add_links_the_batch_once(self):
        self.hub("add", str(self.batch / "review.html"), "--no-server")
        self.hub("add", str(self.batch), "--no-server")
        self.assertEqual(self.entries(), ["project--batch-one"])
        link = self.hub_root / "in-review" / "project--batch-one"
        self.assertTrue(link.is_symlink())
        record=json.loads((self.hub_root/".hub/entries/project--batch-one.json").read_text())
        self.assertEqual(os.path.realpath(link), str(Path(record["gallery"]).parent))
        self.assertEqual(record["sources"][0]["manifest"], str(self.batch/"review.json"))

    def test_archive_freezes_review_and_restores_same_id(self):
        self.hub("add", str(self.batch), "--no-server")
        self.hub("archive", "project--batch-one", "--reason", "Finished review")
        self.assertEqual(self.entries(), [])
        record = json.loads((self.hub_root/'.hub/entries/project--batch-one.json').read_text())
        original = Path(record['snapshotGallery']).read_text()
        (self.batch/'review.html').write_text('New version')
        self.assertEqual(Path(record['snapshotGallery']).read_text(), original)
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
                                    env=self.env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), str(folder / "review.html"))
            notes.append(result.stderr)
        self.assertEqual(self.entries(), ["project--pending"])
        self.assertIn("review hub", notes[0])
        self.assertEqual(notes[1], "")

    def test_server_lists_entries_and_serves_only_review_files(self):
        self.hub("add", str(self.batch), "--no-server")
        sibling = self.project / "sibling"
        sibling.mkdir()
        (sibling / "shared.mp4").write_bytes(b"s" * 8)
        (sibling / "page.html").write_text("<p>not an entry</p>")
        self.start_server()
        status, body = self.get("/api/queue")
        [entry] = json.loads(body)["entries"]
        self.assertEqual((entry["project"], entry["label"]), ("Project", "Batch one / round 2"))
        self.assertEqual(entry["summary"], {"items": 2, "review": 1, "progress": 0, "approved": 1})
        batch = "/files" + quote(str(self.batch))
        self.assertEqual(self.get(entry["url"])[0], 200)
        self.assertEqual(self.get(batch + "/clip.mp4", Range="bytes=2-5"), (206, bytes([2, 3, 4, 5])))
        self.assertEqual(self.get(batch + "/clip.mp4", Range="bytes=-3"), (206, bytes([61, 62, 63])))
        self.assertEqual(self.get("/files" + quote(str(sibling / "shared.mp4")))[0], 200)
        self.assertEqual(self.get("/files" + quote(str(sibling / "page.html")))[0], 404)
        self.assertEqual(self.get(batch + "/secret.env")[0], 404)
        self.assertEqual(self.get("/files" + quote(str(self.outside / "other.mp4")))[0], 404)
        self.assertEqual(self.get(batch + "/../../../outside/other.mp4")[0], 404)
        self.assertEqual(self.get("/api/queue", Host="attacker.example")[0], 403)

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

    def test_symlink_escape_and_explicit_download(self):
        manifest=self.batch/'review.json';data=json.loads(manifest.read_text());data['downloads']=[{'id':'brief','title':'Brief','path':'review.json'}];manifest.write_text(json.dumps(data))
        (self.batch/'escape.mp4').symlink_to(self.outside/'other.mp4')
        self.hub('add',str(self.batch),'--no-server');self.start_server()
        self.assertEqual(self.get('/files'+quote(str(self.batch/'escape.mp4')))[0],404)
        self.assertEqual(self.get('/files'+quote(str(manifest)))[0],404)
        self.assertEqual(self.get('/downloads/project--batch-one/brief')[0],200)
        self.assertEqual(self.get('/downloads/project--batch-one/unknown')[0],404)

    @unittest.skipUnless(shutil.which("ffmpeg") and chrome_available(), "needs ffmpeg and Chrome")
    def test_check_plays_a_gallery_headless(self):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=2",
                        "-pix_fmt", "yuv420p", "-c:v", "libx264", str(self.batch / "play.mp4")], check=True, timeout=60)
        (self.batch / "review.html").write_text(
            '<title>Play test</title><video src="play.mp4" preload="metadata"></video><button>Copy ID</button>',
            encoding="utf-8")
        data=json.loads((self.batch/'review.json').read_text())
        for item in data['items']:item['src']='play.mp4'
        if self._testMethodName=='test_check_plays_a_gallery_headless':data['items']=data['items'][:1]
        else:data['items'][0]['previous']={'kind':'video','src':'play.mp4','version':0}
        (self.batch/'review.json').write_text(json.dumps(data))
        self.hub("add", str(self.batch), "--no-server")
        self.start_server()
        result = subprocess.run([sys.executable, str(HUB), "check", str(self.batch), "--seconds", "3", "--json"],
                                env=self.env, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        record=json.loads((self.hub_root/".hub/entries/project--batch-one.json").read_text())
        self.assertEqual(report["url"], f"http://127.0.0.1:{self.port}/files" + quote(record["gallery"]))
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
        data=json.loads((self.batch/'review.json').read_text())
        for item in data['items']:item['src']='play.mp4'
        if self._testMethodName=='test_check_plays_a_gallery_headless':data['items']=data['items'][:1]
        else:data['items'][0]['previous']={'kind':'video','src':'play.mp4','version':0}
        (self.batch/'review.json').write_text(json.dumps(data))
        self.hub("add", str(self.batch), "--no-server")
        self.start_server()
        result = subprocess.run([sys.executable, str(HUB), "check", str(self.batch), "--all-current", "--seconds", "1", "--json"],
                                env=self.env, capture_output=True, text=True, timeout=120)
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


if __name__ == "__main__":
    unittest.main()
