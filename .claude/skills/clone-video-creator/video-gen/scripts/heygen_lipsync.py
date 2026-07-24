#!/usr/bin/env python3
"""Replace a video's audio and re-animate its lips with HeyGen v3."""

import argparse
import ipaddress
import json
import math
import mimetypes
import os
import socket
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import urlsplit


BASE = "https://api.heygen.com"
MAX_ASSET_BYTES = 32 * 1024 * 1024
VIDEO_SUFFIXES = {".mp4", ".webm"}
AUDIO_SUFFIXES = {".mp3", ".wav"}
SUPPORTED_SUFFIXES = VIDEO_SUFFIXES | AUDIO_SUFFIXES


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects so authenticated headers cannot reach another origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class PublicHttpsRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Allow downloads to redirect only to another public HTTPS URL."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_https_url(newurl, "download", resolve_host=True)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_authenticated(request: urllib.request.Request, timeout: float):
    return urllib.request.build_opener(NoRedirectHandler()).open(request, timeout=timeout)


def validate_public_https_url(
    value: str,
    label: str = "media",
    resolve_host: bool = False,
) -> str:
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        sys.exit(f"error: {label} URL is invalid")
    if parsed.scheme.lower() != "https" or not hostname:
        sys.exit(f"error: {label} URLs must use public HTTPS")
    if parsed.username is not None or parsed.password is not None:
        sys.exit(f"error: {label} URL must not contain credentials")
    if port is not None and not 1 <= port <= 65535:
        sys.exit(f"error: {label} URL has an invalid port")
    lowered = hostname.rstrip(".").lower()
    if lowered == "localhost" or lowered.endswith((".localhost", ".local")):
        sys.exit(f"error: {label} URL must use a public host")
    try:
        address = ipaddress.ip_address(lowered.strip("[]"))
    except ValueError:
        try:
            address = ipaddress.ip_address(socket.inet_ntoa(socket.inet_aton(lowered)))
        except OSError:
            address = None
    if address is not None and not address.is_global:
        sys.exit(f"error: {label} URL must use a public host")
    if resolve_host and address is None:
        try:
            resolved = socket.getaddrinfo(lowered, port or 443, type=socket.SOCK_STREAM)
        except OSError as exc:
            sys.exit(f"error: could not resolve {label} URL host: {exc}")
        if not resolved or any(
            not ipaddress.ip_address(item[4][0]).is_global for item in resolved
        ):
            sys.exit(f"error: {label} URL must resolve only to public addresses")
    return value


def api(method: str, path: str, key: str, body: dict | None = None) -> dict:
    headers = {"x-api-key": key}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with open_authenticated(request, timeout=180) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        exc.close()
        sys.exit(f"error: HeyGen HTTP {exc.code} on {path}: {detail}")
    except (OSError, urllib.error.URLError) as exc:
        sys.exit(f"error: HeyGen request failed on {path}: {exc}")


def upload_asset(path: str, key: str) -> str:
    source = Path(path)
    if source.suffix.lower() not in SUPPORTED_SUFFIXES:
        sys.exit("error: HeyGen lipsync assets must be MP4, WebM, MP3, or WAV")
    boundary = uuid.uuid4().hex
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    filename = source.name
    if any(ord(character) < 32 or ord(character) == 127 for character in filename):
        sys.exit("error: media filename must not contain control characters")
    filename = filename.replace("\\", "_").replace('"', "_")
    try:
        with source.open("rb") as handle:
            details = os.fstat(handle.fileno())
            if not stat.S_ISREG(details.st_mode):
                sys.exit(f"error: media input is not a regular file: {path}")
            if details.st_size > MAX_ASSET_BYTES:
                sys.exit(f"error: {path} exceeds HeyGen's 32 MB simple-upload limit")
            payload = handle.read(MAX_ASSET_BYTES + 1)
    except OSError as exc:
        sys.exit(f"error: could not read media input {path}: {exc}")
    if len(payload) > MAX_ASSET_BYTES:
        sys.exit(f"error: {path} exceeds HeyGen's 32 MB simple-upload limit")
    if len(payload) != details.st_size:
        sys.exit(f"error: media input changed while it was being read: {path}")
    raw = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'
    ).encode() + payload + f"\r\n--{boundary}--\r\n".encode()
    headers = {
        "x-api-key": key,
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    request = urllib.request.Request(BASE + "/v3/assets", data=raw, method="POST", headers=headers)
    try:
        with open_authenticated(request, timeout=300) as response:
            result = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        exc.close()
        sys.exit(f"error: HeyGen asset upload HTTP {exc.code}: {detail}")
    except (OSError, urllib.error.URLError) as exc:
        sys.exit(f"error: HeyGen asset upload failed: {exc}")
    data = result.get("data", result)
    asset_id = data.get("asset_id") or data.get("id")
    if not asset_id:
        sys.exit(f"error: HeyGen asset upload returned no asset id: {str(result)[:300]}")
    return asset_id


def asset_input(spec: str, dry_run: bool, key: str = "", kind: str = "media") -> dict:
    if "://" in spec:
        url = validate_public_https_url(spec, "media")
        suffix = Path(urlsplit(url).path).suffix.lower()
        if kind == "video" and suffix and suffix not in VIDEO_SUFFIXES:
            sys.exit("error: video input must be MP4 or WebM")
        if kind == "audio" and suffix and suffix not in AUDIO_SUFFIXES:
            sys.exit("error: audio input must be MP3 or WAV")
        return {"type": "url", "url": url}
    if not os.path.exists(spec):
        sys.exit(f"error: media input is neither a URL nor an existing file: {spec}")
    suffix = Path(spec).suffix.lower()
    if kind == "video" and suffix not in VIDEO_SUFFIXES:
        sys.exit("error: video input must be MP4 or WebM")
    if kind == "audio" and suffix not in AUDIO_SUFFIXES:
        sys.exit("error: audio input must be MP3 or WAV")
    if kind == "media" and suffix not in SUPPORTED_SUFFIXES:
        sys.exit("error: HeyGen lipsync assets must be MP4, WebM, MP3, or WAV")
    if Path(spec).stat().st_size > MAX_ASSET_BYTES:
        sys.exit(f"error: {spec} exceeds HeyGen's 32 MB simple-upload limit")
    if dry_run:
        return {"type": "asset_id", "asset_id": f"<upload {spec} via /v3/assets>"}
    return {"type": "asset_id", "asset_id": upload_asset(spec, key)}


def download(url: str, output: str) -> None:
    validate_public_https_url(url, "download", resolve_host=True)
    destination = Path(output)
    part = None
    try:
        temporary = tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.name}.",
            suffix=".part",
            dir=destination.parent,
            delete=False,
        )
        part = Path(temporary.name)
        opener = urllib.request.build_opener(PublicHttpsRedirectHandler())
        with temporary as target, opener.open(url, timeout=300) as response:
            expected_header = response.headers.get("Content-Length")
            try:
                expected = int(expected_header) if expected_header is not None else None
            except ValueError as exc:
                raise OSError("download returned an invalid Content-Length") from exc
            if expected is not None and expected < 0:
                raise OSError("download returned an invalid Content-Length")
            received = 0
            while chunk := response.read(1 << 16):
                target.write(chunk)
                received += len(chunk)
            if expected is not None and received != expected:
                raise OSError(
                    f"incomplete download: expected {expected} bytes but received {received}"
                )
            if received == 0:
                raise OSError("download returned an empty video")
            target.flush()
            os.fsync(target.fileno())
        os.replace(part, destination)
    except Exception:
        if part is not None:
            part.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(
        description="HeyGen existing-video lipsync with supplied voice audio"
    )
    parser.add_argument("--video", required=True, help="Local path or public URL")
    parser.add_argument("--audio", required=True, help="Local WAV/MP3 or public URL")
    parser.add_argument("--mode", choices=["speed", "precision"], default="precision")
    parser.add_argument(
        "--dynamic-duration",
        action="store_true",
        help="Allow HeyGen to change shot length to match audio (default preserves timing)",
    )
    parser.add_argument("--title")
    parser.add_argument("--poll-interval", type=float, default=10.0)
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--out", default="lipsynced.mp4")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--confirm-upload",
        action="store_true",
        help="Acknowledge that the video and audio will be sent to HeyGen",
    )
    args = parser.parse_args()

    if not math.isfinite(args.poll_interval) or args.poll_interval <= 0:
        sys.exit("error: --poll-interval must be a positive finite number")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        sys.exit("error: --timeout must be a positive finite number")
    if Path(args.out).suffix.lower() != ".mp4":
        sys.exit("error: --out must end in .mp4")
    if not args.dry_run and not args.confirm_upload:
        sys.exit(
            "error: live rendering uploads the video and audio to HeyGen; "
            "pass --confirm-upload to continue"
        )

    key = os.environ.get("HEYGEN_API_KEY", "")
    if not (key or args.dry_run):
        sys.exit("error: HEYGEN_API_KEY is not set")
    body = {
        "video": asset_input(args.video, args.dry_run, key, "video"),
        "audio": asset_input(args.audio, args.dry_run, key, "audio"),
        "mode": args.mode,
        "enable_dynamic_duration": args.dynamic_duration,
    }
    if args.title:
        body["title"] = args.title
    if args.dry_run:
        print(json.dumps({"POST": f"{BASE}/v3/lipsyncs", "body": body, "out": args.out}, indent=2))
        return

    response = api("POST", "/v3/lipsyncs", key, body)
    lipsync_id = response.get("data", response).get("lipsync_id")
    if not lipsync_id:
        sys.exit(f"error: HeyGen returned no lipsync id: {str(response)[:300]}")
    print(f"lipsync {lipsync_id} submitted; polling ...", file=sys.stderr)
    deadline = time.monotonic() + args.timeout
    while time.monotonic() <= deadline:
        result = api("GET", f"/v3/lipsyncs/{lipsync_id}", key)
        data = result.get("data", result)
        status = data.get("status")
        if status == "completed":
            video_url = data.get("video_url")
            if not video_url:
                sys.exit("error: completed HeyGen lipsync returned no video URL")
            try:
                download(video_url, args.out)
            except Exception as exc:
                sys.exit(f"error: could not download completed video: {exc}")
            print(args.out)
            return
        if status == "failed":
            sys.exit(f"error: HeyGen lipsync failed: {data.get('failure_message', 'unknown error')}")
        time.sleep(max(args.poll_interval, 0))
    sys.exit(f"error: HeyGen lipsync timed out after {args.timeout:g} seconds")


if __name__ == "__main__":
    main()
