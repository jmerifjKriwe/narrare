#!/usr/bin/env python3
"""Bulk-download Stitch screens to disk (bypasses the agent context window).

Usage:
  STITCH_API_KEY=... python3 scripts/stitch_download.py \\
      --project 15314899202287259920 --out docs/design/stitch/screens/_bulk
"""

import argparse
import base64
import json
import os
import re
import sys
import urllib.request
from typing import Any, cast

BASE = "https://stitch.googleapis.com/v1"


def req(path: str, key: str) -> dict[str, Any]:
    url = path if path.startswith("https://") else f"{BASE}{path}"
    # S310 audits the scheme of every non-literal URL; the only producer of
    # absolute paths is the API's own downloadUrl, and this check pins both
    # cases to https before the socket opens.
    if not url.startswith("https://"):
        raise ValueError(f"refusing non-https URL: {url!r}")
    r = urllib.request.Request(  # noqa: S310 - scheme pinned above
        url, headers={"X-Goog-Api-Key": key}
    )
    with urllib.request.urlopen(r) as f:  # noqa: S310 - scheme pinned above
        loaded = cast("dict[str, Any]", json.load(f))
    return loaded


def slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower() or "screen"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--out", default="docs/design/stitch/screens/_bulk")
    ap.add_argument("--key", default=os.environ.get("STITCH_API_KEY"))
    args = ap.parse_args()
    if not args.key:
        sys.exit("STITCH_API_KEY missing (env or --key)")

    os.makedirs(args.out, exist_ok=True)
    listing = req(f"/projects/{args.project}/screens", args.key)
    screens = cast("list[dict[str, Any]]", listing.get("screens", []))
    manifest: list[dict[str, Any]] = []
    for sc in screens:
        title = str(sc.get("title", "screen"))
        name = slug(title)
        for kind, field in (("html", "htmlCode"), ("image", "screenshot")):
            info = cast("dict[str, Any]", sc.get(field) or {})
            url = str(info.get("downloadUrl", ""))
            if not url:
                continue
            data = req(url, args.key)
            raw = str(data["dataString"])
            ext = "html" if kind == "html" else "webp"
            out = os.path.join(args.out, f"{name}.{ext}")
            i = 2
            while os.path.exists(out):
                out = os.path.join(args.out, f"{name}-{i}.{ext}")
                i += 1
            with open(out, "wb") as f:
                if kind == "html":
                    f.write(raw.encode())
                else:
                    f.write(base64.b64decode(raw))
            manifest.append({"title": title, "kind": kind, "file": os.path.relpath(out, args.out)})
        print(f"downloaded: {title}")
    with open(os.path.join(args.out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"done: {len(screens)} screens -> {args.out}")


if __name__ == "__main__":
    main()
