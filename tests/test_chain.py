import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/cartoon-pipeline/0_chain.py"

CFG = {
    "scenes": [
        {"name": "a", "keyframe": "KA"},
        {"name": "b", "keyframe": "KB"},
        {"name": "c", "keyframe": "KC"},
    ]
}


def load_script(env):
    with mock.patch.dict(os.environ, env, clear=False):
        spec = importlib.util.spec_from_file_location("chain", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


def result(code):
    completed = mock.Mock()
    completed.returncode = code
    return completed


class ChainOrderingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        (self.base / "clips").mkdir()
        self.env = {"CARTOON_DIR": self.tmp.name}
        self.module = load_script(self.env)
        self.module.cfg = CFG
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def stage_calls(self):
        """(stage-script basename, scene) for every recorded subprocess call."""
        return [(Path(argv[1]).name, argv[2]) for argv in self.calls]

    def run_chain(self, argv, rc=lambda call_argv: 0):
        def fake_run(call_argv, **kwargs):
            self.calls.append(call_argv)
            return result(rc(call_argv))

        with mock.patch.object(self.module.subprocess, "run", fake_run):
            self.module.main(argv)

    def test_scene_runs_to_completion_before_next_scene_starts(self):
        self.run_chain([])
        self.assertEqual(
            self.stage_calls(),
            [
                ("1_nano_scenes.py", "a"),
                ("2_veo_scenes.py", "a"),
                ("1_nano_scenes.py", "b"),
                ("2_veo_scenes.py", "b"),
                ("1_nano_scenes.py", "c"),
                ("2_veo_scenes.py", "c"),
            ],
        )

    def test_failure_stops_the_chain_before_later_scenes(self):
        def rc(call_argv):
            return 1 if ("2_veo_scenes.py" in call_argv[1] and call_argv[2] == "b") else 0

        with self.assertRaises(SystemExit) as ctx:
            self.run_chain([], rc=rc)
        self.assertIn("b", str(ctx.exception))
        self.assertIn("veo", str(ctx.exception))
        self.assertEqual(self.stage_calls()[-1], ("2_veo_scenes.py", "b"))
        self.assertNotIn(("1_nano_scenes.py", "c"), self.stage_calls())

    def test_unknown_scene_name_exits_without_running_anything(self):
        with self.assertRaises(SystemExit):
            self.run_chain(["zzz"])
        self.assertEqual(self.calls, [])

    def test_unsafe_scene_name_in_config_exits_without_running_anything(self):
        self.module.cfg = {"scenes": [{"name": "../evil", "keyframe": "K"}]}
        with self.assertRaises(SystemExit):
            self.run_chain([])
        self.assertEqual(self.calls, [])


class ChainHeygenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        (self.base / "clips").mkdir()
        self.module = load_script({"CARTOON_DIR": self.tmp.name})
        self.module.cfg = {"scenes": [{"name": "a", "keyframe": "KA"}]}
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def run_chain(self, argv, key="test-key", produce_output=True):
        def fake_run(call_argv, **kwargs):
            self.calls.append(call_argv)
            if produce_output and "--out" in call_argv:
                Path(call_argv[call_argv.index("--out") + 1]).write_bytes(b"lipsynced")
            return result(0)

        env = {"HEYGEN_API_KEY": key} if key else {}
        with mock.patch.dict(os.environ, env, clear=False):
            if not key:
                os.environ.pop("HEYGEN_API_KEY", None)
            with mock.patch.object(self.module.subprocess, "run", fake_run):
                self.module.main(argv)

    def heygen_call(self):
        matches = [c for c in self.calls if self.module.HEYGEN_SCRIPT in c]
        self.assertEqual(len(matches), 1)
        return matches[0]

    def test_heygen_step_uses_dub_audio_when_present(self):
        (self.base / "clips" / "a_dub.mp4").write_bytes(b"dub")
        self.run_chain(["--heygen"])
        ffmpeg = next(c for c in self.calls if c[0] == "ffmpeg")
        self.assertEqual(
            ffmpeg[ffmpeg.index("-i") + 1], f"{self.module.BASE}/clips/a_dub.mp4"
        )
        call = self.heygen_call()
        self.assertEqual(call[call.index("--video") + 1], f"{self.module.BASE}/clips/a.mp4")
        self.assertEqual(call[call.index("--audio") + 1], f"{self.module.BASE}/heygen/a.wav")
        self.assertEqual(call[call.index("--out") + 1], f"{self.module.BASE}/clips/a_heygen.mp4")
        self.assertIn("--confirm-upload", call)

    def test_heygen_step_falls_back_to_clip_audio(self):
        self.run_chain(["--heygen"])
        ffmpeg = next(c for c in self.calls if c[0] == "ffmpeg")
        self.assertEqual(
            ffmpeg[ffmpeg.index("-i") + 1], f"{self.module.BASE}/clips/a.mp4"
        )

    def test_existing_heygen_output_is_skipped(self):
        (self.base / "clips" / "a_heygen.mp4").write_bytes(b"done")
        self.run_chain(["--heygen"])
        self.assertEqual([c for c in self.calls if c[0] == "ffmpeg"], [])
        self.assertEqual([c for c in self.calls if self.module.HEYGEN_SCRIPT in c], [])

    def test_missing_heygen_output_stops_the_chain(self):
        with self.assertRaises(SystemExit) as ctx:
            self.run_chain(["--heygen"], produce_output=False)
        self.assertIn("heygen", str(ctx.exception))

    def test_without_flag_no_heygen_calls_are_made(self):
        self.run_chain([])
        self.assertEqual(len(self.calls), 2)  # nano + veo only

    def test_flag_without_key_skips_heygen_and_completes(self):
        self.run_chain(["--heygen"], key=None)
        self.assertEqual(len(self.calls), 2)  # nano + veo only


if __name__ == "__main__":
    unittest.main()
