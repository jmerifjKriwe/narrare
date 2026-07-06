"""Tests for scripts/check_frontend_file_size.py — core logic.

Covers file category detection (_limit_for), including the AUFG-03-04
hook-export detection for files named without the ``use`` prefix.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.check_frontend_file_size import (  # noqa: E402
    FileSizeViolation,
    _exports_hook,
    _limit_for,
)

# ---------------------------------------------------------------------------
# _limit_for — filename-based classification
# ---------------------------------------------------------------------------


class TestLimitForByFilename:
    def test_page_tsx_gets_100(self, tmp_path: Path) -> None:
        assert _limit_for(tmp_path / "page.tsx") == ("page", 100)

    def test_component_tsx_gets_200(self, tmp_path: Path) -> None:
        assert _limit_for(tmp_path / "Foo.tsx") == ("component", 200)

    def test_use_prefix_ts_gets_hook_150(self, tmp_path: Path) -> None:
        assert _limit_for(tmp_path / "useContinueStream.ts") == ("hook", 150)

    def test_store_suffix_ts_gets_store_150(self, tmp_path: Path) -> None:
        assert _limit_for(tmp_path / "editorStore.ts") == ("store", 150)

    def test_plain_ts_gets_typescript_400(self, tmp_path: Path) -> None:
        assert _limit_for(tmp_path / "utils.ts") == ("typescript", 400)


# ---------------------------------------------------------------------------
# _limit_for — AUFG-03-04 hook-export detection (content-aware)
# ---------------------------------------------------------------------------


class TestLimitForHookExportDetection:
    """A `.ts` file exporting `useXxx` is a hook regardless of filename."""

    def test_controller_exporting_hook_classified_as_hook(self, tmp_path: Path) -> None:
        content = (
            "import { useState } from 'react';\n\n"
            "export function useTipTapEditorController() {\n"
            "  return useState(0);\n}\n"
        )
        assert _limit_for(tmp_path / "TipTapEditorController.ts", content) == ("hook", 150)

    def test_async_hook_export_detected(self, tmp_path: Path) -> None:
        content = "export async function useFetchData() {\n  return null;\n}\n"
        assert _limit_for(tmp_path / "data-loader.ts", content) == ("hook", 150)

    def test_const_arrow_hook_detected(self, tmp_path: Path) -> None:
        content = "export const useFoo = () => null;\n"
        assert _limit_for(tmp_path / "bar.ts", content) == ("hook", 150)

    def test_lowercase_hook_name_not_matched(self, tmp_path: Path) -> None:
        # `usefoo` (lowercase) is not a hook per React convention.
        content = "export function usefoo() { return null; }\n"
        assert _limit_for(tmp_path / "weird.ts", content) == ("typescript", 400)

    def test_non_exported_function_not_matched(self, tmp_path: Path) -> None:
        # An internal helper called `useFoo` (not exported) doesn't make
        # the file a hook module.
        content = "function useFooInternal() { return null; }\nexport const helper = () => null;\n"
        assert _limit_for(tmp_path / "bar.ts", content) == ("typescript", 400)

    def test_plain_ts_without_hook_export_still_typescript(self, tmp_path: Path) -> None:
        content = "export const helper = () => null;\nexport function compute() { return 42; }\n"
        assert _limit_for(tmp_path / "utils.ts", content) == ("typescript", 400)

    def test_filename_prefix_still_works_without_content(self, tmp_path: Path) -> None:
        # The pre-AUFG-03-04 filename rule must still work when content
        # is not provided — preserves backward compatibility.
        assert _limit_for(tmp_path / "useFoo.ts") == ("hook", 150)


# ---------------------------------------------------------------------------
# _exports_hook
# ---------------------------------------------------------------------------


class TestExportsHook:
    def test_detects_export_function(self) -> None:
        assert _exports_hook(Path("dummy"), "export function useFoo() {}")

    def test_detects_export_async_function(self) -> None:
        assert _exports_hook(Path("dummy"), "export async function useFoo() {}")

    def test_detects_export_const(self) -> None:
        assert _exports_hook(Path("dummy"), "export const useFoo = () => {};")

    def test_rejects_non_exported(self) -> None:
        assert not _exports_hook(Path("dummy"), "function useFoo() {}")

    def test_rejects_lowercase(self) -> None:
        assert not _exports_hook(Path("dummy"), "export function usefoo() {}")

    def test_rejects_uppercase_after_use(self) -> None:
        # `usefoo` lowercase is rejected; `useFoo` matches.
        assert _exports_hook(Path("dummy"), "export function useFoo() {}")
        assert not _exports_hook(Path("dummy"), "export function use() {}")


# ---------------------------------------------------------------------------
# FileSizeViolation fingerprint
# ---------------------------------------------------------------------------


class TestFingerprint:
    def test_stable_fingerprint(self, tmp_path: Path) -> None:
        v1 = FileSizeViolation(path=tmp_path / "foo.ts", lines=200, limit=150, kind="hook")
        v2 = FileSizeViolation(path=tmp_path / "foo.ts", lines=180, limit=150, kind="hook")
        # Same path + kind + limit → same fingerprint (debt can shrink).
        assert v1.fingerprint() == v2.fingerprint()

    def test_different_kind_different_fingerprint(self, tmp_path: Path) -> None:
        v1 = FileSizeViolation(path=tmp_path / "foo.ts", lines=200, limit=150, kind="hook")
        v2 = FileSizeViolation(path=tmp_path / "foo.ts", lines=200, limit=400, kind="typescript")
        assert v1.fingerprint() != v2.fingerprint()
