#!/usr/bin/env python3
"""Generate or edit a scene image with Nano Banana (Gemini image models).

Requires: pip install google-genai; GEMINI_API_KEY set.
"""
import argparse
import json
import mimetypes
import os
import sys


def main():
    p = argparse.ArgumentParser(description="Scene image via Nano Banana (Gemini image models)")
    p.add_argument("--prompt", required=True, help="Scene description (or edit instruction with --edit)")
    p.add_argument("--edit", metavar="IMAGE", help="Existing image to edit instead of generating fresh")
    p.add_argument("--model", default="gemini-3.1-flash-image-preview",
                   help="Model id (default: %(default)s — Nano Banana 2; older: gemini-2.5-flash-image)")
    p.add_argument("--aspect", help="Aspect ratio, e.g. 16:9, 9:16, 1:1 (omit for model default)")
    p.add_argument("--out", default="scene.png", help="Output image path (default: %(default)s)")
    p.add_argument("--dry-run", action="store_true", help="Print the planned request and exit")
    args = p.parse_args()

    if args.edit and not os.path.exists(args.edit):
        sys.exit(f"error: --edit file not found: {args.edit}")

    plan = {"model": args.model, "prompt": args.prompt, "edit_image": args.edit,
            "aspect_ratio": args.aspect, "out": args.out}
    if args.dry_run:
        print(json.dumps(plan, indent=2))
        return

    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("error: GEMINI_API_KEY is not set (get one at aistudio.google.com/apikey)")

    from google import genai
    from google.genai import types

    client = genai.Client()
    contents = [args.prompt]
    if args.edit:
        mime = mimetypes.guess_type(args.edit)[0] or "image/png"
        with open(args.edit, "rb") as f:
            contents.append(types.Part.from_bytes(data=f.read(), mime_type=mime))

    config_kwargs = {"response_modalities": ["IMAGE"]}
    if args.aspect:
        try:
            config_kwargs["image_config"] = types.ImageConfig(aspect_ratio=args.aspect)
        except AttributeError:
            print("note: this SDK version has no ImageConfig; ignoring --aspect", file=sys.stderr)

    print(f"generating with {args.model} ...", file=sys.stderr)
    try:
        resp = client.models.generate_content(
            model=args.model, contents=contents,
            config=types.GenerateContentConfig(**config_kwargs),
        )
    except Exception as e:
        msg = str(e)
        if "RESOURCE_EXHAUSTED" in msg and "free_tier" in msg:
            sys.exit("error: this API key is on the FREE tier — image models have a free-tier limit of 0.\n"
                     "Enable billing on the key's project (aistudio.google.com/apikey ->\n"
                     "your key's project -> set up billing / upgrade plan), then retry.")
        sys.exit(f"error: API call failed: {msg[:400]}")

    for part in resp.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            with open(args.out, "wb") as f:
                f.write(part.inline_data.data)
            print(args.out)
            return
    sys.exit(f"error: no image in response (text: {getattr(resp, 'text', '')!r:.200})")


if __name__ == "__main__":
    main()
