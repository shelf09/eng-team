import json
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
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


class HeyGenLipsyncCliTests(unittest.TestCase):
    def test_live_run_requires_explicit_upload_confirmation(self):
        module = load_script("heygen_lipsync.py")

        with mock.patch.dict(os.environ, {"HEYGEN_API_KEY": "heygen-test-key"}, clear=False):
            with mock.patch.object(module, "asset_input", return_value={"type": "asset_id", "asset_id": "test"}):
                with mock.patch.object(module, "api", return_value={}):
                    with mock.patch.object(sys, "argv", [
                        "heygen_lipsync.py",
                        "--video",
                        "scene.mp4",
                        "--audio",
                        "voice.wav",
                    ]):
                        with self.assertRaisesRegex(SystemExit, "--confirm-upload"):
                            module.main()

    def test_rejects_nonpositive_or_nonfinite_polling_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "scene.mp4"
            audio = tmp_path / "voice.wav"
            video.write_bytes(b"video")
            audio.write_bytes(b"audio")

            cases = [
                ("--poll-interval", "0", "--poll-interval must be a positive finite number"),
                ("--timeout", "nan", "--timeout must be a positive finite number"),
            ]
            for option, value, message in cases:
                with self.subTest(option=option, value=value):
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(SCRIPTS / "heygen_lipsync.py"),
                            "--video",
                            str(video),
                            "--audio",
                            str(audio),
                            option,
                            value,
                            "--dry-run",
                        ],
                        cwd=ROOT,
                        text=True,
                        capture_output=True,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(message, result.stderr)

    def test_dry_run_builds_precision_request_from_local_video_and_voice_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "scene.mp4"
            audio = tmp_path / "local-voice.wav"
            video.write_bytes(b"video")
            audio.write_bytes(b"audio")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "heygen_lipsync.py"),
                    "--video",
                    str(video),
                    "--audio",
                    str(audio),
                    "--mode",
                    "precision",
                    "--out",
                    "synced.mp4",
                    "--dry-run",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertEqual(plan["POST"], "https://api.heygen.com/v3/lipsyncs")
            self.assertEqual(plan["body"]["mode"], "precision")
            self.assertFalse(plan["body"]["enable_dynamic_duration"])
            self.assertEqual(plan["out"], "synced.mp4")
            self.assertEqual(plan["body"]["video"]["type"], "asset_id")
            self.assertIn(str(video), plan["body"]["video"]["asset_id"])
            self.assertEqual(plan["body"]["audio"]["type"], "asset_id")
            self.assertIn(str(audio), plan["body"]["audio"]["asset_id"])

    def test_dry_run_can_allow_heygen_to_change_the_shot_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "scene.mp4"
            audio = tmp_path / "voice.wav"
            video.write_bytes(b"video")
            audio.write_bytes(b"audio")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "heygen_lipsync.py"),
                    "--video",
                    str(video),
                    "--audio",
                    str(audio),
                    "--dynamic-duration",
                    "--dry-run",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)["body"]["enable_dynamic_duration"])

    def test_dry_run_rejects_an_unsupported_local_audio_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "scene.mp4"
            audio = tmp_path / "voice.aiff"
            video.write_bytes(b"video")
            audio.write_bytes(b"audio")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "heygen_lipsync.py"),
                    "--video",
                    str(video),
                    "--audio",
                    str(audio),
                    "--dry-run",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("audio input must be MP3 or WAV", result.stderr)

    def test_dry_run_rejects_a_local_asset_over_the_simple_upload_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "large.mp4"
            audio = tmp_path / "voice.wav"
            with video.open("wb") as target:
                target.truncate(32 * 1024 * 1024 + 1)
            audio.write_bytes(b"audio")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "heygen_lipsync.py"),
                    "--video",
                    str(video),
                    "--audio",
                    str(audio),
                    "--dry-run",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("exceeds HeyGen's 32 MB simple-upload limit", result.stderr)

    def test_dry_run_rejects_video_and_audio_files_in_the_wrong_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "scene.mp4"
            audio = tmp_path / "voice.wav"
            video.write_bytes(b"video")
            audio.write_bytes(b"audio")

            cases = [
                (audio, audio, "video input must be MP4 or WebM"),
                (video, video, "audio input must be MP3 or WAV"),
            ]
            for video_arg, audio_arg, message in cases:
                with self.subTest(message=message):
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(SCRIPTS / "heygen_lipsync.py"),
                            "--video",
                            str(video_arg),
                            "--audio",
                            str(audio_arg),
                            "--dry-run",
                        ],
                        cwd=ROOT,
                        text=True,
                        capture_output=True,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(message, result.stderr)

    def test_dry_run_rejects_video_and_audio_urls_in_the_wrong_fields(self):
        cases = [
            (
                "https://cdn.example.test/voice.wav",
                "https://cdn.example.test/voice.wav",
                "video input must be MP4 or WebM",
            ),
            (
                "https://cdn.example.test/scene.mp4",
                "https://cdn.example.test/scene.mp4",
                "audio input must be MP3 or WAV",
            ),
        ]
        for video, audio, message in cases:
            with self.subTest(message=message):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPTS / "heygen_lipsync.py"),
                        "--video",
                        video,
                        "--audio",
                        audio,
                        "--dry-run",
                    ],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)

    def test_dry_run_rejects_a_non_mp4_output_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "scene.mp4"
            audio = tmp_path / "voice.wav"
            video.write_bytes(b"video")
            audio.write_bytes(b"audio")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "heygen_lipsync.py"),
                    "--video",
                    str(video),
                    "--audio",
                    str(audio),
                    "--out",
                    "synced.wav",
                    "--dry-run",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--out must end in .mp4", result.stderr)

    def test_live_run_uploads_local_media_polls_and_downloads_completed_video(self):
        module = load_script("heygen_lipsync.py")
        api_calls = []

        def fake_api(method, path, key, body=None):
            api_calls.append((method, path, key, body))
            if method == "POST":
                return {"data": {"lipsync_id": "lip-123"}}
            poll_number = sum(1 for call in api_calls if call[0] == "GET")
            if poll_number == 1:
                return {"data": {"status": "pending"}}
            if poll_number == 2:
                return {"data": {"status": "running"}}
            return {
                "data": {
                    "status": "completed",
                    "video_url": "https://cdn.example/synced.mp4",
                }
            }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "scene.mp4"
            audio = tmp_path / "voice.wav"
            output = tmp_path / "synced.mp4"
            video.write_bytes(b"video")
            audio.write_bytes(b"audio")

            with mock.patch.dict(os.environ, {"HEYGEN_API_KEY": "heygen-test-key"}, clear=False):
                with mock.patch.object(
                    module, "upload_asset", side_effect=["video-asset", "audio-asset"], create=True
                ) as upload:
                    with mock.patch.object(module, "api", side_effect=fake_api, create=True):
                        with mock.patch.object(module, "download", create=True) as download:
                            with mock.patch("time.sleep", return_value=None):
                                with mock.patch.object(sys, "argv", [
                                        "heygen_lipsync.py",
                                        "--video",
                                        str(video),
                                        "--audio",
                                        str(audio),
                                        "--mode",
                                        "precision",
                                        "--poll-interval",
                                        "0.001",
                                        "--confirm-upload",
                                        "--out",
                                        str(output),
                                ]):
                                    with mock.patch.object(sys, "stdout", io.StringIO()):
                                        with mock.patch.object(sys, "stderr", io.StringIO()):
                                            try:
                                                module.main()
                                            except (SystemExit, NotImplementedError) as exc:
                                                self.fail(f"HeyGen lipsync exited early: {exc}")

            self.assertEqual(
                upload.call_args_list,
                [mock.call(str(video), "heygen-test-key"), mock.call(str(audio), "heygen-test-key")],
            )
            post = api_calls[0]
            self.assertEqual(post[:3], ("POST", "/v3/lipsyncs", "heygen-test-key"))
            self.assertEqual(post[3]["video"], {"type": "asset_id", "asset_id": "video-asset"})
            self.assertEqual(post[3]["audio"], {"type": "asset_id", "asset_id": "audio-asset"})
            self.assertEqual(post[3]["mode"], "precision")
            self.assertEqual([call[1] for call in api_calls[1:]], [
                "/v3/lipsyncs/lip-123",
                "/v3/lipsyncs/lip-123",
                "/v3/lipsyncs/lip-123",
            ])
            download.assert_called_once_with("https://cdn.example/synced.mp4", str(output))

    def test_live_run_reports_a_download_failure_cleanly(self):
        module = load_script("heygen_lipsync.py")

        def fake_api(method, _path, _key, _body=None):
            if method == "POST":
                return {"data": {"lipsync_id": "lip-123"}}
            return {
                "data": {
                    "status": "completed",
                    "video_url": "https://cdn.example/synced.mp4",
                }
            }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "scene.mp4"
            audio = tmp_path / "voice.wav"
            output = tmp_path / "synced.mp4"
            video.write_bytes(b"video")
            audio.write_bytes(b"audio")

            with mock.patch.dict(os.environ, {"HEYGEN_API_KEY": "heygen-test-key"}, clear=False):
                with mock.patch.object(module, "upload_asset", side_effect=["video", "audio"]):
                    with mock.patch.object(module, "api", side_effect=fake_api):
                        with mock.patch.object(module, "download", side_effect=OSError("truncated")):
                            with mock.patch.object(sys, "argv", [
                                "heygen_lipsync.py",
                                "--video", str(video),
                                "--audio", str(audio),
                                "--out", str(output),
                                "--confirm-upload",
                            ]):
                                with mock.patch.object(sys, "stderr", io.StringIO()):
                                    with self.assertRaisesRegex(
                                        SystemExit, "could not download completed video"
                                    ):
                                        module.main()


class CharacterVoiceCliTests(unittest.TestCase):
    def test_non_utf8_text_file_fails_without_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            text_file = Path(tmp) / "script.txt"
            text_file.write_bytes(b"not utf-8: \xff")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "character_voice.py"),
                    "--provider", "elevenlabs",
                    "--text-file", str(text_file),
                    "--voice-id", "voice-123",
                    "--dry-run",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must be valid UTF-8", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_local_provider_rejects_an_unknown_macos_voice(self):
        module = load_script("character_voice.py")
        voice_list = subprocess.CompletedProcess(
            ["/usr/bin/say", "-v", "?"],
            0,
            stdout=(
                "Samantha           en_US    # Hello! My name is Samantha.\n"
                "Ava (Premium)       en_US    # Hello! My name is Ava.\n"
            ),
            stderr="",
        )

        with mock.patch.object(module.shutil, "which", return_value="/usr/bin/say"):
            with mock.patch.object(module.subprocess, "run", return_value=voice_list) as run:
                with mock.patch.object(sys, "argv", [
                    "character_voice.py",
                    "--provider",
                    "local",
                    "--text",
                    "Voice names should not silently fall back.",
                    "--local-voice",
                    "Definitely Missing",
                    "--out",
                    "voice.wav",
                    "--dry-run",
                ]):
                    with self.assertRaisesRegex(SystemExit, "not an installed macOS voice"):
                        module.main()

        run.assert_called_once()

    def test_local_provider_rejects_a_nonpositive_rate(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "character_voice.py"),
                "--provider",
                "local",
                "--text",
                "Pacing must be positive.",
                "--local-voice",
                "Samantha",
                "--rate",
                "0",
                "--out",
                "voice.wav",
                "--dry-run",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env={"PATH": os.environ.get("PATH", "")},
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--rate must be positive", result.stderr)

    def test_elevenlabs_dry_run_rejects_an_unsupported_output_format(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "character_voice.py"),
                "--provider",
                "elevenlabs",
                "--text",
                "Do not write MP3 bytes under an AIFF extension.",
                "--voice-id",
                "voice-123",
                "--out",
                "voice.aiff",
                "--dry-run",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env={"PATH": os.environ.get("PATH", "")},
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ElevenLabs output must end in .mp3 or .wav", result.stderr)

    def test_elevenlabs_dry_run_builds_tts_request_without_requiring_a_key(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "character_voice.py"),
                "--provider",
                "elevenlabs",
                "--text",
                "That is three buzzwords in a trench coat.",
                "--voice-id",
                "voice-123",
                "--out",
                "engineer.wav",
                "--dry-run",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env={"PATH": os.environ.get("PATH", "")},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["provider"], "elevenlabs")
        self.assertEqual(
            plan["POST"],
            "https://api.elevenlabs.io/v1/text-to-speech/voice-123?output_format=mp3_44100_128",
        )
        self.assertEqual(plan["body"]["model_id"], "eleven_v3")
        self.assertEqual(plan["body"]["text"], "That is three buzzwords in a trench coat.")
        self.assertEqual(plan["out"], "engineer.wav")

    def test_local_dry_run_uses_macos_voice_without_a_cloud_key(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "character_voice.py"),
                "--provider",
                "local",
                "--text",
                "No. But you get synergy.",
                "--local-voice",
                "Samantha",
                "--rate",
                "185",
                "--out",
                "boss.wav",
                "--dry-run",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env={"PATH": os.environ.get("PATH", "")},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["provider"], "local")
        self.assertTrue(plan["command"][0].endswith("say"))
        self.assertIn("Samantha", plan["command"])
        self.assertIn("185", plan["command"])
        self.assertEqual(plan["stdin"], "No. But you get synergy.")
        self.assertEqual(plan["out"], "boss.wav")

    def test_local_provider_rejects_a_non_wav_output_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "voice.mp3"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "character_voice.py"),
                    "--provider",
                    "local",
                    "--text",
                    "Do not disguise WAV bytes as MP3.",
                    "--local-voice",
                    "Samantha",
                    "--out",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("local voice output must end in .wav", result.stderr)

    @unittest.skipUnless(shutil.which("say") and shutil.which("ffprobe"), "requires macOS say and ffprobe")
    def test_local_provider_renders_a_valid_wav(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "local.wav"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "character_voice.py"),
                    "--provider",
                    "local",
                    "--text",
                    "Local character voice test.",
                    "--local-voice",
                    "Samantha",
                    "--out",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.exists())
            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "a:0",
                    "-show_entries",
                    "stream=codec_name,sample_rate,channels",
                    "-of",
                    "json",
                    str(output),
                ],
                text=True,
                capture_output=True,
                check=True,
            )
            stream = json.loads(probe.stdout)["streams"][0]
            self.assertEqual(stream["codec_name"], "pcm_s16le")
            self.assertEqual(stream["sample_rate"], "44100")
            self.assertEqual(stream["channels"], 1)

    def test_elevenlabs_provider_writes_returned_mp3(self):
        module = load_script("character_voice.py")
        captured = {}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return b"ID3-local-test-audio"

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return Response()

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "voice.mp3"
            with mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key"}, clear=False):
                with mock.patch.object(module, "open_authenticated", side_effect=fake_urlopen):
                    with mock.patch.object(sys, "argv", [
                            "character_voice.py",
                            "--provider",
                            "elevenlabs",
                            "--text",
                            "Hello from ElevenLabs.",
                            "--voice-id",
                            "voice-123",
                            "--out",
                            str(output),
                    ]):
                        with mock.patch.object(sys, "stdout", io.StringIO()):
                            try:
                                module.main()
                            except SystemExit as exc:
                                self.fail(f"ElevenLabs generation exited early: {exc}")

            self.assertEqual(output.read_bytes(), b"ID3-local-test-audio")
            self.assertEqual(captured["timeout"], 120)
            self.assertEqual(captured["request"].get_header("Xi-api-key"), "test-key")
            request_body = json.loads(captured["request"].data)
            self.assertEqual(request_body["text"], "Hello from ElevenLabs.")
            self.assertEqual(request_body["model_id"], "eleven_v3")

    def test_elevenlabs_output_write_failure_is_reported_cleanly(self):
        module = load_script("character_voice.py")

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return b"ID3-test-audio"

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "voice.mp3"
            with mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key"}, clear=False):
                with mock.patch.object(module, "open_authenticated", return_value=Response()):
                    with mock.patch.object(module.os, "replace", side_effect=OSError("read-only")):
                        with mock.patch.object(sys, "argv", [
                            "character_voice.py",
                            "--provider", "elevenlabs",
                            "--text", "Write error test.",
                            "--voice-id", "voice-123",
                            "--out", str(output),
                        ]):
                            with self.assertRaisesRegex(
                                SystemExit, "could not write ElevenLabs output"
                            ):
                                module.main()

            self.assertEqual(list(Path(tmp).iterdir()), [])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "requires ffmpeg")
    def test_elevenlabs_provider_can_transcode_the_response_to_wav(self):
        module = load_script("character_voice.py")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source.mp3"
            output = tmp_path / "voice.wav"
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=0.1",
                    str(source),
                ],
                check=True,
            )

            class Response:
                def __enter__(self):
                    return self

                def __exit__(self, *_):
                    return False

                def read(self):
                    return source.read_bytes()

            with mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key"}, clear=False):
                with mock.patch.object(module, "open_authenticated", return_value=Response()):
                    with mock.patch.object(sys, "argv", [
                            "character_voice.py",
                            "--provider",
                            "elevenlabs",
                            "--text",
                            "WAV output test.",
                            "--voice-id",
                            "voice-123",
                            "--out",
                            str(output),
                    ]):
                        with mock.patch.object(sys, "stdout", io.StringIO()):
                            try:
                                module.main()
                            except SystemExit as exc:
                                self.fail(f"ElevenLabs WAV generation exited early: {exc}")

            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "a:0",
                    "-show_entries",
                    "stream=codec_name,sample_rate,channels",
                    "-of",
                    "json",
                    str(output),
                ],
                text=True,
                capture_output=True,
                check=True,
            )
            stream = json.loads(probe.stdout)["streams"][0]
            self.assertEqual(stream["codec_name"], "pcm_s16le")
            self.assertEqual(stream["sample_rate"], "44100")
            self.assertEqual(stream["channels"], 1)


if __name__ == "__main__":
    unittest.main()
