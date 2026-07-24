import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/cartoon-pipeline/3_compose.sh"
SCENES = json.loads((ROOT / "tools/cartoon-pipeline/scenes.json").read_text())


def video_duration(path):
    return float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nk=1:nw=1", str(path)],
        capture_output=True, text=True).stdout.strip())


class ComposeAssemblyTests(unittest.TestCase):
    """Full assembly runs against two synthesized 2s clips."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.script_dir = base / "pipeline"
        self.script_dir.mkdir()
        shutil.copy(SCRIPT, self.script_dir / "3_compose.sh")
        (self.script_dir / "scenes.json").write_text(json.dumps(
            {"episode": "t", "scenes": [{"name": "a"}, {"name": "b"}]}))
        self.cartoon = base / "run"
        (self.cartoon / "clips").mkdir(parents=True)
        for name in ("a", "b"):
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y",
                 "-f", "lavfi", "-i", "testsrc=s=270x480:r=30:d=2",
                 "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                 "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", str(self.cartoon / "clips" / f"{name}.mp4")],
                check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def compose(self, extra_env=None):
        out = Path(self.tmp.name) / "out.mp4"
        env = dict(os.environ, CARTOON_DIR=str(self.cartoon), **(extra_env or {}))
        proc = subprocess.run(
            ["bash", str(self.script_dir / "3_compose.sh"), str(out)],
            env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return out

    def test_scenes_crossfade_into_each_other(self):
        # two 2s scenes with a 0.3s dissolve overlap ≈ 3.7s, not 4.0s
        duration = video_duration(self.compose())
        self.assertLess(duration, 3.9)
        self.assertGreater(duration, 3.4)

    def test_scenes_trim_to_dialogue_when_placement_exists(self):
        # last line ends at 1.0s -> each scene trims to ~1.45s
        (self.cartoon / "placement.json").write_text(json.dumps(
            {"a": [{"end": 1.0}], "b": [{"end": 1.0}]}))
        duration = video_duration(self.compose())
        self.assertLess(duration, 2.9)

    def test_plain_concat_preserved_when_xfade_disabled(self):
        duration = video_duration(self.compose({"COMPOSE_XFADE": "0"}))
        self.assertGreater(duration, 3.9)


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
