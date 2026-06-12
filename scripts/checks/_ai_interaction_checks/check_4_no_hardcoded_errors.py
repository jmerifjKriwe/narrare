from __future__ import annotations

from pathlib import Path

from ._shared import WEB_DIR, ExcludeRegistry, display_path, rg_files, rg_lines

GATE = "check_4_no_hardcoded_errors"


def check_no_hardcoded_errors(
    registry: ExcludeRegistry,
) -> tuple[list[str], list[str]]:
    passes: list[str] = []
    violations: list[str] = []

    studio_dir = WEB_DIR / "components" / "studio"
    if not studio_dir.exists():
        passes.append("Studio components directory not found -- skip")
        return passes, violations

    files = rg_files(r"(err|error)\.message", "-g", "*.tsx", path=str(studio_dir))
    if not files:
        passes.append("No hardcoded error.message in Studio components +")
        return passes, violations

    for filepath_str in files:
        fp = Path(filepath_str)
        rel = display_path(fp)
        if registry.is_excluded(rel, gate=GATE):
            continue

        lines = rg_lines(r"(err|error)\.message", str(fp))
        detail = ""
        if lines:
            shown: list[str] = []
            for line in lines:
                if len(shown) >= 3:
                    break
                parts = line.split(":", 1)
                if len(parts) == 2:
                    shown.append(f"    L{parts[0]}: {parts[1].strip()[:100]}")
            if shown:
                detail = "\n" + "\n".join(shown)

        violations.append(
            f"{rel} contains hardcoded error.message{detail}\n"
            f"  -> Use state.error.userMessage instead of raw error.message\n"
            f"  -> See ADR-043 section 16.4 for structured error pattern"
        )

    return passes, violations
