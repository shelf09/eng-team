import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/cartoon-pipeline/7_episode.py"

SEED = {
    "style_image": "SI",
    "style_video": "SV",
    "voices": "VOICES",
    "scenes": [{"name": "old", "keyframe": "K", "action": "A", "lines": [["boss", "x"]]}],
    "tts": {"model": "m", "voices": {"boss": "B", "eng": "E"}, "styles": {}},
}

GOOD_SCENES = [
    {
        "name": f"s{i}_thing{i}",
        "keyframe": f"KF{i}",
        "end_keyframe": f"EK{i} BOTH MOUTHS FULLY CLOSED",
        "action": f'The boss says: "Line {i}." The engineer replies flatly: "Reply {i}."',
        "lines": [["boss", f"Line {i}."], ["eng", f"Reply {i}."]],
    }
    for i in range(1, 5)
]

GOOD_EPISODE = {
    "slug": "rto_no_desks",
    "loop_hook": "Scene 5's final line announces a new mandate, which is exactly "
                 "what scene 1 opens reacting to — the loop reads as continuous.",
    "scenes": GOOD_SCENES,
}


def gemini_response(payload):
    text = "```json\n" + json.dumps(payload) + "\n```"
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def load_script(env):
    with mock.patch.dict(os.environ, env, clear=False):
        spec = importlib.util.spec_from_file_location("episode", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class EpisodeGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        (self.base / "scenes.json").write_text(json.dumps(SEED))
        self.module = load_script({"GEMINI_API_KEY": "test-key"})
        self.module.HERE = str(self.base)

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, responses, argv=None):
        replies = [io.BytesIO(json.dumps(r).encode()) for r in responses]

        def fake_urlopen(req, timeout=None):
            self.requests.append(json.loads(req.data))
            return replies.pop(0)

        self.requests = []
        with mock.patch.object(self.module.urllib.request, "urlopen", fake_urlopen):
            return self.module.main(argv or [])

    def test_writes_episode_file_and_activates_it(self):
        self.run_main([gemini_response(GOOD_EPISODE)], ["return to office"])
        episode = json.loads((self.base / "episodes" / "rto_no_desks.json").read_text())
        active = json.loads((self.base / "scenes.json").read_text())
        self.assertEqual(episode, active)
        # the slug is stamped so the chain can name the run folder
        self.assertEqual(active["episode"], "rto_no_desks")
        # locked identity comes from the seed file, not the model
        self.assertEqual(active["style_image"], "SI")
        self.assertEqual(active["style_video"], "SV")
        self.assertEqual(active["voices"], "VOICES")
        self.assertEqual(active["tts"], SEED["tts"])
        # scenes come from the model
        self.assertEqual(len(active["scenes"]), 4)
        self.assertEqual(active["scenes"][0]["name"], "s1_thing1")
        # the topic reached the prompt
        self.assertIn("return to office", self.requests[0]["contents"][0]["parts"][0]["text"])

    def test_invalid_scene_names_trigger_one_reroll_then_succeed(self):
        bad = {"slug": "ok_slug", "scenes": [dict(s, name="../evil") for s in GOOD_SCENES]}
        self.run_main([gemini_response(bad), gemini_response(GOOD_EPISODE)], ["t"])
        self.assertEqual(len(self.requests), 2)
        self.assertTrue((self.base / "episodes" / "rto_no_desks.json").exists())

    def test_two_invalid_responses_exit_without_touching_scenes_json(self):
        bad = {"slug": "x", "scenes": []}  # wrong scene count
        with self.assertRaises(SystemExit):
            self.run_main([gemini_response(bad), gemini_response(bad)], ["t"])
        self.assertEqual(json.loads((self.base / "scenes.json").read_text()), SEED)

    def test_missing_end_keyframe_is_rejected(self):
        bad_scenes = [dict(s) for s in GOOD_SCENES]
        del bad_scenes[2]["end_keyframe"]
        bad = {"slug": "x", "scenes": bad_scenes}
        with self.assertRaises(SystemExit):
            self.run_main([gemini_response(bad), gemini_response(bad)], ["t"])

    def test_missing_loop_hook_is_rejected(self):
        bad = {k: v for k, v in GOOD_EPISODE.items() if k != "loop_hook"}
        with self.assertRaises(SystemExit):
            self.run_main([gemini_response(bad), gemini_response(bad)], ["t"])

    def test_line_not_present_in_action_is_rejected(self):
        bad_scenes = [dict(s) for s in GOOD_SCENES]
        bad_scenes[0] = dict(bad_scenes[0], action="Totally different words.")
        bad = {"slug": "x", "scenes": bad_scenes}
        with self.assertRaises(SystemExit):
            self.run_main([gemini_response(bad), gemini_response(bad)], ["t"])


if __name__ == "__main__":
    unittest.main()
