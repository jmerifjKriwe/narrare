from __future__ import annotations

import subprocess  # nosec
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
WEB_DIR = REPO_ROOT / "packages" / "web"
I18N_DIR = REPO_ROOT / "packages" / "i18n" / "messages"


def display_path(path: Path, base: Path = REPO_ROOT) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def load_exclude_list(path: Path) -> set[str]:
    if not path.exists():
        print(f"  [info] No exclude file at {path} — using empty exclude list")
        return set()
    excludes: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            excludes.add(line)
    print(f"  [info] Loaded {len(excludes)} exclude pattern(s) from {path}")
    return excludes


def is_excluded(filepath: str, excludes: set[str]) -> bool:
    return any(excl in filepath or filepath == excl for excl in excludes)


def rg_files(pattern: str, *extra_args: str, path: str | Path = "") -> list[str]:
    cmd = ["rg", "--no-heading", "-l", pattern]
    if extra_args:
        cmd.extend(extra_args)
    if path:
        cmd.append(str(path))
    try:
        result = subprocess.run(  # noqa: S603  # nosec
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired, FileNotFoundError:
        return []
    if result.returncode not in (0, 1):
        return []
    return sorted({line.strip() for line in result.stdout.splitlines() if line.strip()})


def rg_lines(pattern: str, filepath: str | Path) -> list[str]:
    cmd = ["rg", "--no-heading", "-n", pattern, str(filepath)]
    try:
        result = subprocess.run(  # noqa: S603  # nosec
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired, FileNotFoundError:
        return []
    if result.returncode not in (0, 1):
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]
