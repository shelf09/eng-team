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
SCRIPT = ROOT / "tools/cartoon-pipeline/1_nano_scenes.py"

IMAGE_RESPONSE = {
    "candidates": [
        {
            "content": {
                "parts": [
                    {"inlineData": {"data": base64.b64encode(b"generated").decode()}}
                ]
            }
        }
    ]
}


def forbid_network(req, timeout=None):
    raise AssertionError("network request during module import")


def load_script(env):
    with mock.patch.dict(os.environ, env, clear=False):
        with mock.patch("urllib.request.urlopen", forbid_network):
            spec = importlib.util.spec_from_file_location("nano_scenes", SCRIPT)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
    return module


class NanoScenesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        (self.base / "refs").mkdir()
        (self.base / "refs" / "cast.png").write_bytes(b"ref-image")
        self.module = load_script(
            {"CARTOON_DIR": self.tmp.name, "GEMINI_API_KEY": "test-key"}
        )
        self.requests = []

        def fake_urlopen(req, timeout=None):
            self.requests.append(json.loads(req.data))
            return io.BytesIO(json.dumps(IMAGE_RESPONSE).encode())

        self.fake_urlopen = fake_urlopen

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, cfg, names=None):
        self.module.cfg = cfg
        with mock.patch.object(self.module.urllib.request, "urlopen", self.fake_urlopen):
            return self.module.main(names)

    def prompts(self):
        return [r["contents"][0]["parts"][0]["text"] for r in self.requests]

    def test_scene_with_end_keyframe_generates_both_images(self):
        result = self.run_main(
            {
                "style_image": "SI",
                "scenes": [{"name": "a", "keyframe": "KA", "end_keyframe": "EA"}],
            }
        )
        self.assertTrue(result)
        self.assertTrue((self.base / "keyframes" / "a.png").exists())
        self.assertTrue((self.base / "keyframes" / "a_end.png").exists())
        self.assertEqual(self.prompts(), ["SI KA", "SI EA"])

    def images_of(self, request):
        return [
            part["inlineData"]["data"]
            for part in request["contents"][0]["parts"]
            if "inlineData" in part
        ]

    def test_next_scene_start_seeded_with_previous_end_keyframe(self):
        self.run_main(
            {
                "style_image": "SI",
                "scenes": [
                    {"name": "a", "keyframe": "KA", "end_keyframe": "EA"},
                    {"name": "b", "keyframe": "KB"},
                ],
            }
        )
        ref = base64.b64encode(b"ref-image").decode()
        generated = base64.b64encode(b"generated").decode()
        # scene 1 start: standing refs only
        self.assertEqual(self.images_of(self.requests[0]), [ref])
        # scene 2 start: standing refs + scene 1's end keyframe
        self.assertEqual(self.images_of(self.requests[2]), [ref, generated])

    def test_end_keyframe_seeded_with_own_start_keyframe(self):
        self.run_main(
            {
                "style_image": "SI",
                "scenes": [{"name": "a", "keyframe": "KA", "end_keyframe": "EA"}],
            }
        )
        ref = base64.b64encode(b"ref-image").decode()
        generated = base64.b64encode(b"generated").decode()
        self.assertEqual(self.images_of(self.requests[1]), [ref, generated])

    def test_rerun_skips_existing_start_and_end_keyframes(self):
        cfg = {
            "style_image": "SI",
            "scenes": [{"name": "a", "keyframe": "KA", "end_keyframe": "EA"}],
        }
        self.run_main(cfg)
        first_run_requests = len(self.requests)
        self.run_main(cfg)
        self.assertEqual(len(self.requests), first_run_requests)

    def test_named_scene_restricts_generation(self):
        self.run_main(
            {
                "style_image": "SI",
                "scenes": [
                    {"name": "a", "keyframe": "KA"},
                    {"name": "b", "keyframe": "KB"},
                ],
            },
            names=["b"],
        )
        self.assertEqual(self.prompts(), ["SI KB"])

    def test_unknown_scene_name_exits(self):
        self.module.cfg = {"style_image": "SI", "scenes": [{"name": "a", "keyframe": "K"}]}
        with self.assertRaises(SystemExit):
            self.module.main(["zzz"])

    def test_unsafe_scene_name_in_config_exits(self):
        self.module.cfg = {
            "style_image": "SI",
            "scenes": [{"name": "../evil", "keyframe": "K"}],
        }
        with self.assertRaises(SystemExit):
            self.module.main(None)
        self.assertEqual(self.requests, [])

    def test_failed_start_keyframe_blocks_the_end_keyframe(self):
        self.module.cfg = {
            "style_image": "SI",
            "scenes": [{"name": "a", "keyframe": "KA", "end_keyframe": "EA"}],
        }

        def no_image(req, timeout=None):
            self.requests.append(json.loads(req.data))
            return io.BytesIO(
                json.dumps({"candidates": [{"content": {"parts": []}}]}).encode()
            )

        with mock.patch.object(self.module.urllib.request, "urlopen", no_image):
            result = self.module.main(None)
        self.assertFalse(result)
        # the end keyframe must NOT be generated unseeded: a rerun would freeze
        # it (exists-on-disk skip) with no start frame ever attached
        self.assertEqual(len(self.requests), 1)
        self.assertFalse((self.base / "keyframes" / "a_end.png").exists())


if __name__ == "__main__":
    unittest.main()
