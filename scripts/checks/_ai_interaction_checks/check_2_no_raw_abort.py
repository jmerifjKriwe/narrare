from __future__ import annotations

from pathlib import Path

from ._shared import WEB_DIR, display_path, is_excluded, rg_files


def check_no_raw_abort_controller(excludes: set[str]) -> tuple[list[str], list[str]]:
    passes: list[str] = []
    violations: list[str] = []

    studio_dir = WEB_DIR / "components" / "studio"
    if not studio_dir.exists():
        passes.append("Studio components directory not found -- skip")
        return passes, violations

    files = rg_files(r"new AbortController", "-g", "*.tsx", path=str(studio_dir))
    if not files:
        passes.append("No raw AbortController in Studio components +")
        return passes, violations

    for filepath_str in files:
        fp = Path(filepath_str)
        rel = display_path(fp)
        if is_excluded(rel, excludes):
            passes.append(f"[EXCLUDED] {rel} -- excluded from Check 2")
            continue
        violations.append(
            f"{rel} contains raw 'new AbortController()'\n"
            f"  -> Use useAIOperation or the AIOperationStateMachine instead"
        )

    return passes, violations
