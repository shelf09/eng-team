import json
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / ".claude/skills/clone-video-creator/video-gen/scripts/cartoon_voiceover.py"
)


def load_script():
    spec = importlib.util.spec_from_file_location("cartoon_voiceover", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CartoonVoiceoverTests(unittest.TestCase):
    def test_live_run_requires_top_level_upload_confirmation(self):
        module = load_script()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "shot.mp4").write_bytes(b"video")
            (project / "line.wav").write_bytes(b"audio")
            manifest = project / "cartoon.json"
            manifest.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "shots": [
                            {
                                "id": "shot-1",
                                "video": "shot.mp4",
                                "voice": {"provider": "existing", "path": "line.wav"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch.dict(os.environ, {"HEYGEN_API_KEY": "test-key"}, clear=False):
                with mock.patch.object(module.subprocess, "run") as run:
                    with mock.patch.object(sys, "argv", [
                        "cartoon_voiceover.py",
                        "--manifest", str(manifest),
                        "--work-dir", str(project / "rendered"),
                    ]):
                        stderr = io.StringIO()
                        with mock.patch.object(sys, "stderr", stderr):
                            result = module.main()

            self.assertEqual(result, 2)
            self.assertIn("--confirm-upload", stderr.getvalue())
            run.assert_not_called()

    def test_dry_run_forwards_per_shot_dynamic_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "shot.mp4").write_bytes(b"video")
            (project / "line.wav").write_bytes(b"audio")
            manifest = project / "cartoon.json"
            manifest.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "shots": [
                            {
                                "id": "shot-1",
                                "video": "shot.mp4",
                                "dynamic_duration": True,
                                "voice": {"provider": "existing", "path": "line.wav"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--manifest", str(manifest),
                    "--work-dir", str(project / "rendered"),
                    "--dry-run",
                ],
                cwd=ROOT,
                env={"PATH": os.environ.get("PATH", "")},
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            lipsync = json.loads(result.stdout)["steps"][0]["command"]
            self.assertIn("--dynamic-duration", lipsync)

    def test_dry_run_plans_all_voice_sources_in_shot_order_without_keys_or_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            for name in ("one.mp4", "two.mp4", "three.mp4"):
                (project / name).write_bytes(b"video")
            (project / "recorded.wav").write_bytes(b"audio")
            manifest = project / "cartoon.json"
            manifest.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "shots": [
                            {
                                "id": "intro",
                                "video": "one.mp4",
                                "voice": {
                                    "provider": "elevenlabs",
                                    "text": "Cloud line.",
                                    "voice_id": "voice-123",
                                },
                            },
                            {
                                "id": "reply",
                                "video": "two.mp4",
                                "mode": "speed",
                                "voice": {
                                    "provider": "local",
                                    "text": "Local line.",
                                    "voice": "Samantha",
                                    "rate": 180,
                                },
                            },
                            {
                                "id": "button",
                                "video": "three.mp4",
                                "voice": {
                                    "provider": "existing",
                                    "path": "recorded.wav",
                                },
                            },
                        ],
                        "concat": {"output": "episode.mp4"},
                    }
                ),
                encoding="utf-8",
            )
            work_dir = project / "rendered"
            env = {"PATH": os.environ.get("PATH", "")}

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--manifest",
                    str(manifest),
                    "--work-dir",
                    str(work_dir),
                    "--dry-run",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(work_dir.exists())
            plan = json.loads(result.stdout)
            self.assertTrue(plan["dry_run"])
            self.assertEqual(
                [(step["shot"], step["stage"]) for step in plan["steps"]],
                [
                    ("intro", "voice"),
                    ("intro", "lipsync"),
                    ("reply", "voice"),
                    ("reply", "lipsync"),
                    ("button", "lipsync"),
                    (None, "concat"),
                ],
            )
            voice_commands = [
                step["command"] for step in plan["steps"] if step["stage"] == "voice"
            ]
            self.assertIn("elevenlabs", voice_commands[0])
            self.assertIn("local", voice_commands[1])
            self.assertTrue(all("--dry-run" in command for command in voice_commands))
            lipsync_commands = [
                step["command"]
                for step in plan["steps"]
                if step["stage"] == "lipsync"
            ]
            self.assertTrue(all("--dry-run" in command for command in lipsync_commands))
            self.assertTrue(
                all("--confirm-upload" not in command for command in lipsync_commands)
            )
            self.assertIn(str((project / "recorded.wav").resolve()), lipsync_commands[2])
            self.assertEqual(plan["final_output"], str(work_dir / "episode.mp4"))

    def test_live_run_invokes_voice_then_lipsync_for_each_ordered_shot(self):
        module = load_script()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "one.mp4").write_bytes(b"video-one")
            (project / "two.mp4").write_bytes(b"video-two")
            (project / "recorded.mp3").write_bytes(b"audio")
            manifest = project / "cartoon.json"
            manifest.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "shots": [
                            {
                                "id": "generated",
                                "video": "one.mp4",
                                "voice": {
                                    "provider": "elevenlabs",
                                    "text": "Generated line.",
                                    "voice_id": "voice-123",
                                },
                            },
                            {
                                "id": "recorded",
                                "video": "two.mp4",
                                "voice": {
                                    "provider": "existing",
                                    "path": "recorded.mp3",
                                },
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            work_dir = project / "rendered"
            commands = []

            def fake_run(command, **kwargs):
                commands.append(command)
                output = Path(command[command.index("--out") + 1])
                output.write_bytes(b"generated")
                return subprocess.CompletedProcess(command, 0)

            with mock.patch.dict(
                os.environ,
                {
                    "HEYGEN_API_KEY": "heygen-test-key",
                    "ELEVENLABS_API_KEY": "eleven-test-key",
                },
                clear=False,
            ):
                with mock.patch.object(module, "subprocess", create=True) as child_process:
                    child_process.run.side_effect = fake_run
                    with mock.patch.object(
                        sys,
                        "argv",
                        [
                            "cartoon_voiceover.py",
                            "--manifest",
                            str(manifest),
                            "--work-dir",
                            str(work_dir),
                            "--confirm-upload",
                        ],
                    ):
                        with mock.patch.object(sys, "stdout", io.StringIO()):
                            try:
                                result = module.main()
                            except SystemExit as exc:
                                self.fail(f"live workflow exited early: {exc}")

            self.assertEqual(result, 0)
            self.assertTrue(work_dir.is_dir())
            self.assertEqual(
                [Path(command[1]).name for command in commands],
                ["character_voice.py", "heygen_lipsync.py", "heygen_lipsync.py"],
            )
            self.assertTrue(
                all(
                    "--confirm-upload" in command
                    for command in commands
                    if Path(command[1]).name == "heygen_lipsync.py"
                )
            )
            first_audio = commands[0][commands[0].index("--out") + 1]
            self.assertEqual(
                commands[1][commands[1].index("--audio") + 1], first_audio
            )
            self.assertEqual(
                commands[2][commands[2].index("--audio") + 1],
                str((project / "recorded.mp3").resolve()),
            )

    def test_live_run_concats_completed_shots_in_manifest_order(self):
        module = load_script()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "one.mp4").write_bytes(b"video-one")
            (project / "two.mp4").write_bytes(b"video-two")
            (project / "one.wav").write_bytes(b"audio-one")
            (project / "two.wav").write_bytes(b"audio-two")
            manifest = project / "cartoon.json"
            manifest.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "shots": [
                            {
                                "id": "first",
                                "video": "one.mp4",
                                "voice": {"provider": "existing", "path": "one.wav"},
                            },
                            {
                                "id": "second",
                                "video": "two.mp4",
                                "voice": {"provider": "existing", "path": "two.wav"},
                            },
                        ],
                        "concat": {"output": "episode.mp4"},
                    }
                ),
                encoding="utf-8",
            )
            work_dir = project / "rendered"
            commands = []

            def fake_run(command, **kwargs):
                commands.append(command)
                if "--out" in command:
                    Path(command[command.index("--out") + 1]).write_bytes(b"shot")
                else:
                    Path(command[-1]).write_bytes(b"episode")
                return subprocess.CompletedProcess(command, 0)

            with mock.patch.dict(
                os.environ, {"HEYGEN_API_KEY": "heygen-test-key"}, clear=False
            ):
                with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
                    with mock.patch.object(
                        sys,
                        "argv",
                        [
                            "cartoon_voiceover.py",
                            "--manifest",
                            str(manifest),
                            "--work-dir",
                            str(work_dir),
                            "--confirm-upload",
                        ],
                    ):
                        stdout = io.StringIO()
                        with mock.patch.object(sys, "stdout", stdout):
                            result = module.main()

            self.assertEqual(result, 0)
            self.assertEqual(len(commands), 3)
            self.assertEqual(Path(commands[-1][0]).name, "ffmpeg")
            self.assertEqual(
                (work_dir / "concat.txt").read_text(encoding="utf-8"),
                "file '001-first.synced.mp4'\nfile '002-second.synced.mp4'\n",
            )
            self.assertEqual(stdout.getvalue().strip(), str(work_dir / "episode.mp4"))
            self.assertEqual((work_dir / "episode.mp4").read_bytes(), b"episode")

    def test_rejects_invalid_and_unsafe_manifests_before_planning(self):
        cases = [
            (
                lambda manifest: manifest.update({"version": 2}),
                "manifest version must be 1",
            ),
            (
                lambda manifest: manifest.update({"shots": []}),
                "shots must be a non-empty array",
            ),
            (
                lambda manifest: manifest.update({"unexpected": True}),
                "unknown manifest field: unexpected",
            ),
            (
                lambda manifest: manifest["shots"][0].update({"id": "../escape"}),
                "shot 1 id must use only letters, numbers, '_' or '-'",
            ),
            (
                lambda manifest: manifest["shots"].append(
                    json.loads(json.dumps(manifest["shots"][0]))
                ),
                "duplicate shot id: shot-1",
            ),
            (
                lambda manifest: manifest["shots"][0].update({"mode": "ultra"}),
                "shot 'shot-1' mode must be speed or precision",
            ),
            (
                lambda manifest: manifest["shots"][0].update({"typo": "value"}),
                "shot 'shot-1' has unknown field: typo",
            ),
            (
                lambda manifest: manifest["shots"][0].update(
                    {"voice": {"provider": "mystery", "path": "line.wav"}}
                ),
                "shot 'shot-1' voice provider must be elevenlabs, local, or existing",
            ),
            (
                lambda manifest: manifest["shots"][0].update(
                    {"voice": {"provider": "elevenlabs", "text": "Missing ID"}}
                ),
                "shot 'shot-1' elevenlabs voice requires voice_id",
            ),
            (
                lambda manifest: manifest["shots"][0].update(
                    {
                        "voice": {
                            "provider": "local",
                            "text": "Bad rate",
                            "voice": "Samantha",
                            "rate": 0,
                        }
                    }
                ),
                "shot 'shot-1' local rate must be between 80 and 500",
            ),
            (
                lambda manifest: manifest["shots"][0]["voice"].update(
                    {"path": "../outside.wav"}
                ),
                "shot 'shot-1' audio path must stay inside the manifest directory",
            ),
            (
                lambda manifest: manifest.update(
                    {"concat": {"output": "../episode.mp4"}}
                ),
                "concat output must be a safe MP4 filename",
            ),
            (
                lambda manifest: manifest["shots"][0].update(
                    {"video": "https://127.1/shot.mp4"}
                ),
                "shot 'shot-1' video URL must use a public host",
            ),
        ]

        for mutate, expected_error in cases:
            with self.subTest(expected_error=expected_error):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    project = root / "project"
                    project.mkdir()
                    (project / "shot.mp4").write_bytes(b"video")
                    (project / "line.wav").write_bytes(b"audio")
                    (root / "outside.wav").write_bytes(b"outside")
                    manifest_data = {
                        "version": 1,
                        "shots": [
                            {
                                "id": "shot-1",
                                "video": "shot.mp4",
                                "voice": {
                                    "provider": "existing",
                                    "path": "line.wav",
                                },
                            }
                        ],
                    }
                    mutate(manifest_data)
                    manifest = project / "cartoon.json"
                    manifest.write_text(json.dumps(manifest_data), encoding="utf-8")
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(SCRIPT),
                            "--manifest",
                            str(manifest),
                            "--work-dir",
                            str(project / "rendered"),
                            "--dry-run",
                        ],
                        cwd=ROOT,
                        env={"PATH": os.environ.get("PATH", "")},
                        text=True,
                        capture_output=True,
                    )

                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(expected_error, result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertEqual(result.stdout, "")

    def test_reports_malformed_json_without_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            manifest = project / "cartoon.json"
            manifest.write_text('{"version": 1, "shots": [', encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--manifest",
                    str(manifest),
                    "--work-dir",
                    str(project / "rendered"),
                    "--dry-run",
                ],
                cwd=ROOT,
                env={"PATH": os.environ.get("PATH", "")},
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("cannot parse manifest JSON", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_live_preflight_fails_before_starting_any_child(self):
        module = load_script()
        cases = [
            (
                {"provider": "existing", "path": "line.wav"},
                {},
                {"say": "/usr/bin/say", "ffmpeg": "/usr/bin/ffmpeg"},
                "HEYGEN_API_KEY is not set",
                False,
            ),
            (
                {
                    "provider": "elevenlabs",
                    "text": "Cloud line.",
                    "voice_id": "voice-123",
                },
                {"HEYGEN_API_KEY": "heygen-test-key"},
                {"say": "/usr/bin/say", "ffmpeg": "/usr/bin/ffmpeg"},
                "ELEVENLABS_API_KEY is not set",
                False,
            ),
            (
                {"provider": "local", "text": "Local line.", "voice": "Samantha"},
                {"HEYGEN_API_KEY": "heygen-test-key"},
                {"say": None, "ffmpeg": "/usr/bin/ffmpeg"},
                "local provider requires macOS 'say'",
                False,
            ),
            (
                {"provider": "existing", "path": "line.wav"},
                {"HEYGEN_API_KEY": "heygen-test-key"},
                {"say": "/usr/bin/say", "ffmpeg": None},
                "concat requires ffmpeg",
                True,
            ),
        ]

        for voice, environment, tools, expected_error, concat in cases:
            with self.subTest(expected_error=expected_error):
                with tempfile.TemporaryDirectory() as tmp:
                    project = Path(tmp)
                    (project / "shot.mp4").write_bytes(b"video")
                    (project / "line.wav").write_bytes(b"audio")
                    manifest_data = {
                        "version": 1,
                        "shots": [
                            {"id": "shot-1", "video": "shot.mp4", "voice": voice}
                        ],
                    }
                    if concat:
                        manifest_data["concat"] = {"output": "episode.mp4"}
                    manifest = project / "cartoon.json"
                    manifest.write_text(json.dumps(manifest_data), encoding="utf-8")
                    work_dir = project / "rendered"

                    with mock.patch.dict(os.environ, environment, clear=True):
                        with mock.patch.object(
                            module.shutil,
                            "which",
                            side_effect=lambda name: tools.get(name),
                        ):
                            with mock.patch.object(module.subprocess, "run") as run:
                                with mock.patch.object(
                                    sys,
                                    "argv",
                                    [
                                        "cartoon_voiceover.py",
                                        "--manifest",
                                        str(manifest),
                                        "--work-dir",
                                        str(work_dir),
                                        "--confirm-upload",
                                    ],
                                ):
                                    stderr = io.StringIO()
                                    with mock.patch.object(sys, "stderr", stderr):
                                        result = module.main()

                    self.assertEqual(result, 2)
                    self.assertIn(expected_error, stderr.getvalue())
                    run.assert_not_called()
                    self.assertFalse(work_dir.exists())

    def test_live_run_refuses_to_overwrite_a_planned_artifact(self):
        module = load_script()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "shot.mp4").write_bytes(b"video")
            (project / "line.wav").write_bytes(b"audio")
            manifest = project / "cartoon.json"
            manifest.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "shots": [
                            {
                                "id": "shot-1",
                                "video": "shot.mp4",
                                "voice": {
                                    "provider": "existing",
                                    "path": "line.wav",
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            work_dir = project / "rendered"
            work_dir.mkdir()
            existing_output = work_dir / "001-shot-1.synced.mp4"
            existing_output.write_bytes(b"keep-me")

            with mock.patch.dict(
                os.environ, {"HEYGEN_API_KEY": "heygen-test-key"}, clear=False
            ):
                with mock.patch.object(module.subprocess, "run") as run:
                    with mock.patch.object(
                        sys,
                        "argv",
                        [
                            "cartoon_voiceover.py",
                            "--manifest",
                            str(manifest),
                            "--work-dir",
                            str(work_dir),
                            "--confirm-upload",
                        ],
                    ):
                        stderr = io.StringIO()
                        with mock.patch.object(sys, "stderr", stderr):
                            result = module.main()

            self.assertEqual(result, 2)
            self.assertIn("refusing to overwrite existing artifact", stderr.getvalue())
            self.assertEqual(existing_output.read_bytes(), b"keep-me")
            run.assert_not_called()

    def test_failed_child_is_reported_and_its_partial_output_is_removed(self):
        module = load_script()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "shot.mp4").write_bytes(b"video")
            (project / "line.wav").write_bytes(b"audio")
            manifest = project / "cartoon.json"
            manifest.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "shots": [
                            {
                                "id": "shot-1",
                                "video": "shot.mp4",
                                "voice": {
                                    "provider": "existing",
                                    "path": "line.wav",
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            work_dir = project / "rendered"
            partial = work_dir / "001-shot-1.synced.mp4"

            def fail_after_partial_write(command, **kwargs):
                Path(command[command.index("--out") + 1]).write_bytes(b"partial")
                return subprocess.CompletedProcess(command, 7)

            with mock.patch.dict(
                os.environ, {"HEYGEN_API_KEY": "heygen-test-key"}, clear=False
            ):
                with mock.patch.object(
                    module.subprocess, "run", side_effect=fail_after_partial_write
                ):
                    with mock.patch.object(
                        sys,
                        "argv",
                        [
                            "cartoon_voiceover.py",
                            "--manifest",
                            str(manifest),
                            "--work-dir",
                            str(work_dir),
                            "--confirm-upload",
                        ],
                    ):
                        stderr = io.StringIO()
                        with mock.patch.object(sys, "stderr", stderr):
                            result = module.main()

            self.assertEqual(result, 2)
            self.assertIn(
                "shot 'shot-1' lipsync failed with exit code 7", stderr.getvalue()
            )
            self.assertFalse(partial.exists())


if __name__ == "__main__":
    unittest.main()
