#!/usr/bin/env bash
# Stage 3 — composite. Usage: bash 3_compose.sh out.mp4
# Auto-crops letterboxing per Veo clip, scales to 1080x1920, concats
# (optional cover.png/title.png/end.png in $CARTOON_DIR are included if present).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# same run-dir resolution as 0_chain.py: $CARTOON_DIR, else the newest
# builds/*_<episode-slug> run dir, else the legacy build/ dir
BASE="${CARTOON_DIR:-$(python3 - "$HERE" <<'PY'
import glob, json, os, sys
here = sys.argv[1]
slug = json.load(open(os.path.join(here, "scenes.json"))).get("episode", "episode")
prior = sorted(glob.glob(os.path.join(here, "builds", "*_" + slug)))
print(prior[-1] if prior else os.path.join(here, "build"))
PY
)}"
echo "run dir: $BASE"
OUT="${1:?usage: 3_compose.sh out.mp4}"
VE="-c:v libx264 -pix_fmt yuv420p -r 30 -c:a aac -ar 44100 -ac 2 -b:a 192k"
cd "$BASE"
mkdir -p seg
: > seg/concat.txt

# optional cover (with optional title overlay baked via Pillow — ffmpeg drawtext
# is missing from Homebrew builds)
if [ "${COMPOSE_LIST_ONLY:-}" != "1" ] && [ -f cover.png ]; then
  if [ -f title.png ]; then
    python3 - <<'PY'
from PIL import Image
Image.alpha_composite(Image.open("cover.png").convert("RGBA"),
                      Image.open("title.png").convert("RGBA")).convert("RGB").save("seg/cover.png")
PY
  else cp cover.png seg/cover.png; fi
  ffmpeg -hide_banner -v error -y -loop 1 -i seg/cover.png -f lavfi -i anullsrc=r=44100:cl=stereo \
    -t 2.2 -vf "scale=1080:1920,setsar=1,format=yuv420p" $VE -shortest seg/00_cover.mp4
  echo "file '$BASE/seg/00_cover.mp4'" >> seg/concat.txt
fi

i=0
for clip in $(python3 -c "import json,os;print(' '.join(s['name'] for s in json.load(open(os.path.join('$HERE','scenes.json')))['scenes']))"); do
  [[ "$clip" =~ ^[A-Za-z0-9_-]+$ ]] || { echo "invalid scene name: '$clip' (use letters/digits/_/- only)"; exit 1; }
  i=$((i+1))
  in="clips/${clip}_heygen.mp4"
  [ -f "$in" ] || in="clips/${clip}_dub.mp4"
  [ -f "$in" ] || in="clips/${clip}.mp4"
  if [ "${COMPOSE_LIST_ONLY:-}" = "1" ]; then echo "$clip -> $in"; continue; fi
  crop=$(ffmpeg -hide_banner -i "$in" -vf "cropdetect=20:2:0" -frames:v 90 -f null - 2>&1 \
        | grep -oE "crop=[0-9]+:[0-9]+:[0-9]+:[0-9]+" | sort | uniq -c | sort -rn | head -1 | grep -oE "crop=.*")
  crop=${crop:-crop=in_w:in_h:0:0}
  echo "[$clip] $crop"
  ffmpeg -hide_banner -v error -y -i "$in" \
    -vf "${crop},scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,format=yuv420p" \
    $VE "seg/$(printf %02d $i)_${clip}.mp4"
  echo "file '$BASE/seg/$(printf %02d $i)_${clip}.mp4'" >> seg/concat.txt
done

[ "${COMPOSE_LIST_ONLY:-}" = "1" ] && exit 0

if [ -f end.png ]; then
  ffmpeg -hide_banner -v error -y -loop 1 -i end.png -f lavfi -i anullsrc=r=44100:cl=stereo \
    -t 2.8 -vf "scale=1080:1920,setsar=1,format=yuv420p" $VE -shortest seg/99_end.mp4
  echo "file '$BASE/seg/99_end.mp4'" >> seg/concat.txt
fi

ffmpeg -hide_banner -v error -y -f concat -safe 0 -i seg/concat.txt \
  -c:v libx264 -pix_fmt yuv420p -r 30 -c:a aac -ar 44100 -ac 2 -b:a 192k -movflags +faststart "$OUT"
echo "FINAL -> $OUT ($(ffprobe -v error -show_entries format=duration -of default=nk=1:nw=1 "$OUT")s)"
