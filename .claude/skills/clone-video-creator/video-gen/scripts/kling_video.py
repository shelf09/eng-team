#!/usr/bin/env python3
"""Generate a video clip with Kling AI — text-to-video or image-to-video.

Stdlib only. Requires KLING_ACCESS_KEY and KLING_SECRET_KEY (developer console).
Auth is a short-lived HS256 JWT built from those keys. Model names shift with
releases — override --model if the default is rejected, and verify the current
list in Kling's API docs.
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("KLING_BASE_URL", "https://api-singapore.klingai.com")


def _b64url(data: bytes) -> bytes:
    return base64.urlsafe_b64encode(data).rstrip(b"=")


def kling_jwt(access_key: str, secret_key: str) -> str:
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    now = int(time.time())
    payload = _b64url(json.dumps({"iss": access_key, "exp": now + 1800, "nbf": now - 5}).encode())
    signature = _b64url(hmac.new(secret_key.encode(), header + b"." + payload, hashlib.sha256).digest())
    return (header + b"." + payload + b"." + signature).decode()


def api(method: str, path: str, token: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"error: HTTP {e.code} on {path}: {e.read().decode(errors='replace')[:500]}")
    if resp.get("code") not in (0, None):
        sys.exit(f"error: Kling API code {resp.get('code')}: {resp.get('message')}")
    return resp


def main():
    p = argparse.ArgumentParser(description="Video clip via Kling AI")
    p.add_argument("--prompt", required=True, help="Action / camera / mood description")
    p.add_argument("--image", help="Scene image to animate: local path (sent base64) or URL")
    p.add_argument("--image-tail", help="End-frame image (kling-v2-1 pro mode only): local path or URL")
    p.add_argument("--model", default="kling-v2-1", help="model_name (default: %(default)s — verify current list)")
    p.add_argument("--mode", choices=["std", "pro"], default="std", help="Generation mode (default: %(default)s)")
    p.add_argument("--duration", choices=["5", "10"], default="5", help="Clip seconds (default: %(default)s)")
    p.add_argument("--aspect", choices=["16:9", "9:16", "1:1"], help="Aspect ratio (text-to-video only)")
    p.add_argument("--negative", help="Negative prompt")
    p.add_argument("--out", default="video.mp4", help="Output path (default: %(default)s)")
    p.add_argument("--dry-run", action="store_true", help="Print the planned request and exit")
    args = p.parse_args()

    body = {"model_name": args.model, "prompt": args.prompt,
            "mode": args.mode, "duration": args.duration}
    if args.negative:
        body["negative_prompt"] = args.negative
    if args.image:
        path = "/v1/videos/image2video"
        if args.image.startswith(("http://", "https://")):
            body["image"] = args.image
        elif os.path.exists(args.image):
            with open(args.image, "rb") as f:
                body["image"] = base64.b64encode(f.read()).decode()
        else:
            sys.exit(f"error: --image not found: {args.image}")
        if args.image_tail:
            if args.image_tail.startswith(("http://", "https://")):
                body["image_tail"] = args.image_tail
            elif os.path.exists(args.image_tail):
                with open(args.image_tail, "rb") as f:
                    body["image_tail"] = base64.b64encode(f.read()).decode()
            else:
                sys.exit(f"error: --image-tail not found: {args.image_tail}")
    else:
        if args.image_tail:
            sys.exit("error: --image-tail requires --image (image2video only)")
        path = "/v1/videos/text2video"
        if args.aspect:
            body["aspect_ratio"] = args.aspect

    if args.dry_run:
        preview = dict(body)
        for key in ("image", "image_tail"):
            if len(preview.get(key, "")) > 80:
                preview[key] = f"<base64 {len(body[key])} chars>"
        print(json.dumps({"POST": BASE + path, "body": preview, "out": args.out}, indent=2))
        return

    ak, sk = os.environ.get("KLING_ACCESS_KEY"), os.environ.get("KLING_SECRET_KEY")
    if not (ak and sk):
        sys.exit("error: KLING_ACCESS_KEY / KLING_SECRET_KEY not set")

    token = kling_jwt(ak, sk)
    task = api("POST", path, token, body)["data"]
    task_id = task["task_id"]
    print(f"task {task_id} submitted; polling ...", file=sys.stderr)

    while True:
        time.sleep(10)
        token = kling_jwt(ak, sk)  # cheap; avoids expiry on long renders
        data = api("GET", f"{path}/{task_id}", token)["data"]
        status = data.get("task_status")
        if status == "succeed":
            url = data["task_result"]["videos"][0]["url"]
            break
        if status == "failed":
            sys.exit(f"error: task failed: {data.get('task_status_msg', 'no message')}")
        print(f"  ...{status}", file=sys.stderr)

    with urllib.request.urlopen(url, timeout=300) as r, open(args.out, "wb") as f:
        while chunk := r.read(1 << 16):
            f.write(chunk)
    print(args.out)


if __name__ == "__main__":
    main()
