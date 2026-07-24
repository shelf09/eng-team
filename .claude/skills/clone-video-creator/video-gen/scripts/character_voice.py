#!/usr/bin/env python3
"""Generate a character voice with ElevenLabs or a macOS system voice."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote


ELEVENLABS_BASE = "https://api.elevenlabs.io"


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects so the ElevenLabs key cannot reach another origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_authenticated(request: urllib.request.Request, timeout: float):
    return urllib.request.build_opener(NoRedirectHandler()).open(request, timeout=timeout)


def child_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in ("ELEVENLABS_API_KEY", "HEYGEN_API_KEY"):
        environment.pop(name, None)
    return environment


def installed_local_voices(say: str) -> set[str]:
    try:
        result = subprocess.run(
            [say, "-v", "?"],
            text=True,
            capture_output=True,
            env=child_environment(),
        )
    except OSError as exc:
        sys.exit(f"error: could not start macOS 'say': {exc}")
    if result.returncode:
        sys.exit(f"error: could not list installed macOS voices: {result.stderr.strip()[:400]}")
    voices = set()
    locale = re.compile(r"\s+[a-z]{2,3}_[A-Z0-9]{2,3}\s+#")
    for line in result.stdout.splitlines():
        match = locale.search(line)
        if match:
            voices.add(line[:match.start()].strip())
    if not voices:
        sys.exit("error: macOS 'say' returned no installed voices")
    return voices


def temporary_output_path(output: str, suffix: str) -> Path:
    destination = Path(output)
    try:
        temporary = tempfile.NamedTemporaryFile(
            prefix=f".{destination.name}.",
            suffix=suffix,
            dir=destination.parent,
            delete=False,
        )
    except OSError as exc:
        sys.exit(f"error: could not create a temporary output beside {output}: {exc}")
    path = Path(temporary.name)
    temporary.close()
    return path


def main():
    parser = argparse.ArgumentParser(description="Generate character voice audio")
    parser.add_argument("--provider", choices=["elevenlabs", "local"], default="elevenlabs")
    parser.add_argument("--text")
    parser.add_argument("--text-file")
    parser.add_argument("--voice-id", help="ElevenLabs voice ID")
    parser.add_argument("--local-voice", help="macOS system voice name")
    parser.add_argument("--rate", type=int, default=190, help="Local voice words per minute")
    parser.add_argument("--model", default="eleven_v3")
    parser.add_argument("--out", default="voice.wav")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.text is not None:
        text = args.text
    elif args.text_file:
        try:
            text = Path(args.text_file).read_text(encoding="utf-8").strip()
        except UnicodeDecodeError:
            sys.exit(f"error: --text-file {args.text_file} must be valid UTF-8")
        except OSError as exc:
            sys.exit(f"error: could not read --text-file {args.text_file}: {exc}")
    else:
        text = None
    if not text:
        sys.exit("error: --text or --text-file is required")

    if args.provider == "elevenlabs":
        if not args.voice_id:
            sys.exit("error: --voice-id is required for the ElevenLabs provider")
        suffix = Path(args.out).suffix.lower()
        if suffix not in {".mp3", ".wav"}:
            sys.exit("error: ElevenLabs output must end in .mp3 or .wav")
        url = (
            f"{ELEVENLABS_BASE}/v1/text-to-speech/{quote(args.voice_id, safe='')}"
            "?output_format=mp3_44100_128"
        )
        body = {"text": text, "model_id": args.model}
        if args.dry_run:
            print(json.dumps({
                "provider": "elevenlabs",
                "POST": url,
                "body": body,
                "out": args.out,
            }, indent=2))
            return
        key = os.environ.get("ELEVENLABS_API_KEY")
        if not key:
            sys.exit("error: ELEVENLABS_API_KEY is not set")
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            headers={
                "xi-api-key": key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
        )
        try:
            with open_authenticated(request, timeout=120) as response:
                audio = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:400]
            exc.close()
            sys.exit(f"error: ElevenLabs HTTP {exc.code}: {detail}")
        except (OSError, urllib.error.URLError) as exc:
            sys.exit(f"error: ElevenLabs request failed: {exc}")
        if not audio:
            sys.exit("error: ElevenLabs returned empty audio")
        destination = Path(args.out)
        if suffix == ".mp3":
            part = temporary_output_path(args.out, ".part.mp3")
            try:
                part.write_bytes(audio)
                os.replace(part, destination)
            except OSError as exc:
                part.unlink(missing_ok=True)
                sys.exit(f"error: could not write ElevenLabs output {args.out}: {exc}")
        else:
            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                sys.exit("error: WAV output requires ffmpeg; use an .mp3 output path instead")
            source = temporary_output_path(args.out, ".source.mp3")
            part = temporary_output_path(args.out, ".part.wav")
            try:
                source.write_bytes(audio)
                result = subprocess.run(
                    [ffmpeg, "-y", "-v", "error", "-i", str(source), "-ar", "44100",
                     "-ac", "1", "-c:a", "pcm_s16le", str(part)],
                    text=True,
                    capture_output=True,
                    env=child_environment(),
                )
                if result.returncode:
                    sys.exit(
                        "error: ffmpeg could not convert ElevenLabs audio: "
                        f"{result.stderr[:400]}"
                    )
                os.replace(part, destination)
            except OSError as exc:
                sys.exit(f"error: could not write ElevenLabs output {args.out}: {exc}")
            finally:
                source.unlink(missing_ok=True)
                part.unlink(missing_ok=True)
        print(args.out)
        return

    if not args.local_voice:
        sys.exit("error: --local-voice is required for the local provider")
    if args.rate <= 0:
        sys.exit("error: --rate must be positive")
    if Path(args.out).suffix.lower() != ".wav":
        sys.exit("error: local voice output must end in .wav")
    say = shutil.which("say")
    if not say:
        sys.exit("error: local provider requires macOS 'say'; use a supplied WAV/MP3 instead")
    if args.local_voice not in installed_local_voices(say):
        sys.exit(
            f"error: {args.local_voice!r} is not an installed macOS voice; "
            "list choices with: say -v '?'"
        )
    def local_command(output: str) -> list[str]:
        return [
            say,
            "-v",
            args.local_voice,
            "-r",
            str(args.rate),
            "-o",
            output,
            "--file-format=WAVE",
            "--data-format=LEI16@44100",
            "-f",
            "-",
        ]
    command = local_command(args.out)
    if args.dry_run:
        print(json.dumps({
            "provider": "local",
            "command": command,
            "stdin": text,
            "out": args.out,
        }, indent=2))
        return
    part = temporary_output_path(args.out, ".part.wav")
    try:
        result = subprocess.run(
            local_command(str(part)),
            input=text,
            text=True,
            capture_output=True,
            env=child_environment(),
        )
        if result.returncode:
            sys.exit(f"error: local voice generation failed: {result.stderr.strip()[:400]}")
        if not part.exists() or part.stat().st_size == 0:
            sys.exit("error: local voice generation returned empty audio")
        os.replace(part, args.out)
    except OSError as exc:
        sys.exit(f"error: could not write local voice output {args.out}: {exc}")
    finally:
        part.unlink(missing_ok=True)
    print(args.out)


if __name__ == "__main__":
    main()
