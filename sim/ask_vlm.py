"""
ask_vlm.py — send rendered frames to the self-hosted Cosmos Reason 2 NIM and print its answer.

The NIM serves an OpenAI-compatible API on the box (default http://localhost:8000).
Images go in as base64 data URLs. Plain python3, stdlib only.

  python3 sim/ask_vlm.py renders/venue_oblique.png \
      --prompt "How many people are visible? Is any exit blocked by smoke?"
"""
import argparse
import base64
import json
import mimetypes
import sys
import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("images", nargs="+", help="PNG/JPG frames to send (in order)")
ap.add_argument("--prompt", required=True)
ap.add_argument("--url", default="http://localhost:8000")
ap.add_argument("--model", default=None, help="model id; default = first one the server lists")
ap.add_argument("--max-tokens", type=int, default=1024)
args = ap.parse_args()


def get(path):
    with urllib.request.urlopen(args.url + path, timeout=30) as r:
        return json.load(r)


model = args.model or get("/v1/models")["data"][0]["id"]

content = []
for p in args.images:
    mime = mimetypes.guess_type(p)[0] or "image/png"
    b64 = base64.b64encode(open(p, "rb").read()).decode()
    content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
content.append({"type": "text", "text": args.prompt})

body = {
    "model": model,
    "messages": [
        {"role": "system", "content": "You are a safety analyst reviewing camera frames of a public venue. "
                                      "Answer only from what is visible. Say when you cannot tell."},
        {"role": "user", "content": content},
    ],
    "max_tokens": args.max_tokens,
    "temperature": 0.2,
}
req = urllib.request.Request(args.url + "/v1/chat/completions", data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.load(r)
except urllib.error.HTTPError as e:
    sys.exit(f"HTTP {e.code}: {e.read().decode()[:500]}")

print(f"[model] {model}")
print(out["choices"][0]["message"]["content"])
