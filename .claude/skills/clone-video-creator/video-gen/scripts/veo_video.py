#!/usr/bin/env python3
"""Generate a video clip with Veo 3.1 (Gemini API) — text-to-video or image-to-video.

Requires: pip install google-genai; GEMINI_API_KEY set.
Notes: 1080p/4k require --duration 8; image-to-video person generation is
restricted to adults; results are stored server-side ~2 days (this downloads
immediately); audio is generated natively.
"""
import argparse
import json
import os
import sys
import time


def main():
    p = argparse.ArgumentParser(description="Video clip via Veo 3.1 (Gemini API)")
    p.add_argument("--prompt", required=True, help="Action / camera / mood description")
    p.add_argument("--image", help="Optional scene image to animate (image-to-video)")
    p.add_argument("--reference", action="append", metavar="IMG",
                   help="Reference image for likeness (repeatable, up to 3; Veo 3.1 text-to-video; forces --duration 8)")
    p.add_argument("--model", default="veo-3.1-generate-preview",
                   help="Model id (default: %(default)s; also veo-3.1-fast-generate-preview, veo-3.1-lite-generate-preview)")
    p.add_argument("--aspect", choices=["16:9", "9:16"], help="Aspect ratio (default 16:9)")
    p.add_argument("--resolution", choices=["720p", "1080p", "4k"], help="Output resolution (1080p/4k need --duration 8)")
    p.add_argument("--duration", type=int, choices=[4, 6, 8], help="Clip seconds (default 8)")
    p.add_argument("--negative", help="Negative prompt (what to avoid)")
    p.add_argument("--out", default="video.mp4", help="Output path (default: %(default)s)")
    p.add_argument("--dry-run", action="store_true", help="Print the planned request and exit")
    args = p.parse_args()

    if args.image and not os.path.exists(args.image):
        sys.exit(f"error: --image file not found: {args.image}")
    if args.resolution in ("1080p", "4k") and args.duration not in (None, 8):
        sys.exit("error: 1080p/4k require --duration 8")
    if args.reference:
        if args.image:
            sys.exit("error: --reference is for text-to-video; don't combine with --image")
        if len(args.reference) > 3:
            sys.exit("error: at most 3 --reference images")
        for ref in args.reference:
            if not os.path.exists(ref):
                sys.exit(f"error: --reference file not found: {ref}")
        if args.duration not in (None, 8):
            sys.exit("error: reference images require --duration 8")
        args.duration = 8

    config = {k: v for k, v in {
        "aspect_ratio": args.aspect, "resolution": args.resolution,
        "duration_seconds": args.duration, "negative_prompt": args.negative,
    }.items() if v is not None}
    plan = {"model": args.model, "prompt": args.prompt, "image": args.image,
            "reference_images": args.reference, "config": config, "out": args.out}
    if args.dry_run:
        print(json.dumps(plan, indent=2))
        return

    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("error: GEMINI_API_KEY is not set (get one at aistudio.google.com/apikey)")

    from google import genai
    from google.genai import types

    client = genai.Client()
    kwargs = {"model": args.model, "prompt": args.prompt}
    if args.image:
        kwargs["image"] = types.Image.from_file(location=args.image)
    if args.reference:
        config["reference_images"] = [
            types.VideoGenerationReferenceImage(
                image=types.Image.from_file(location=ref), reference_type="asset")
            for ref in args.reference
        ]
    if config:
        kwargs["config"] = types.GenerateVideosConfig(**config)

    print(f"generating with {args.model} (typically 1-6 min) ...", file=sys.stderr)
    try:
        operation = client.models.generate_videos(**kwargs)
        while not operation.done:
            time.sleep(10)
            operation = client.operations.get(operation)
            print("  ...waiting", file=sys.stderr)
    except Exception as e:
        msg = str(e)
        if "RESOURCE_EXHAUSTED" in msg and "free_tier" in msg:
            sys.exit("error: this API key is on the FREE tier — Veo's free-tier limit is 0.\n"
                     "Enable billing on the key's project (aistudio.google.com/apikey ->\n"
                     "your key's project -> set up billing / upgrade plan), then retry.")
        sys.exit(f"error: API call failed: {msg[:400]}")

    if getattr(operation, "error", None):
        sys.exit(f"error: generation failed: {operation.error}")
    videos = getattr(operation.response, "generated_videos", None) or []
    if not videos:
        sys.exit("error: no video returned (possibly safety-blocked; blocked generations are not billed)")

    video = videos[0]
    client.files.download(file=video.video)
    video.video.save(args.out)
    print(args.out)


if __name__ == "__main__":
    main()
