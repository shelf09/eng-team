#!/usr/bin/env python3
"""Create a HeyGen talking-head video: avatar + background (scene image) + script.

Stdlib only. Requires HEYGEN_API_KEY (dashboard -> Settings -> API).
Uses the v3 API (POST /v3/videos); v2 remains supported through Oct 2026.

The talking character comes from ONE of:
  --character IMG           a provided character image (local file or URL) —
                            HeyGen animates it as a photo avatar (type: image);
                            requires --voice-id (a provided image has no default voice)
  --avatar-id ID            an existing HeyGen avatar/look id

Other:
  --list-avatars            show avatar/look ids to use as --avatar-id
  --list-voices             show voice ids (stock avatars have a default voice)
  --background              hex color (#0e1116), image URL, or local file
                            (local files are uploaded via POST /v3/assets)
  --motion / --expressiveness   body-motion prompt and intensity (photo avatars)
"""
import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE = "https://api.heygen.com"


def api(method: str, path: str, key: str, body: dict | None = None,
        raw: bytes | None = None, content_type: str | None = None) -> dict:
    headers = {"x-api-key": key}
    data = raw
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    elif content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"error: HTTP {e.code} on {path}: {e.read().decode(errors='replace')[:500]}")


def upload_asset(path: str, key: str) -> dict:
    boundary = uuid.uuid4().hex
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        payload = f.read()
    if len(payload) > 32 * 1024 * 1024:
        sys.exit("error: background image exceeds HeyGen's 32 MB asset limit")
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{os.path.basename(path)}"\r\nContent-Type: {mime}\r\n\r\n'
    ).encode() + payload + f"\r\n--{boundary}--\r\n".encode()
    return api("POST", "/v3/assets", key, raw=body,
               content_type=f"multipart/form-data; boundary={boundary}")["data"]


def build_background(spec: str, key: str, dry: bool) -> dict:
    if spec.startswith("#"):
        return {"type": "color", "value": spec}
    if spec.startswith(("http://", "https://")):
        return {"type": "image", "url": spec}
    if os.path.exists(spec):
        if dry:
            return {"type": "image", "asset_id": f"<upload {spec} via /v3/assets>"}
        asset = upload_asset(spec, key)
        print(f"uploaded background: asset_id={asset['asset_id']}", file=sys.stderr)
        return {"type": "image", "asset_id": asset["asset_id"]}
    sys.exit(f"error: --background is neither a hex color, URL, nor existing file: {spec}")


def main():
    p = argparse.ArgumentParser(description="HeyGen talking-head video (v3 API)")
    p.add_argument("--list-avatars", action="store_true", help="List avatar/look ids and exit")
    p.add_argument("--list-voices", action="store_true", help="List voice ids and exit")
    p.add_argument("--avatar-id", help="Existing HeyGen avatar/look id (from --list-avatars)")
    p.add_argument("--character", metavar="IMG",
                   help="Provided character image (local file or URL) to animate instead of --avatar-id")
    p.add_argument("--motion", help="Natural-language body-motion prompt (photo avatars)")
    p.add_argument("--expressiveness", choices=["low", "medium", "high"],
                   help="Motion intensity (photo avatars; default low)")
    p.add_argument("--text", help="Script the avatar speaks")
    p.add_argument("--text-file", help="Read the script from a file instead")
    p.add_argument("--voice-id", help="Voice id (omit to use the avatar's default voice)")
    p.add_argument("--speed", type=float, help="Voice speed 0.5-1.5")
    p.add_argument("--background", help="Hex color, image URL, or local image path")
    p.add_argument("--aspect", default="16:9", choices=["16:9", "9:16", "4:5", "5:4", "1:1"],
                   help="Aspect ratio (default: %(default)s)")
    p.add_argument("--resolution", default="1080p", choices=["720p", "1080p", "4k"],
                   help="Resolution (default: %(default)s)")
    p.add_argument("--title", help="Dashboard title for the video")
    p.add_argument("--out", default="avatar.mp4", help="Output path (default: %(default)s)")
    p.add_argument("--dry-run", action="store_true", help="Print the planned request and exit")
    args = p.parse_args()

    key = os.environ.get("HEYGEN_API_KEY", "")
    if not (key or args.dry_run):
        sys.exit("error: HEYGEN_API_KEY is not set (HeyGen dashboard -> Settings -> API)")

    if args.list_avatars or args.list_voices:
        path = "/v3/avatars/looks?limit=50" if args.list_avatars else "/v3/voices"
        data = api("GET", path, key)
        items = data.get("data", data)
        for item in items if isinstance(items, list) else items.get("voices", []):
            if args.list_avatars:
                print(f"{item['id']}  {item.get('avatar_type', '')}  {item['name']}"
                      f"  (default_voice: {item.get('default_voice_id') or '-'})")
            else:
                print(f"{item.get('voice_id', item.get('id'))}  {item.get('language', '')}"
                      f"  {item.get('gender', '')}  {item.get('name', '')}")
        return

    script = args.text or (open(args.text_file).read().strip() if args.text_file else None)
    if bool(args.avatar_id) == bool(args.character):
        sys.exit("error: provide exactly one of --avatar-id (stock/custom avatar) or --character (your own image)")
    if not script:
        sys.exit("error: --text or --text-file is required to create a video")

    if args.character:
        if not args.voice_id:
            sys.exit("error: --voice-id is required with --character (a provided image has no default voice; see --list-voices)")
        if args.character.startswith(("http://", "https://")):
            image = {"type": "url", "url": args.character}
        elif os.path.exists(args.character):
            if args.dry_run:
                image = {"type": "asset_id", "asset_id": f"<upload {args.character} via /v3/assets>"}
            else:
                asset = upload_asset(args.character, key)
                print(f"uploaded character: asset_id={asset['asset_id']}", file=sys.stderr)
                image = {"type": "asset_id", "asset_id": asset["asset_id"]}
        else:
            sys.exit(f"error: --character is neither a URL nor an existing file: {args.character}")
        body = {"type": "image", "image": image, "script": script,
                "resolution": args.resolution, "aspect_ratio": args.aspect}
        if args.motion:
            body["motion_prompt"] = args.motion
        if args.expressiveness:
            body["expressiveness"] = args.expressiveness
    else:
        body = {"type": "avatar", "avatar_id": args.avatar_id, "script": script,
                "resolution": args.resolution, "aspect_ratio": args.aspect}
        if args.motion:
            body["motion_prompt"] = args.motion
        if args.expressiveness:
            body["expressiveness"] = args.expressiveness

    if args.voice_id:
        body["voice_id"] = args.voice_id
    if args.speed:
        body["voice_settings"] = {"speed": args.speed}
    if args.background:
        body["background"] = build_background(args.background, key, args.dry_run)
    if args.title:
        body["title"] = args.title

    if args.dry_run:
        print(json.dumps({"POST": f"{BASE}/v3/videos", "body": body, "out": args.out}, indent=2))
        return

    video_id = api("POST", "/v3/videos", key, body)["data"]["video_id"]
    print(f"video {video_id} submitted; polling ...", file=sys.stderr)

    while True:
        time.sleep(10)
        data = api("GET", f"/v3/videos/{video_id}", key)
        data = data.get("data", data)
        status = data.get("status")
        if status == "completed":
            url = data["video_url"]
            break
        if status == "failed":
            sys.exit(f"error: render failed: {data.get('failure_code')} {data.get('failure_message')}")
        print(f"  ...{status}", file=sys.stderr)

    with urllib.request.urlopen(url, timeout=300) as r, open(args.out, "wb") as f:
        while chunk := r.read(1 << 16):
            f.write(chunk)
    print(args.out)


if __name__ == "__main__":
    main()
