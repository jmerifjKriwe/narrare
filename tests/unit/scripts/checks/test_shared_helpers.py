"""Tests for the shared helpers in ``_ai_interaction_checks._shared``.

Focus: the pure-Python fallback used when the ``rg`` (ripgrep) binary is
unavailable (e.g. some CI runners).  The fallback must produce results
equivalent to the ``rg`` fast-path so that all file-scanning checks keep
working regardless of whether ``rg`` is installed.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from _ai_interaction_checks import _shared

_PATTERN = r'(\|\||\?\?)\s*["\'`]'


def _force_rg_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``rg`` appear unavailable by raising ``FileNotFoundError``.

    This simulates the exact environmental condition (binary not on PATH)
    that triggers the fallback path, without touching the real ``rg``.
    Only ``rg`` invocations are intercepted; every other ``subprocess.run``
    call delegates to the real implementation.
    """
    real_run = _shared.subprocess.run

    def fake_run(cmd: list[str], *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        if cmd and cmd[0] == "rg":
            raise FileNotFoundError(2, "No such file or directory: 'rg'")
        return real_run(cmd, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(_shared.subprocess, "run", fake_run)


# ---------------------------------------------------------------------------
# Fallback behaviour when rg is unavailable
# ---------------------------------------------------------------------------


def test_rg_files_falls_back_when_rg_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With rg unavailable, rg_files still finds matching files and honours
    the include/exclude globs exactly as rg would."""
    (tmp_path / "match.ts").write_text('const x = t("k") || "Hi";\n', encoding="utf-8")
    (tmp_path / "match.tsx").write_text('const y = v ?? "Yo";\n', encoding="utf-8")
    # No content match -> excluded regardless of glob.
    (tmp_path / "plain.ts").write_text("nothing here\n", encoding="utf-8")
    # Excluded by negative globs.
    (tmp_path / "skip.test.ts").write_text('t("k") || "Hi";\n', encoding="utf-8")
    (tmp_path / "skip.spec.tsx").write_text('t("k") || "Hi";\n', encoding="utf-8")
    tests_dir = tmp_path / "__tests__"
    tests_dir.mkdir()
    (tests_dir / "nested.ts").write_text('t("k") || "Hi";\n', encoding="utf-8")
    # Wrong extension (glob include does not match).
    (tmp_path / "ignore.md").write_text('t("k") || "Hi";\n', encoding="utf-8")

    _force_rg_missing(monkeypatch)
    files = _shared.rg_files(
        _PATTERN,
        "-g",
        "*.ts",
        "-g",
        "*.tsx",
        "-g",
        "!*.test.*",
        "-g",
        "!*.spec.*",
        "-g",
        "!__tests__/*",
        path=str(tmp_path),
    )
    names = sorted(Path(f).name for f in files)
    assert names == ["match.ts", "match.tsx"]


def test_rg_files_type_filter_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--type ts`` includes both ``.ts`` and ``.tsx`` and excludes others."""
    (tmp_path / "a.ts").write_text('import { useConnectionLost } from "x";\n', encoding="utf-8")
    (tmp_path / "b.tsx").write_text('import { useConnectionLost } from "x";\n', encoding="utf-8")
    (tmp_path / "c.md").write_text("import useConnectionLost\n", encoding="utf-8")

    _force_rg_missing(monkeypatch)
    files = _shared.rg_files(
        r"import.*useConnectionLost",
        "--type",
        "ts",
        path=str(tmp_path),
    )
    names = sorted(Path(f).name for f in files)
    assert names == ["a.ts", "b.tsx"]


def test_rg_files_fallback_skips_ignored_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fallback must not descend into ignored directories (node_modules,
    .git, build artefacts) — mirroring rg's default gitignore-like behaviour."""
    (tmp_path / "real.ts").write_text('t("k") || "Hi";\n', encoding="utf-8")
    nm = tmp_path / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    (nm / "vendor.ts").write_text('t("k") || "Hi";\n', encoding="utf-8")
    hidden = tmp_path / ".cache"
    hidden.mkdir()
    (hidden / "hid.ts").write_text('t("k") || "Hi";\n', encoding="utf-8")

    _force_rg_missing(monkeypatch)
    files = _shared.rg_files(_PATTERN, "-g", "*.ts", "-g", "*.tsx", path=str(tmp_path))
    names = sorted(Path(f).name for f in files)
    assert names == ["real.ts"]


def test_rg_files_emits_warning_on_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A warning is emitted when the fallback is used, so CI logs reveal it."""
    (tmp_path / "a.ts").write_text('t("k") || "Hi";\n', encoding="utf-8")
    _force_rg_missing(monkeypatch)
    _shared.rg_files(_PATTERN, "-g", "*.ts", path=str(tmp_path))
    out = capsys.readouterr().out.lower()
    assert "rg" in out and "fallback" in out


# ---------------------------------------------------------------------------
# Equivalence: fallback must match the rg fast-path exactly
# ---------------------------------------------------------------------------


_HAS_RG = shutil.which("rg") is not None


@pytest.mark.skipif(not _HAS_RG, reason="requires rg to compare against the fast-path")
def test_rg_files_fallback_matches_rg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The Python fallback must return identical results to real rg."""
    (tmp_path / "a.ts").write_text('t("k") || "Hi";\n', encoding="utf-8")
    (tmp_path / "b.tsx").write_text('v ?? "Yo";\n', encoding="utf-8")
    (tmp_path / "c.test.ts").write_text('t("k") || "Hi";\n', encoding="utf-8")
    (tmp_path / "d.md").write_text('t("k") || "Hi";\n', encoding="utf-8")
    nested = tmp_path / "kb"
    nested.mkdir()
    (nested / "deep.tsx").write_text('x ?? "Deep";\n', encoding="utf-8")

    args = ("-g", "*.ts", "-g", "*.tsx", "-g", "!*.test.*", "-g", "!*.spec.*")
    via_rg = sorted(_shared.rg_files(_PATTERN, *args, path=str(tmp_path)))

    _force_rg_missing(monkeypatch)
    via_fallback = sorted(_shared.rg_files(_PATTERN, *args, path=str(tmp_path)))

    assert via_fallback == via_rg


@pytest.mark.skipif(not _HAS_RG, reason="requires rg to compare against the fast-path")
def test_rg_lines_fallback_matches_rg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """rg_lines must also degrade gracefully and match rg when available."""
    target = tmp_path / "a.ts"
    target.write_text(
        'const a = t("k") || "Hi";\nconst b = "no match";\nconst c = v ?? "Yo";\n',
        encoding="utf-8",
    )
    via_rg = _shared.rg_lines(r"\|\|", str(target))

    _force_rg_missing(monkeypatch)
    via_fallback = _shared.rg_lines(r"\|\|", str(target))

    assert via_fallback == via_rg
    assert len(via_fallback) == 1
