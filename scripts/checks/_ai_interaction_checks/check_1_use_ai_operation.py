from __future__ import annotations

import re
import subprocess  # nosec
from pathlib import Path

from ._shared import WEB_DIR, display_path, is_excluded

SSE_API_MODULES = [
    "generation",
    "generation-streams",
    "streaming",
    "coauthor",
    "chat",
    "kb-sessions",
    "timeline",
]


def _find_sse_api_importing_tsx_files() -> list[Path]:
    """Find TSX files that import values (not just types) from SSE API modules."""
    modules = "|".join(re.escape(m) for m in SSE_API_MODULES)
    pattern = rf'from\s+["\'](?:@/)?lib/api/(?:{modules})["\']'
    found_paths: set[Path] = set()
    try:
        proc = subprocess.run(  # noqa: S603  # nosec
            ["rg", "-g", "*.tsx", "-l", "-n", "--no-heading", pattern, str(WEB_DIR / "components")],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0:
            for raw in proc.stdout.splitlines():
                raw = raw.strip()
                if not raw:
                    continue
                fp = Path(raw.split(":")[0])
                found_paths.add(fp)
    except subprocess.TimeoutExpired, FileNotFoundError:
        pass

    matched: list[Path] = []
    for fp in sorted(found_paths):
        try:
            content = fp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in content.splitlines():
            stripped = line.strip()
            if re.match(r"^import\s+type\b", stripped):
                continue
            if re.search(r'from\s+["\'](?:@/)?lib/api/(?:' + modules + r')["\']', stripped):
                matched.append(fp)
                break
    return matched


def _file_imports_use_ai_operation(filepath: Path) -> bool:
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
        return "useAIOperation" in content
    except OSError:
        return False


def check_use_ai_operation_usage(excludes: set[str]) -> tuple[list[str], list[str]]:
    passes: list[str] = []
    violations: list[str] = []

    importing_files = _find_sse_api_importing_tsx_files()

    if not importing_files:
        passes.append("No TSX files import SSE API values — check not applicable")
        return passes, violations

    for filepath in importing_files:
        rel = display_path(filepath)
        if is_excluded(rel, excludes):
            passes.append(f"[EXCLUDED] {rel} — excluded from Check 1")
            continue
        if _file_imports_use_ai_operation(filepath):
            passes.append(f"{rel} uses useAIOperation +")
        else:
            violations.append(
                f"{rel} imports SSE API values but does NOT import useAIOperation\n"
                f'  -> Add: import {{ useAIOperation }} from "@/lib/hooks/use-ai-operation"\n'
                f"  -> Or add to exclude list if migration is in progress"
            )

    return passes, violations
