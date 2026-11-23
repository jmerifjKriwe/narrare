#!/usr/bin/env python3
"""Normalize the V8 LCOV report's SF paths to repo-root-relative form.

Vitest writes ``SF:`` paths relative to ``web/`` (its project root), so
capability components appear as ``../app/capabilities/...`` while web files
appear bare (``components/ChromeFrame.tsx``). SonarCloud's scanner resolves
LCOV paths against the repository root and fails to match the ``../`` form —
every capability-local web file has read 0% coverage since
``coverage.allowExternal`` turned them on, which is why the quality gate's
``new_coverage`` ran far below the project's real coverage.

The rewrite is purely textual and idempotent:

- ``SF:../app/...``    -> ``SF:app/...``    (strip the up-climb)
- ``SF:<bare path>``   -> ``SF:web/<path>`` (web-rooted file)
- ``SF:web/...`` / ``SF:app/...`` already root-relative -> untouched

Used by ``just test-frontend-cov`` so local and CI produce the same report.
"""

from __future__ import annotations

import sys
from pathlib import Path


def normalize(report: str) -> None:
    path = Path(report)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    seen: dict[str, int] = {}
    out: list[str] = []
    for line in lines:
        if not line.startswith("SF:"):
            out.append(line)
            continue
        sf = line[3:].rstrip("\r\n")
        if sf.startswith("../"):
            # Relative to web/: one up-climb lands at the repo root.
            fixed = sf[3:]
        elif sf.startswith(("web/", "app/")):
            fixed = sf
        else:
            fixed = f"web/{sf}"
        seen[fixed] = seen.get(fixed, 0) + 1
        out.append(f"SF:{fixed}\n")
    path.write_text("".join(out), encoding="utf-8")
    dupes = {k: v for k, v in seen.items() if v > 1}
    if dupes:
        # A duplicate SF would double-count a file's hits; the V8 reporter
        # does not emit them, so refusing loudly beats silently skewing.
        raise SystemExit(f"duplicate SF after normalization: {dupes}")
    print(f"normalized {len(seen)} SF paths in {report}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: sonar_lcov.py <lcov-report>")
    normalize(sys.argv[1])
