import importlib.util
import io
import os
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".claude/skills/clone-video-creator/video-gen/scripts"


def load_script(name):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def redirect_server():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def record(self):
            requests.append({
                "method": self.command,
                "path": self.path,
                "headers": {key.lower(): value for key, value in self.headers.items()},
            })

        def do_GET(self):
            self.record()
            if self.path == "/sink":
                payload = b"{}"
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            self.send_response(302)
            self.send_header("Location", "/sink")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            self.record()
            self.send_response(302)
            self.send_header("Location", "/sink")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, _format, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@contextmanager
def truncated_response_server():
    payload = b"truncated-video"
    declared_length = len(payload) + 100
    request_count = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            request_count.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(declared_length))
            self.end_headers()
            self.wfile.write(payload)
            self.wfile.flush()
            self.close_connection = True

        def log_message(self, _format, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}/truncated.mp4", request_count
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class HeyGenMediaUrlSecurityTests(unittest.TestCase):
    def test_rejects_non_public_media_urls(self):
        module = load_script("heygen_lipsync.py")
        unsafe_urls = [
            "http://cdn.example.test/scene.mp4",
            "https://user:password@cdn.example.test/scene.mp4",
            "https://localhost/scene.mp4",
            "https://127.0.0.1/scene.mp4",
            "https://10.0.0.1/scene.mp4",
            "https://2130706433/scene.mp4",
            "https://127.1/scene.mp4",
            "https://0x7f000001/scene.mp4",
            "https://017700000001/scene.mp4",
        ]

        for url in unsafe_urls:
            with self.subTest(url=url):
                with self.assertRaises(SystemExit):
                    module.asset_input(url, dry_run=True, kind="video")


class AuthenticatedRedirectSecurityTests(unittest.TestCase):
    def test_heygen_api_does_not_follow_redirects(self):
        module = load_script("heygen_lipsync.py")

        with redirect_server() as (base_url, requests):
            module.BASE = base_url
            with self.assertRaises(SystemExit):
                module.api("GET", "/redirect", "heygen-secret")

        source = [request for request in requests if request["path"] == "/redirect"]
        sink = [request for request in requests if request["path"] == "/sink"]
        self.assertEqual(source[0]["headers"].get("x-api-key"), "heygen-secret")
        self.assertEqual(sink, [], "authenticated redirect target must not be requested")

    def test_elevenlabs_api_does_not_follow_redirects(self):
        module = load_script("character_voice.py")

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "voice.mp3"
            with redirect_server() as (base_url, requests):
                module.ELEVENLABS_BASE = base_url
                with mock.patch.dict(
                    os.environ, {"ELEVENLABS_API_KEY": "elevenlabs-secret"}, clear=False
                ):
                    with mock.patch.object(sys, "argv", [
                        "character_voice.py",
                        "--provider", "elevenlabs",
                        "--text", "Security redirect test.",
                        "--voice-id", "voice-123",
                        "--out", str(output),
                    ]):
                        with mock.patch.object(sys, "stdout", io.StringIO()):
                            with self.assertRaises(SystemExit):
                                module.main()

        source = [request for request in requests if request["path"].startswith("/v1/")]
        sink = [request for request in requests if request["path"] == "/sink"]
        self.assertEqual(source[0]["headers"].get("xi-api-key"), "elevenlabs-secret")
        self.assertEqual(sink, [], "authenticated redirect target must not be requested")


class OutputIntegritySecurityTests(unittest.TestCase):
    def test_download_rejects_private_url_before_opening_it(self):
        module = load_script("heygen_lipsync.py")

        with mock.patch.object(module.urllib.request, "urlopen") as urlopen:
            with self.assertRaises(SystemExit):
                module.download("https://127.0.0.1/synced.mp4", "synced.mp4")

        urlopen.assert_not_called()

    def test_truncated_download_preserves_existing_output(self):
        module = load_script("heygen_lipsync.py")

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "synced.mp4"
            original = b"existing-complete-video"
            output.write_bytes(original)

            with truncated_response_server() as (url, requests):
                with mock.patch.object(module, "validate_public_https_url", return_value=url):
                    try:
                        module.download(url, str(output))
                    except (Exception, SystemExit):
                        pass

            self.assertEqual(requests, ["/truncated.mp4"])
            self.assertEqual(output.read_bytes(), original)

    def test_local_say_failure_preserves_existing_output(self):
        module = load_script("character_voice.py")

        def failing_say(command, *_args, **_kwargs):
            if "-o" not in command:
                return module.subprocess.CompletedProcess(
                    command,
                    returncode=0,
                    stdout="Samantha                en_US    # Hello!\n",
                    stderr="",
                )
            rendered_path = Path(command[command.index("-o") + 1])
            rendered_path.write_bytes(b"partial-invalid-wave")
            return module.subprocess.CompletedProcess(
                command, returncode=1, stdout="", stderr="synthetic say failure"
            )

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "voice.wav"
            original = b"existing-complete-wave"
            output.write_bytes(original)

            with mock.patch.object(module.shutil, "which", return_value="/usr/bin/say"):
                with mock.patch.object(module.subprocess, "run", side_effect=failing_say):
                    with mock.patch.object(sys, "argv", [
                        "character_voice.py",
                        "--provider", "local",
                        "--local-voice", "Samantha",
                        "--text", "Preserve the prior output.",
                        "--out", str(output),
                    ]):
                        with mock.patch.object(sys, "stdout", io.StringIO()):
                            with self.assertRaises(SystemExit):
                                module.main()

            self.assertEqual(output.read_bytes(), original)


class MultipartUploadSecurityTests(unittest.TestCase):
    def test_multipart_filename_rejects_or_sanitizes_crlf(self):
        module = load_script("heygen_lipsync.py")

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'{"data":{"asset_id":"asset-123"}}'

        unsafe_names = [
            "voice\r\nX-Injected: yes.wav",
            "voice\nX-Injected: yes.wav",
            "voice\rX-Injected: yes.wav",
        ]

        with tempfile.TemporaryDirectory() as tmp:
            for unsafe_name in unsafe_names:
                with self.subTest(filename=repr(unsafe_name)):
                    source = Path(tmp) / unsafe_name
                    source.write_bytes(b"wave-data")
                    requests = []

                    def open_authenticated(request, timeout):
                        requests.append((request, timeout))
                        return Response()

                    with mock.patch.object(
                        module, "open_authenticated", side_effect=open_authenticated
                    ):
                        try:
                            module.upload_asset(str(source), "heygen-secret")
                        except (SystemExit, ValueError):
                            self.assertEqual(requests, [])
                            continue

                    self.assertEqual(len(requests), 1)
                    body = requests[0][0].data
                    self.assertNotIn(b"\r\nX-Injected:", body)
                    self.assertNotIn(b"\nX-Injected:", body)
                    self.assertNotIn(b"\rX-Injected:", body)


if __name__ == "__main__":
    unittest.main()
