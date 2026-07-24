#!/usr/bin/env python3
"""Orchestrate ordered one-speaker cartoon shots from a JSON manifest."""

import argparse
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit


SCRIPT_DIR = Path(__file__).resolve().parent
CHARACTER_VOICE = SCRIPT_DIR / "character_voice.py"
HEYGEN_LIPSYNC = SCRIPT_DIR / "heygen_lipsync.py"
SHOT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
SAFE_MP4_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.mp4$")
VIDEO_SUFFIXES = {".mp4", ".webm"}
AUDIO_SUFFIXES = {".mp3", ".wav"}


class ManifestError(ValueError):
    pass


class WorkflowError(RuntimeError):
    pass


def local_input(spec: str, manifest_dir: Path) -> str:
    if spec.startswith("https://"):
        return spec
    path = Path(spec)
    return str((path if path.is_absolute() else manifest_dir / path).resolve())


def reject_unknown(value: dict, allowed: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ManifestError(f"{label} has unknown field: {unknown[0]}")


def require_text(value: dict, field: str, message: str) -> str:
    item = value.get(field)
    if not isinstance(item, str) or not item.strip():
        raise ManifestError(message)
    return item


def validated_input(
    spec: object,
    manifest_dir: Path,
    suffixes: set[str],
    shot_id: str,
    kind: str,
) -> str:
    if not isinstance(spec, str) or not spec:
        raise ManifestError(f"shot {shot_id!r} {kind} must be a file path or HTTPS URL")
    parsed = urlsplit(spec)
    if parsed.scheme:
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            raise ManifestError(f"shot {shot_id!r} {kind} URL must use public HTTPS")
        if parsed.username is not None or parsed.password is not None:
            raise ManifestError(f"shot {shot_id!r} {kind} URL must not include credentials")
        hostname = parsed.hostname.rstrip(".").lower()
        if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
            raise ManifestError(f"shot {shot_id!r} {kind} URL must use a public host")
        try:
            address = ipaddress.ip_address(hostname.strip("[]"))
        except ValueError:
            try:
                address = ipaddress.ip_address(
                    socket.inet_ntoa(socket.inet_aton(hostname))
                )
            except OSError:
                address = None
        if address is not None and not address.is_global:
            raise ManifestError(f"shot {shot_id!r} {kind} URL must use a public host")
        suffix = Path(parsed.path).suffix.lower()
        if suffix and suffix not in suffixes:
            formats = "MP4 or WebM" if kind == "video" else "MP3 or WAV"
            raise ManifestError(f"shot {shot_id!r} {kind} must be {formats}")
        return spec

    root = manifest_dir.resolve()
    path = Path(spec)
    candidate = (path if path.is_absolute() else root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ManifestError(
            f"shot {shot_id!r} {kind} path must stay inside the manifest directory"
        ) from exc
    if not candidate.is_file():
        raise ManifestError(f"shot {shot_id!r} {kind} file does not exist: {spec}")
    if candidate.suffix.lower() not in suffixes:
        formats = "MP4 or WebM" if kind == "video" else "MP3 or WAV"
        raise ManifestError(f"shot {shot_id!r} {kind} must be {formats}")
    return str(candidate)


def validate_voice(voice: object, manifest_dir: Path, shot_id: str) -> dict:
    if not isinstance(voice, dict):
        raise ManifestError(f"shot {shot_id!r} voice must be an object")
    provider = voice.get("provider")
    if provider not in {"elevenlabs", "local", "existing"}:
        raise ManifestError(
            f"shot {shot_id!r} voice provider must be elevenlabs, local, or existing"
        )

    normalized = dict(voice)
    if provider == "existing":
        reject_unknown(voice, {"provider", "path"}, f"shot {shot_id!r} voice")
        normalized["path"] = validated_input(
            voice.get("path"), manifest_dir, AUDIO_SUFFIXES, shot_id, "audio"
        )
        return normalized

    require_text(
        voice,
        "text",
        f"shot {shot_id!r} {provider} voice requires non-empty text",
    )
    if provider == "elevenlabs":
        reject_unknown(
            voice,
            {"provider", "text", "voice_id", "model"},
            f"shot {shot_id!r} voice",
        )
        require_text(
            voice,
            "voice_id",
            f"shot {shot_id!r} elevenlabs voice requires voice_id",
        )
        if "model" in voice:
            require_text(
                voice,
                "model",
                f"shot {shot_id!r} elevenlabs model must be non-empty",
            )
        return normalized

    reject_unknown(
        voice,
        {"provider", "text", "voice", "rate"},
        f"shot {shot_id!r} voice",
    )
    require_text(
        voice,
        "voice",
        f"shot {shot_id!r} local voice requires voice",
    )
    if "rate" in voice:
        rate = voice["rate"]
        if isinstance(rate, bool) or not isinstance(rate, int) or not 80 <= rate <= 500:
            raise ManifestError(
                f"shot {shot_id!r} local rate must be between 80 and 500"
            )
    return normalized


def validate_manifest(value: object, manifest_dir: Path) -> dict:
    if not isinstance(value, dict):
        raise ManifestError("manifest root must be an object")
    unknown = sorted(set(value) - {"version", "shots", "concat"})
    if unknown:
        raise ManifestError(f"unknown manifest field: {unknown[0]}")
    if value.get("version") != 1 or isinstance(value.get("version"), bool):
        raise ManifestError("manifest version must be 1")
    shots = value.get("shots")
    if not isinstance(shots, list) or not shots:
        raise ManifestError("shots must be a non-empty array")

    normalized_shots = []
    seen_ids = set()
    for number, shot in enumerate(shots, start=1):
        if not isinstance(shot, dict):
            raise ManifestError(f"shot {number} must be an object")
        shot_id = shot.get("id")
        if not isinstance(shot_id, str) or not SHOT_ID.fullmatch(shot_id):
            raise ManifestError(
                f"shot {number} id must use only letters, numbers, '_' or '-'"
            )
        if shot_id in seen_ids:
            raise ManifestError(f"duplicate shot id: {shot_id}")
        seen_ids.add(shot_id)
        reject_unknown(
            shot,
            {"id", "video", "voice", "mode", "title", "dynamic_duration"},
            f"shot {shot_id!r}",
        )
        mode = shot.get("mode", "precision")
        if mode not in {"speed", "precision"}:
            raise ManifestError(f"shot {shot_id!r} mode must be speed or precision")
        normalized = dict(shot)
        normalized["video"] = validated_input(
            shot.get("video"), manifest_dir, VIDEO_SUFFIXES, shot_id, "video"
        )
        normalized["voice"] = validate_voice(shot.get("voice"), manifest_dir, shot_id)
        if "title" in shot and (
            not isinstance(shot["title"], str) or not shot["title"].strip()
        ):
            raise ManifestError(f"shot {shot_id!r} title must be non-empty")
        if "dynamic_duration" in shot and not isinstance(shot["dynamic_duration"], bool):
            raise ManifestError(f"shot {shot_id!r} dynamic_duration must be true or false")
        normalized_shots.append(normalized)

    normalized_manifest = {"version": 1, "shots": normalized_shots}
    if "concat" in value:
        concat = value["concat"]
        if not isinstance(concat, dict):
            raise ManifestError("concat must be an object")
        reject_unknown(concat, {"output"}, "concat")
        output = concat.get("output")
        if not isinstance(output, str) or not SAFE_MP4_NAME.fullmatch(output):
            raise ManifestError("concat output must be a safe MP4 filename")
        normalized_manifest["concat"] = {"output": output}
    return normalized_manifest


def load_manifest(path: Path) -> object:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"cannot read manifest: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ManifestError(
            f"cannot parse manifest JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc


def voice_command(voice: dict, output: Path, dry_run: bool) -> list[str]:
    provider = voice["provider"]
    command = [
        sys.executable,
        str(CHARACTER_VOICE),
        "--provider",
        provider,
        "--text",
        voice["text"],
        "--out",
        str(output),
    ]
    if provider == "elevenlabs":
        command.extend(["--voice-id", voice["voice_id"]])
        if "model" in voice:
            command.extend(["--model", voice["model"]])
    else:
        command.extend(["--local-voice", voice["voice"]])
        if "rate" in voice:
            command.extend(["--rate", str(voice["rate"])])
    if dry_run:
        command.append("--dry-run")
    return command


def build_plan(
    manifest: dict,
    manifest_dir: Path,
    work_dir: Path,
    dry_run: bool,
    confirm_upload: bool = False,
) -> dict:
    steps = []
    synced_outputs = []
    for number, shot in enumerate(manifest["shots"], start=1):
        shot_id = shot["id"]
        stem = f"{number:03d}-{shot_id}"
        audio = work_dir / f"{stem}.voice.wav"
        synced = work_dir / f"{stem}.synced.mp4"
        voice = shot["voice"]
        if voice["provider"] == "existing":
            audio_spec = local_input(voice["path"], manifest_dir)
        else:
            audio_spec = str(audio)
            steps.append(
                {
                    "shot": shot_id,
                    "stage": "voice",
                    "command": voice_command(voice, audio, dry_run),
                }
            )
        command = [
            sys.executable,
            str(HEYGEN_LIPSYNC),
            "--video",
            local_input(shot["video"], manifest_dir),
            "--audio",
            audio_spec,
            "--mode",
            shot.get("mode", "precision"),
            "--out",
            str(synced),
        ]
        if "title" in shot:
            command.extend(["--title", shot["title"]])
        if shot.get("dynamic_duration"):
            command.append("--dynamic-duration")
        if dry_run:
            command.append("--dry-run")
        elif confirm_upload:
            command.append("--confirm-upload")
        else:
            raise WorkflowError(
                "live workflow uploads every shot to HeyGen; pass --confirm-upload"
            )
        steps.append({"shot": shot_id, "stage": "lipsync", "command": command})
        synced_outputs.append(synced)

    final_output = None
    concat = manifest.get("concat")
    if concat:
        final_output = work_dir / concat["output"]
        concat_file = work_dir / "concat.txt"
        command = [
            shutil.which("ffmpeg") or "ffmpeg",
            "-v",
            "error",
            "-f",
            "concat",
            "-safe",
            "1",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            "-n",
            str(final_output),
        ]
        steps.append({"shot": None, "stage": "concat", "command": command})

    return {
        "dry_run": dry_run,
        "work_dir": str(work_dir),
        "steps": steps,
        "shot_outputs": [str(path) for path in synced_outputs],
        "final_output": str(final_output) if final_output else None,
    }


def preflight(manifest: dict) -> None:
    if not os.environ.get("HEYGEN_API_KEY"):
        raise WorkflowError("HEYGEN_API_KEY is not set")
    providers = {shot["voice"]["provider"] for shot in manifest["shots"]}
    if "elevenlabs" in providers and not os.environ.get("ELEVENLABS_API_KEY"):
        raise WorkflowError("ELEVENLABS_API_KEY is not set")
    if "local" in providers and not shutil.which("say"):
        raise WorkflowError(
            "local provider requires macOS 'say'; use an existing WAV/MP3 instead"
        )
    if manifest.get("concat") and not shutil.which("ffmpeg"):
        raise WorkflowError("concat requires ffmpeg")


def ensure_artifacts_available(plan: dict) -> None:
    artifacts = {Path(output) for output in plan["shot_outputs"]}
    for step in plan["steps"]:
        command = step["command"]
        if step["stage"] == "voice":
            artifacts.add(Path(command[command.index("--out") + 1]))
        elif step["stage"] == "concat":
            artifacts.add(Path(command[command.index("-i") + 1]))
    if plan["final_output"]:
        artifacts.add(Path(plan["final_output"]))
    for artifact in sorted(artifacts, key=str):
        if artifact.exists():
            raise WorkflowError(f"refusing to overwrite existing artifact: {artifact}")


def execute_plan(plan: dict) -> None:
    work_dir = Path(plan["work_dir"])
    work_dir.mkdir(parents=True, exist_ok=True)
    for step in plan["steps"]:
        if step["stage"] == "concat":
            concat_file = Path(step["command"][step["command"].index("-i") + 1])
            concat_file.write_text(
                "".join(
                    f"file '{Path(output).name}'\n" for output in plan["shot_outputs"]
                ),
                encoding="utf-8",
            )
        if step["stage"] == "concat":
            output = Path(step["command"][-1])
        else:
            output = Path(
                step["command"][step["command"].index("--out") + 1]
            )
        try:
            result = subprocess.run(step["command"])
        except OSError as exc:
            output.unlink(missing_ok=True)
            raise WorkflowError(
                f"could not start {step['stage']} for shot {step['shot']!r}: {exc}"
            ) from exc
        if result.returncode:
            output.unlink(missing_ok=True)
            raise WorkflowError(
                f"shot {step['shot']!r} {step['stage']} failed with exit code "
                f"{result.returncode}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--confirm-upload",
        action="store_true",
        help="Acknowledge that every live shot and voice track is sent to HeyGen",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    try:
        manifest = validate_manifest(load_manifest(manifest_path), manifest_path.parent)
        work_dir = Path(args.work_dir).absolute()
        if not args.dry_run and not args.confirm_upload:
            raise WorkflowError(
                "live workflow uploads every shot to HeyGen; pass --confirm-upload"
            )
        if not args.dry_run:
            preflight(manifest)
        plan = build_plan(
            manifest,
            manifest_path.parent,
            work_dir,
            args.dry_run,
            args.confirm_upload,
        )
        if args.dry_run:
            print(json.dumps(plan, indent=2))
            return 0
        ensure_artifacts_available(plan)
        execute_plan(plan)
        print(plan["final_output"] or plan["shot_outputs"][-1])
        return 0
    except (ManifestError, WorkflowError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
