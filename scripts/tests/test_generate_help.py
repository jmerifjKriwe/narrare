"""Tests for the help scan in scripts/generate_capabilities.py.

The scan is the generator's only read of ``app/capabilities/*/web/help/``,
so every rule it enforces is pinned here: a help directory must carry the
source language, every topic file's frontmatter must parse and agree with
its filename, and every locale directory must be a locale the central
catalog carries.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.generate_capabilities import HelpScanError, scan_help


class HelpScanTests(unittest.TestCase):
    """One help directory under app/capabilities/writing, one root per test."""

    def _make(self, files: dict[str, str]) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        # locales(root) resolves from the central files' names; the scan
        # never reads their contents.
        i18n = root / "i18n"
        i18n.mkdir()
        for locale in ("en", "de", "fr"):
            (i18n / f"{locale}.json").write_text("{}", encoding="utf-8")
        base = root / "app" / "capabilities" / "writing" / "web" / "help"
        for rel, body in files.items():
            path = base / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        return root

    def test_help_scan_error_is_system_exit(self):
        # `just generate` stops plainly on a help validation failure: what
        # the scan raises must travel as SystemExit and name its own type.
        root = self._make({})
        (root / "app" / "capabilities" / "writing" / "web" / "help").mkdir(parents=True)
        with self.assertRaises(SystemExit) as raised:
            scan_help(root)
        self.assertIsInstance(raised.exception, HelpScanError)

    def test_empty_help_dir_is_error(self):
        root = self._make({})
        # create the help dir but leave it empty
        (root / "app" / "capabilities" / "writing" / "web" / "help").mkdir(parents=True)
        with self.assertRaises(HelpScanError):
            scan_help(root)

    def test_missing_source_language_is_error(self):
        root = self._make(
            {"de/editor.md": "---\ntopic: editor\ntitle: Editor\nsurfaces: [editor]\n---\nbody"}
        )
        # only de, no en
        with self.assertRaises(HelpScanError):
            scan_help(root)

    def test_topic_mismatch_is_error(self):
        root = self._make({"en/editor.md": "---\ntopic: other\ntitle: Ed\nsurfaces: []\n---\nbody"})
        with self.assertRaises(HelpScanError):
            scan_help(root)

    def test_surfaces_must_be_list_of_strings(self):
        for frontmatter in (
            "---\ntopic: editor\ntitle: Ed\nsurfaces: editor\n---\nbody",  # a bare string
            "---\ntopic: editor\ntitle: Ed\nsurfaces: [editor, 3]\n---\nbody",  # a non-string entry
        ):
            with self.subTest(frontmatter=frontmatter):
                root = self._make({"en/editor.md": frontmatter})
                with self.assertRaises(HelpScanError):
                    scan_help(root)

    def test_surfaces_may_be_empty(self):
        root = self._make(
            {"en/editor.md": "---\ntopic: editor\ntitle: Ed\nsurfaces: []\n---\nbody"}
        )
        result = scan_help(root)
        self.assertEqual(result[0].topics[0].surfaces, ())

    def test_title_must_be_non_empty_string(self):
        for frontmatter in (
            "---\ntopic: editor\nsurfaces: []\n---\nbody",  # title missing
            '---\ntopic: editor\ntitle: ""\nsurfaces: []\n---\nbody',  # title empty
        ):
            with self.subTest(frontmatter=frontmatter):
                root = self._make({"en/editor.md": frontmatter})
                with self.assertRaises(HelpScanError):
                    scan_help(root)

    def test_order_must_be_int(self):
        root = self._make(
            {"en/editor.md": "---\ntopic: editor\ntitle: Ed\nsurfaces: []\norder: ten\n---\nbody"}
        )
        with self.assertRaises(HelpScanError):
            scan_help(root)

    def test_stranger_locale_is_error(self):
        root = self._make(
            {"es/editor.md": "---\ntopic: editor\ntitle: Ed\nsurfaces: []\n---\nbody"}
        )
        with self.assertRaises(HelpScanError):
            scan_help(root)

    def test_malformed_frontmatter_is_error(self):
        root = self._make({"en/editor.md": "## Ed\n\nno frontmatter block"})
        with self.assertRaises(HelpScanError):
            scan_help(root)

    def test_valid_minimal_scan(self):
        root = self._make(
            {"en/editor.md": "---\ntopic: editor\ntitle: Ed\nsurfaces: [editor]\n---\nbody"}
        )
        result = scan_help(root)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].capability, "writing")
        self.assertEqual(result[0].topics[0].slug, "editor")
        self.assertEqual(result[0].topics[0].locales, ("en",))
        self.assertEqual(result[0].topics[0].surfaces, ("editor",))
        self.assertIsNone(result[0].topics[0].order)
        self.assertEqual(result[0].topics[0].locale_data[0].title, "Ed")
        self.assertEqual(result[0].topics[0].locale_data[0].body, "body")

    def test_optional_locale_discovered(self):
        root = self._make(
            {
                "en/editor.md": "---\ntopic: editor\ntitle: Ed\nsurfaces: [editor]\n---\nbody",
                "de/editor.md": "---\ntopic: editor\ntitle: Editor\nsurfaces: [editor]\n---\nbody",
            }
        )
        result = scan_help(root)
        self.assertEqual(sorted(result[0].topics[0].locales), ["de", "en"])
        # en, the source language, leads the tuple
        self.assertEqual(result[0].topics[0].locales, ("en", "de"))
        self.assertEqual(result[0].topics[0].locale_data[1].title, "Editor")

    def test_optional_order_discovered(self):
        root = self._make(
            {
                "en/editor.md": (
                    "---\ntopic: editor\ntitle: Ed\nsurfaces: [editor]\norder: 10\n---\nbody"
                )
            }
        )
        result = scan_help(root)
        self.assertEqual(result[0].topics[0].order, 10)

    def test_capability_without_help_dir_absent(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "app" / "capabilities" / "writing").mkdir(parents=True)
        self.assertEqual(scan_help(root), ())


if __name__ == "__main__":
    unittest.main()
