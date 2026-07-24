---
name: video-gen
description: Generate real videos, character voices, and scene images via API or local tools — Nano Banana (scene images), Veo 3.1 (cinematic clips with audio), Kling (longer/cheaper clips), ElevenLabs or macOS system voices, and HeyGen (talking avatars or existing-video lip-sync). Use when the user wants to actually render a video, voice, or image, not just plan one — "make the video," "generate a scene," "render my avatar saying X," "animate this image," "lip-sync this video."
---

# Video Generation Engines

This skill turns a **brief** into rendered media using several engines and
providers. Scripts live in `scripts/` — each is runnable, supports `--dry-run`
(prints its request or command plan without spending money), and prints the
output file path on success.

## The brief

Every request reduces to three inputs — collect them before picking an engine:

1. **Avatar** — the character is *provided*: an image the user supplies (a
   photo or a Nano Banana-generated character portrait) passed as
   `--character`, which HeyGen animates as a photo avatar. Alternatively an
   existing HeyGen avatar/look ID via `--avatar-id`
   (`heygen_avatar.py --list-avatars`). Omit for scene-only video.
2. **Scene image** — a file/URL the user provides, or one you generate with
   Nano Banana from a description.
3. **Description** — what happens: the script the avatar speaks, or the
   action/camera/mood prompt for scene video.

## Engine chooser

| You need | Engine | Script |
|---|---|---|
| A scene image (or edit one) | Nano Banana (Gemini image) | `scripts/scene_image.py` |
| Cinematic clip ≤8s, native audio, top quality | Veo 3.1 | `scripts/veo_video.py` |
| Scene clip 5–10s, cheaper, batch-friendly | Kling | `scripts/kling_video.py` |
| A person talking to camera (avatar + background + script) | HeyGen | `scripts/heygen_avatar.py` |
| Re-sync an existing video's mouth to finished audio | HeyGen Precision Lipsync | `scripts/heygen_lipsync.py` |
| A character voice from ElevenLabs or a macOS system voice | ElevenLabs / macOS local | `scripts/character_voice.py` |
| An ordered, multi-character cartoon from one-speaker shots | ElevenLabs / macOS system / existing audio + HeyGen | `scripts/cartoon_voiceover.py` |
| A scripted voice line in a consistent voice | Gemini TTS | `scripts/voice_line.py` |

Chain them: Nano Banana makes the scene image → Veo/Kling animates it, or
HeyGen puts the avatar in front of it.

## Setup (once)

```bash
python3 -m venv .venv && .venv/bin/pip install google-genai   # Nano Banana + Veo only; Kling/HeyGen are stdlib
export GEMINI_API_KEY=...       # aistudio.google.com/apikey — BILLING REQUIRED:
                                # Veo and image models have a free-tier limit of 0
export KLING_ACCESS_KEY=... KLING_SECRET_KEY=...   # klingai.com developer console
export HEYGEN_API_KEY=...       # HeyGen dashboard → Settings → API
export ELEVENLABS_API_KEY=...   # ElevenLabs dashboard → API keys
```

Run the two Google scripts with the venv's interpreter (`.venv/bin/python3`);
macOS's system Python blocks package installs (PEP 668). Keys exported only in
an interactive terminal aren't visible to non-interactive shells — put them in
`~/.zshrc` or a `.env` you source.

Missing cloud keys fail fast with a message naming the variable. Cloud engines
bill per generation — quote rough cost expectations as "verify current
pricing," and use `--dry-run` first on anything experimental. The macOS `say`
provider runs offline and does not bill.

## Usage

**1. Scene image (Nano Banana):**

```bash
python3 scripts/scene_image.py --prompt "sunlit loft office, plants, warm film look, empty desk facing camera" --aspect 16:9 --out scene.png
python3 scripts/scene_image.py --prompt "same room at night, city lights outside" --edit scene.png --out scene-night.png
```

**2. Animate a scene (Veo 3.1 — 4/6/8s, audio included):**

```bash
python3 scripts/veo_video.py --prompt "slow dolly-in across the loft, dust motes in the light, ambient morning sound" --image scene.png --aspect 16:9 --resolution 1080p --duration 8 --out loft.mp4
```

**3. Animate a scene (Kling — 5 or 10s, std/pro):**

```bash
python3 scripts/kling_video.py --prompt "camera pans right across the office as rain starts outside" --image scene.png --duration 10 --mode pro --out loft-kling.mp4
```

**4. Talking head (HeyGen — provided character + scene background + script):**

```bash
# the character is provided: a photo, or a portrait you generate first
python3 scripts/scene_image.py --prompt "portrait of a warm, confident founder in her 40s, studio light, facing camera" --aspect 9:16 --out character.png

python3 scripts/heygen_avatar.py --list-voices                   # pick a voice for the character
python3 scripts/heygen_avatar.py \
  --character character.png \
  --voice-id <voice_id> \
  --background scene.png \
  --text "Here's the thing nobody tells you about hiring your first marketer..." \
  --motion "subtle natural gestures, slight head tilt on emphasis" --expressiveness medium \
  --aspect 16:9 --resolution 1080p --title "hiring-01" --out talking-head.mp4
```

Or use an existing HeyGen avatar instead: `--avatar-id <id>` (find one with
`--list-avatars`; stock avatars have a default voice so `--voice-id` is
optional). `--background` accepts a local image (auto-uploaded via
`/v3/assets`), a URL, or a hex color like `#0e1116`. `--text-file script.md`
reads a longer script from disk.

**5. Generate character audio (ElevenLabs or a macOS system voice):**

```bash
# Expressive cloud voice. Use a Voice Library/design voice ID you are licensed to use.
python3 scripts/character_voice.py \
  --provider elevenlabs --voice-id <voice_id> \
  --text "That's three buzzwords in a trench coat." --out engineer.wav

# Offline macOS system voice. List installed names with: say -v '?'
python3 scripts/character_voice.py \
  --provider local --local-voice Samantha --rate 185 \
  --text "That's three buzzwords in a trench coat." --out engineer-local.wav
```

ElevenLabs output can be `.mp3` or a 44.1 kHz mono PCM `.wav`; WAV conversion
uses ffmpeg. Here, `--provider local` specifically means the offline macOS
system `say` command. For a portable local option on macOS, Linux, or Windows,
render with Piper, Kokoro, another local engine, or a human performer, then pass
the resulting WAV/MP3 directly to the lip-sync step; skip this script.

**6. Lip-sync an existing shot to that audio (HeyGen):**

```bash
# Inspect the exact upload/request without using credits.
python3 scripts/heygen_lipsync.py \
  --video speaking-shot.mp4 --audio engineer.wav \
  --mode precision --out speaking-shot-synced.mp4 --dry-run

# A live run also requires explicit upload confirmation.
python3 scripts/heygen_lipsync.py \
  --video speaking-shot.mp4 --audio engineer.wav \
  --mode precision --out speaking-shot-synced.mp4 --confirm-upload
```

Both inputs may be local files or public HTTPS URLs. Local MP4/WebM and WAV/MP3
files are uploaded to HeyGen automatically (simple uploads are limited to 32 MB).
**Live-upload warning:** a live run with `--confirm-upload` sends both media
inputs to HeyGen: local video and audio files are uploaded, while public URLs
are included for HeyGen to fetch. Audio generated offline is no longer
local-only after this step. The script defaults to Precision mode and never
sends the API key to the signed output URL. HeyGen's lipsync request has no face selector: for
multi-character cartoons, split the source into shots with one active speaker,
process those shots independently, then reassemble them in the editor. Always
test a short shot first because visual lip-sync can alter cartoon mouth/face
linework. Shot duration is preserved by default; add `--dynamic-duration` only
when HeyGen should lengthen or shorten the shot to fit the voice track.

**7. Run an ordered multi-character cartoon:**

Create `cartoon.json` next to the shot and audio files:

```json
{
  "version": 1,
  "shots": [
    {
      "id": "intro",
      "video": "shot-01.mp4",
      "voice": {
        "provider": "elevenlabs",
        "text": "That is three buzzwords in a trench coat.",
        "voice_id": "<voice_id>"
      }
    },
    {
      "id": "reply",
      "video": "shot-02.mp4",
      "voice": {
        "provider": "local",
        "text": "No. But you get synergy.",
        "voice": "Samantha",
        "rate": 185
      }
    },
    {
      "id": "button",
      "video": "shot-03.mp4",
      "voice": {"provider": "existing", "path": "recorded.wav"}
    }
  ],
  "concat": {"output": "episode.mp4"}
}
```

```bash
# Validate and inspect every command without keys, uploads, output writes, or credits.
python3 scripts/cartoon_voiceover.py \
  --manifest cartoon.json --work-dir rendered --dry-run

# Generate voices, lip-sync each one-speaker shot, and concatenate in order.
python3 scripts/cartoon_voiceover.py \
  --manifest cartoon.json --work-dir rendered --confirm-upload
```

The live runner preflights required keys and tools before starting, refuses to
overwrite planned artifacts, and requires one top-level upload confirmation
before passing it to every HeyGen shot. `concat` is optional. Use `existing`
for any human, Piper, Kokoro, or other pre-rendered WAV/MP3.

Manifest schema (unknown fields are rejected):

| Object | Fields |
|---|---|
| Root | `version` must be `1`; `shots` is a non-empty array; optional `concat.output` is a safe `.mp4` filename |
| Shot | Required `id`, `video`, and `voice`; optional `mode` (`precision` default or `speed`), `title`, and boolean `dynamic_duration` |
| ElevenLabs voice | `provider: "elevenlabs"`, `text`, `voice_id`; optional `model` |
| macOS system voice | `provider: "local"`, `text`, installed voice name in `voice`; optional `rate` from 80–500 |
| Existing audio | `provider: "existing"` and WAV/MP3 `path` |

IDs use letters, numbers, `_`, and `-`. Local inputs must already exist inside
the manifest directory (including during dry-run); public inputs use HTTPS and
a recognized suffix when the URL path has one. Set `dynamic_duration: true`
only for shots HeyGen may lengthen or shorten to fit their audio.

**8. Scripted voice + video mux (Gemini TTS — the reliable dialogue path):**

Veo generates ambient audio dependably, but spoken dialogue often comes out
missing or mixed at ambience level (~-35 dB) even when the prompt quotes the
line. The deterministic pattern: render the visual with Veo (character
visibly talking), speak the line with TTS, mux:

```bash
python3 scripts/voice_line.py --text "I'm Marcus. I make things." \
  --voice Charon --style "deep, warm, confident" --out line.wav
ffmpeg -i clip.mp4 -i line.wav -filter_complex "[1:a]apad[a]" \
  -map 0:v -map "[a]" -c:v copy -t 8 final.mp4
```

The voice is a named prebuilt (consistent across every render); lip-sync is
approximate — Veo's talking motion isn't driven by the waveform. For exact
sync, that's HeyGen's job.

## Recipes

- **Founder clip, no camera:** brain-profile script (via `/script`) →
  `/screening` gates → `scene_image.py` for the set → `heygen_avatar.py` with
  the user's provided character image (or custom avatar) over it.
- **B-roll pack:** one Nano Banana scene → Veo for the hero 8s (has audio) →
  Kling variations for cheap alt takes.
- **Scene continuity:** generate one scene image, reuse it as `--image` for
  every clip — same set across the whole video.

## Guardrails (binding)

- **Consent:** avatars, provided character images, and voices only of the
  person running this studio — or a fully synthetic character they generated —
  per the CAPTURE specs' consent sections. Refuse anyone else's likeness,
  including photos of real third parties passed as `--character`.
- **Disclosure:** anything these engines produce is synthetic media — run the
  compliance methodology (`.claude/commands/clone-video-creator/compliance.md`)
  before publishing; platform AI labels are not optional.
- **People in Veo:** image-to-video allows adult person generation only
  (`allow_adult`), stricter in EU/UK/CH/MENA — expect blocks, and note the
  user isn't charged for safety-blocked generations.
- **Retention:** Veo stores results server-side for ~2 days — always download
  immediately (the script does).
- **Model churn:** engine model lists shift quarterly (Veo 3.1 previews,
  Kling v2.x, Nano Banana 2 aka `gemini-3.1-flash-image-preview`). Every
  script takes `--model` to override its default; verify current IDs when a
  default 404s.

## Related

- `video-scripting` — what the clip should *say* before you render it.
- `../../../commands/clone-video-creator/video-clone.md` — the avatar spec the
  render must obey (framing, backgrounds, drift checklist).
- Marketing collection's `video` skill — tool landscape and strategy;
  `.claude/tools/marketing/integrations/heygen.md` — account setup and MCP option.
