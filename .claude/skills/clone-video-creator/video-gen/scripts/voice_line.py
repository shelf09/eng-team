#!/usr/bin/env python3
"""Generate a spoken voice line with Gemini TTS — a consistent, scripted voice.

Requires: pip install google-genai; GEMINI_API_KEY set.
Output is a 24 kHz mono WAV. Mux over a video with:
  ffmpeg -i video.mp4 -i voice.wav -filter_complex "[1:a]apad[a]" \\
         -map 0:v -map "[a]" -c:v copy -t <video seconds> out.mp4
"""
import argparse
import json
import os
import sys
import wave


def main():
    p = argparse.ArgumentParser(description="Scripted voice line via Gemini TTS")
    p.add_argument("--text", help="The line to speak")
    p.add_argument("--text-file", help="Read the line from a file instead")
    p.add_argument("--voice", default="Charon",
                   help="Prebuilt voice name (default: %(default)s; e.g. Charon, Puck, Fenrir, Kore, Enceladus)")
    p.add_argument("--style", help='Delivery direction, e.g. "deep, warm, confident, unhurried"')
    p.add_argument("--model", default="gemini-2.5-flash-preview-tts",
                   help="TTS model (default: %(default)s; also gemini-3.1-flash-tts-preview, gemini-2.5-pro-preview-tts)")
    p.add_argument("--out", default="voice.wav", help="Output WAV path (default: %(default)s)")
    p.add_argument("--dry-run", action="store_true", help="Print the planned request and exit")
    args = p.parse_args()

    text = args.text or (open(args.text_file).read().strip() if args.text_file else None)
    if not text:
        sys.exit("error: --text or --text-file is required")
    contents = f"Say in a {args.style} voice: {text}" if args.style else text

    if args.dry_run:
        print(json.dumps({"model": args.model, "voice": args.voice,
                          "contents": contents, "out": args.out}, indent=2))
        return

    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("error: GEMINI_API_KEY is not set")

    from google import genai
    from google.genai import types

    client = genai.Client()
    print(f"speaking with {args.model} / voice {args.voice} ...", file=sys.stderr)
    try:
        resp = client.models.generate_content(
            model=args.model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=args.voice))),
            ),
        )
    except Exception as e:
        msg = str(e)
        if "RESOURCE_EXHAUSTED" in msg and "free_tier" in msg:
            sys.exit("error: free-tier key — enable billing at aistudio.google.com/apikey")
        sys.exit(f"error: API call failed: {msg[:400]}")

    pcm = None
    for part in resp.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            pcm = part.inline_data.data
            break
    if not pcm:
        sys.exit("error: no audio in response")

    # Gemini TTS returns raw 16-bit mono PCM at 24 kHz — wrap it in a WAV header.
    with wave.open(args.out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(pcm)
    print(f"{args.out}  ({len(pcm) / (24000 * 2):.1f}s)", file=sys.stderr)
    print(args.out)


if __name__ == "__main__":
    main()
