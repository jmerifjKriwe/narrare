from __future__ import annotations

from pathlib import Path

from ._shared import WEB_DIR, display_path, is_excluded, rg_files, rg_lines


def check_no_use_connection_lost(
    excludes: set[str],
    fix: bool = False,
) -> tuple[list[str], list[str], list[str]]:
    passes: list[str] = []
    violations: list[str] = []
    fix_applied: list[str] = []

    files = rg_files(r"import.*useConnectionLost", "--type", "ts", path=str(WEB_DIR))
    if not files:
        passes.append("No deprecated useConnectionLost imports +")
        return passes, violations, fix_applied

    for filepath_str in files:
        fp = Path(filepath_str)
        rel = display_path(fp)
        if is_excluded(rel, excludes):
            passes.append(f"[EXCLUDED] {rel} -- excluded from Check 5")
            continue

        lines = rg_lines(r"useConnectionLost", str(fp))
        line_info = ""
        if lines:
            shown: list[str] = []
            for line in lines:
                if len(shown) >= 5:
                    break
                parts = line.split(":", 1)
                if len(parts) == 2:
                    shown.append(f"    L{parts[0]}: {parts[1].strip()[:100]}")
            if shown:
                line_info = "\n" + "\n".join(shown)

        msg = (
            f"{rel} still imports/uses useConnectionLost{line_info}\n"
            f"  -> useAIOperation provides built-in connection state (section 16.3)\n"
            f"  -> Replace with: const {{ isConnectionLost, retry }} = useAIOperation(...)"
        )
        violations.append(msg)
        if fix:
            fix_applied.append(rel)

    return passes, violations, fix_applied
