#!/usr/bin/env python3
"""Advisory documentation link checker.

Scans Markdown files for relative links and reports any that point at a
missing file. Exit code is 0 even when links are broken (advisory), so it can
run in CI without blocking merges; the report is the signal.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def main() -> int:
    broken: list[str] = []
    for md in ROOT.rglob("*.md"):
        if any(part in {".venv", "node_modules", "web/dist", ".agents"} for part in md.parts):
            continue
        # Archived v1 feature docs carry stale ADR references by design.
        if "docs" in md.parts and "features" in md.parts:
            continue
        # Historical design records: links are relative to their original
        # location and are not maintained.
        if "docs" in md.parts and "superpowers" in md.parts:
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        for match in LINK_RE.finditer(text):
            target = match.group(1).split("#", 1)[0].strip()
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = (md.parent / target).resolve()
            if not resolved.exists():
                broken.append(f"{md.relative_to(ROOT)} -> {target}")
    if broken:
        print(f"broken doc links: {len(broken)}")
        for b in broken[:50]:
            print(f"  {b}")
    else:
        print("no broken doc links")
    return 0


if __name__ == "__main__":
    sys.exit(main())
