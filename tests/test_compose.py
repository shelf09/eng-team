import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/cartoon-pipeline/3_compose.sh"
SCENES = json.loads((ROOT / "tools/cartoon-pipeline/scenes.json").read_text())


class ComposePreferenceTests(unittest.TestCase):
    def test_compose_prefers_heygen_then_dub_then_raw(self):
        first, second, third = [s["name"] for s in SCENES["scenes"][:3]]
        with tempfile.TemporaryDirectory() as tmp:
            clips = Path(tmp) / "clips"
            clips.mkdir()
            for name in (f"{first}_heygen", f"{first}_dub", first,
                         f"{second}_dub", second,
                         third):
                (clips / f"{name}.mp4").write_bytes(b"clip")
            env = dict(os.environ, CARTOON_DIR=tmp, COMPOSE_LIST_ONLY="1")
            proc = subprocess.run(
                ["bash", str(SCRIPT), "out.mp4"],
                env=env, capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            chosen = dict(
                line.split(" -> ")
                for line in proc.stdout.splitlines()
                if " -> " in line
            )
            self.assertEqual(chosen[first], f"clips/{first}_heygen.mp4")
            self.assertEqual(chosen[second], f"clips/{second}_dub.mp4")
            self.assertEqual(chosen[third], f"clips/{third}.mp4")
            self.assertFalse((Path(tmp) / "out.mp4").exists())

    def test_list_mode_does_no_cover_work(self):
        first = SCENES["scenes"][0]["name"]
        with tempfile.TemporaryDirectory() as tmp:
            clips = Path(tmp) / "clips"
            clips.mkdir()
            (clips / f"{first}.mp4").write_bytes(b"clip")
            (Path(tmp) / "cover.png").write_bytes(b"not-a-real-png")
            env = dict(os.environ, CARTOON_DIR=tmp, COMPOSE_LIST_ONLY="1")
            proc = subprocess.run(
                ["bash", str(SCRIPT), "out.mp4"],
                env=env, capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn(f"{first} -> clips/{first}.mp4", proc.stdout)
            self.assertFalse((Path(tmp) / "seg" / "00_cover.mp4").exists())
            self.assertFalse((Path(tmp) / "seg" / "cover.png").exists())


if __name__ == "__main__":
    unittest.main()
