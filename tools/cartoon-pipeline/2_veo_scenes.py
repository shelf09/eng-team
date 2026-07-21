#!/usr/bin/env python3
"""Stage 2 — Veo animation.
Reads scenes.json, submits each keyframe to Veo 3.1 Fast as image-to-video with the
scene's dialogue in the prompt (Veo generates voices + lip-sync natively).
Resumable: operation names persist in $CARTOON_DIR/veo_ops.json; already-downloaded
clips are skipped. Output: $CARTOON_DIR/clips/<scene>.mp4
Scene names as arguments restrict the run to those scenes (default: all).
If keyframes/<scene>_end.png exists it is sent as the clip's last frame
(Veo 3.1 first/last-frame interpolation)."""
import os, re, sys, json, time, base64, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("CARTOON_DIR", os.path.join(HERE, "build"))
KEY = os.environ["GEMINI_API_KEY"]
MODEL = os.environ.get("VEO_MODEL", "veo-3.1-fast-generate-preview")
ROOT = "https://generativelanguage.googleapis.com/v1beta"

cfg = json.load(open(os.path.join(HERE, "scenes.json")))
clipdir = os.path.join(BASE, "clips")
os.makedirs(clipdir, exist_ok=True)
OPS = os.path.join(BASE, "veo_ops.json")

def jreq(url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data,
        headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)

def submit(name, prompt):
    img = base64.b64encode(open(f"{BASE}/keyframes/{name}.png", "rb").read()).decode()
    inst = {"prompt": prompt,
            "image": {"bytesBase64Encoded": img, "mimeType": "image/png"}}
    endpath = f"{BASE}/keyframes/{name}_end.png"
    if os.path.exists(endpath):
        end = base64.b64encode(open(endpath, "rb").read()).decode()
        inst["lastFrame"] = {"bytesBase64Encoded": end, "mimeType": "image/png"}
    params = {"aspectRatio": "9:16"}
    if "lite" not in MODEL:  # veo-3.1-lite rejects negativePrompt (HTTP 400)
        params["negativePrompt"] = "subtitles, captions, on-screen text, watermark, photorealistic"
    body = {"instances": [inst], "parameters": params}
    for attempt in range(4):
        try:
            resp = jreq(f"{ROOT}/models/{MODEL}:predictLongRunning?key={KEY}", body)
            print(f"[{name}] op {resp['name']}", flush=True)
            return resp["name"]
        except urllib.error.HTTPError as e:
            print(f"[{name}] submit HTTP {e.code}: {e.read().decode()[:200]}", flush=True)
            if e.code in (429, 503):
                time.sleep(30 * (attempt + 1)); continue
            return None
    return None

def find_uri(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("uri", "videoUri", "fileUri") and isinstance(v, str):
                return ("uri", v)
            if k in ("bytesBase64Encoded", "videoBytes") and isinstance(v, str):
                return ("b64", v)
            r = find_uri(v)
            if r: return r
    elif isinstance(obj, list):
        for it in obj:
            r = find_uri(it)
            if r: return r
    return None

def download(name, st):
    out = f"{clipdir}/{name}.mp4"
    found = find_uri(st.get("response", st))
    if found is None:  # e.g. RAI content filtering: done=true, no video
        raise RuntimeError(f"operation finished without a video: {json.dumps(st)[:300]}")
    kind, val = found
    if kind == "b64":
        data = base64.b64decode(val)
    else:
        dl = val if "key=" in val else val + (("&" if "?" in val else "?") + f"key={KEY}")
        req = urllib.request.Request(dl, headers={"x-goog-api-key": KEY})
        with urllib.request.urlopen(req, timeout=300) as r:
            data = r.read()          # read fully BEFORE creating the file
    tmp = out + ".part"
    open(tmp, "wb").write(data)
    os.replace(tmp, out)             # resume logic never sees a partial clip
    print(f"[{name}] DONE {os.path.getsize(out)//1024} KB", flush=True)

def main(names=None):
    scenes = cfg["scenes"]
    # scene names become file paths (same guard as 3_compose.sh)
    bad = [s["name"] for s in scenes
           if not re.fullmatch(r"[A-Za-z0-9_-]+", s["name"])]
    if bad:
        sys.exit(f"invalid scene name(s): {bad} (use letters/digits/_/- only)")
    if names:
        unknown = set(names) - {s["name"] for s in scenes}
        if unknown:
            sys.exit(f"unknown scene(s): {sorted(unknown)}")
        scenes = [s for s in scenes if s["name"] in names]

    ops = json.load(open(OPS)) if os.path.exists(OPS) else {}
    for sc in scenes:
        n = sc["name"]
        if os.path.exists(f"{clipdir}/{n}.mp4"):
            print(f"[{n}] exists, skipping"); continue
        if not ops.get(n):
            ops[n] = submit(n, cfg["style_video"] + " " + cfg["voices"] + " " + sc["action"])
            json.dump(ops, open(OPS, "w"))
            time.sleep(3)

    sel = [s["name"] for s in scenes]
    pending = {n: ops[n] for n in sel
               if ops.get(n) and not os.path.exists(f"{clipdir}/{n}.mp4")}
    for i in range(200):
        for n in list(pending):
            try:
                st = jreq(f"{ROOT}/{pending[n]}?key={KEY}")
            except Exception as e:
                print(f"[{n}] poll err {e}", flush=True)
                # a 404'd op is permanently gone (expired/corrupt): clear it so a
                # rerun resubmits; transient errors keep polling — clearing a live
                # paid op would double-spend
                if isinstance(e, urllib.error.HTTPError) and e.code == 404:
                    ops[n] = None
                    json.dump(ops, open(OPS, "w"))
                    del pending[n]
                continue
            if st.get("done"):
                if "error" in st:
                    print(f"[{n}] VEO ERROR {json.dumps(st['error'])[:300]}", flush=True)
                    # clear the op so a rerun resubmits instead of re-polling a dead op
                    ops[n] = None
                    json.dump(ops, open(OPS, "w"))
                else:
                    try:
                        download(n, st)
                    except Exception as ex:
                        # clear the op so a rerun resubmits instead of re-polling a dead op
                        print(f"[{n}] DOWNLOAD FAILED: {ex}", flush=True)
                        ops[n] = None
                        json.dump(ops, open(OPS, "w"))
                del pending[n]
        if not pending:
            break
        if i % 4 == 0:
            print(f"[{i*8:4}s] pending: {sorted(pending)}", flush=True)
        time.sleep(8)

    have = [n for n in sel if os.path.exists(f"{clipdir}/{n}.mp4")]
    print(f"FINISHED {len(have)}/{len(sel)}: {have}")
    return len(have) == len(sel)

if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1:] or None) else 1)
