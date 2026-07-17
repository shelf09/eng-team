import base64
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/cartoon-pipeline/2_veo_scenes.py"


def load_script(env):
    with mock.patch.dict(os.environ, env, clear=False):
        spec = importlib.util.spec_from_file_location("veo_scenes", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class VeoLastFrameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        (self.base / "keyframes").mkdir()
        (self.base / "keyframes" / "s.png").write_bytes(b"start-image")
        self.env = {"CARTOON_DIR": self.tmp.name, "GEMINI_API_KEY": "test-key"}

    def tearDown(self):
        self.tmp.cleanup()

    def capture_submit(self, module, name):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["req"] = req
            return io.BytesIO(json.dumps({"name": "operations/op1"}).encode())

        with mock.patch.object(module.urllib.request, "urlopen", fake_urlopen):
            op = module.submit(name, "a prompt")
        self.assertEqual(op, "operations/op1")
        return json.loads(captured["req"].data)["instances"][0]

    def test_submit_includes_last_frame_when_end_keyframe_exists(self):
        (self.base / "keyframes" / "s_end.png").write_bytes(b"end-image")
        module = load_script(self.env)
        instance = self.capture_submit(module, "s")
        self.assertEqual(
            instance["image"]["bytesBase64Encoded"],
            base64.b64encode(b"start-image").decode(),
        )
        self.assertEqual(
            instance["lastFrame"]["bytesBase64Encoded"],
            base64.b64encode(b"end-image").decode(),
        )
        self.assertEqual(instance["lastFrame"]["mimeType"], "image/png")

    def test_submit_omits_last_frame_without_end_keyframe(self):
        module = load_script(self.env)
        instance = self.capture_submit(module, "s")
        self.assertNotIn("lastFrame", instance)
        self.assertEqual(
            instance["image"]["bytesBase64Encoded"],
            base64.b64encode(b"start-image").decode(),
        )


class VeoSceneFilterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        (self.base / "clips").mkdir()
        self.module = load_script(
            {"CARTOON_DIR": self.tmp.name, "GEMINI_API_KEY": "test-key"}
        )
        self.module.cfg = {
            "style_video": "sv",
            "voices": "v",
            "scenes": [{"name": "a", "action": "A"}, {"name": "b", "action": "B"}],
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_named_scene_restricts_submissions(self):
        submitted = []
        with mock.patch.object(
            self.module, "submit", side_effect=lambda n, p: submitted.append(n)
        ):
            with mock.patch.object(self.module.time, "sleep"):
                result = self.module.main(["a"])
        self.assertEqual(submitted, ["a"])
        self.assertFalse(result)  # nothing downloaded, so the run is incomplete

    def test_no_args_processes_all_scenes(self):
        submitted = []
        with mock.patch.object(
            self.module, "submit", side_effect=lambda n, p: submitted.append(n)
        ):
            with mock.patch.object(self.module.time, "sleep"):
                self.module.main(None)
        self.assertEqual(submitted, ["a", "b"])

    def test_unknown_scene_name_exits(self):
        with self.assertRaises(SystemExit):
            self.module.main(["zzz"])

    def test_unsafe_scene_name_in_config_exits(self):
        self.module.cfg = {
            "style_video": "sv",
            "voices": "v",
            "scenes": [{"name": "../evil", "action": "A"}],
        }
        with mock.patch.object(self.module, "submit") as submit:
            with self.assertRaises(SystemExit):
                self.module.main(None)
        submit.assert_not_called()

    def test_complete_scene_is_skipped_and_reported_done(self):
        (self.base / "clips" / "a.mp4").write_bytes(b"clip")
        with mock.patch.object(self.module, "submit") as submit:
            result = self.module.main(["a"])
        submit.assert_not_called()
        self.assertTrue(result)

    def test_failed_operation_is_cleared_so_a_rerun_resubmits(self):
        (self.base / "veo_ops.json").write_text(json.dumps({"a": "operations/dead"}))
        failed = {"done": True, "error": {"code": 8, "message": "quota"}}

        def fake_urlopen(req, timeout=None):
            return io.BytesIO(json.dumps(failed).encode())

        with mock.patch.object(self.module.urllib.request, "urlopen", fake_urlopen):
            with mock.patch.object(self.module.time, "sleep"):
                result = self.module.main(["a"])
        self.assertFalse(result)
        ops = json.loads((self.base / "veo_ops.json").read_text())
        self.assertIsNone(ops["a"])  # rerun must resubmit, not re-poll a dead op

    def test_expired_operation_404_is_cleared_so_a_rerun_resubmits(self):
        (self.base / "veo_ops.json").write_text(json.dumps({"a": "operations/gone"}))

        def gone(req, timeout=None):
            raise self.module.urllib.error.HTTPError(
                "https://poll", 404, "Not Found", None, io.BytesIO(b"")
            )

        with mock.patch.object(self.module.urllib.request, "urlopen", gone):
            with mock.patch.object(self.module.time, "sleep"):
                result = self.module.main(["a"])
        self.assertFalse(result)
        ops = json.loads((self.base / "veo_ops.json").read_text())
        self.assertIsNone(ops["a"])  # expired op must not be re-polled forever


if __name__ == "__main__":
    unittest.main()
