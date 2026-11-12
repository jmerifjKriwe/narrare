"""Tests for the help scan and registry view in scripts/generate_capabilities.py.

The scan is the generator's only read of ``app/capabilities/*/web/help/``,
so every rule it enforces is pinned here: a help directory must carry the
source language, every topic file's frontmatter must parse and agree with
its filename, and every locale directory must be a locale the central
catalog carries. The registry tests pin what ``typescript_help`` emits for
a scanned tree: canonical ids, per-locale lazy ``?raw`` loads, escaped
titles, and the default sort order. The coverage tests pin what
``help_coverage`` emits: the per-topic locale matrix, the alphabetical
capability sections, and the list of capabilities that ship no help.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.generate_capabilities import HelpScanError, help_coverage, scan_help, typescript_help


class HelpRootTestCase(unittest.TestCase):
    """One throwaway root per test: central i18n files plus a writing help tree."""

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


class HelpScanTests(HelpRootTestCase):
    """One help directory under app/capabilities/writing, one root per test."""

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


class TypescriptHelpTests(HelpRootTestCase):
    """The registry view: what typescript_help emits for a scanned help tree."""

    def test_typescript_help_contains_topic(self):
        root = self._make(
            {
                "en/editor.md": (
                    "---\ntopic: editor\ntitle: Ed\nsurfaces: [editor]\norder: 5\n---\nbody"
                )
            }
        )
        out = typescript_help(root)
        self.assertIn("writing.editor", out)
        self.assertIn("helpFor", out)
        self.assertIn("editor.md?raw", out)
        self.assertIn('surfaces: ["editor"]', out)

    def test_typescript_help_lists_every_locale_with_its_title(self):
        root = self._make(
            {
                "en/editor.md": "---\ntopic: editor\ntitle: Ed\nsurfaces: [editor]\n---\nbody",
                "de/editor.md": "---\ntopic: editor\ntitle: Editor\nsurfaces: [editor]\n---\nbody",
            }
        )
        out = typescript_help(root)
        self.assertIn('"de": { title: "Editor"', out)
        self.assertIn("help/en/editor.md?raw", out)
        self.assertIn("help/de/editor.md?raw", out)

    def test_typescript_help_escapes_quotes_and_backslashes_in_titles(self):
        root = self._make(
            {
                "en/editor.md": (
                    '---\ntopic: editor\ntitle: "The \\"Ed\\" \\\\ editor"\n'
                    "surfaces: [editor]\n---\nbody"
                )
            }
        )
        out = typescript_help(root)
        self.assertIn(r'title: "The \"Ed\" \\ editor"', out)

    def test_typescript_help_order_defaults_to_1000(self):
        root = self._make(
            {
                "en/ordered.md": (
                    "---\ntopic: ordered\ntitle: Or\nsurfaces: [s]\norder: 5\n---\nbody"
                ),
                "en/plain.md": "---\ntopic: plain\ntitle: Pl\nsurfaces: [s]\n---\nbody",
            }
        )
        out = typescript_help(root)
        self.assertIn("order: 5,", out)
        self.assertIn("order: 1000,", out)

    def test_typescript_help_without_help_renders_empty_registry(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "app" / "capabilities" / "writing").mkdir(parents=True)
        out = typescript_help(root)
        self.assertIn("export const helpGroups: readonly HelpGroup[] = [];", out)


class HelpCoverageTests(HelpRootTestCase):
    """The coverage report: what help_coverage emits for a capability tree."""

    def _capability(self, root: Path, name: str) -> None:
        """One capability folder with just the capability.yaml that names it."""
        folder = root / "app" / "capabilities" / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "capability.yaml").write_text(f"id: {name}\n", encoding="utf-8")

    def _topic(self, root: Path, capability: str, locale: str, slug: str) -> None:
        """One valid help topic file under a capability's help tree."""
        directory = root / "app" / "capabilities" / capability / "web" / "help" / locale
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{slug}.md").write_text(
            f"---\ntopic: {slug}\ntitle: {slug}\nsurfaces: [editor]\n---\nbody",
            encoding="utf-8",
        )

    def test_coverage_matches_the_briefs_shape(self):
        root = self._make(
            {"en/editor.md": "---\ntopic: editor\ntitle: Ed\nsurfaces: [editor]\n---\nbody"}
        )
        self._capability(root, "writing")
        self._capability(root, "chat")
        self.assertEqual(
            help_coverage(root),
            "<!-- Generated by scripts/generate_capabilities.py from"
            " app/capabilities/*/web/help/ — DO NOT EDIT. -->\n"
            "<!-- A — marks a translation the topic does not carry yet."
            " Regenerate with `just generate`. -->\n"
            "\n"
            "# Help coverage\n"
            "\n"
            "One row per capability that ships help; capabilities without help"
            " are listed at the bottom.\n"
            "\n"
            "## writing\n"
            "\n"
            "| Topic | en | de | fr |\n"
            "| --- | --- | --- | --- |\n"
            "| editor | ✓ | — | — |\n"
            "\n"
            "## Capabilities without help\n"
            "\n"
            "- chat\n",
        )

    def test_coverage_marks_present_translations(self):
        root = self._make({})
        for locale in ("en", "de", "fr"):
            self._topic(root, "writing", locale, "editor")
        self._capability(root, "writing")
        out = help_coverage(root)
        self.assertIn("| editor | ✓ | ✓ | ✓ |", out)
        # Every capability ships help: the missing list has nothing to list.
        self.assertNotIn("## Capabilities without help", out)

    def test_coverage_orders_capabilities_and_topics_alphabetically(self):
        root = self._make({})
        self._topic(root, "writing", "en", "focus-mode")
        self._topic(root, "writing", "en", "editor")
        self._topic(root, "chat", "en", "dashboard")
        self._capability(root, "writing")
        self._capability(root, "chat")
        out = help_coverage(root)
        self.assertLess(out.index("## chat"), out.index("## writing"))
        self.assertLess(out.index("| editor |"), out.index("| focus-mode |"))

    def test_coverage_without_any_help_lists_every_capability(self):
        root = self._make({})
        self._capability(root, "writing")
        self._capability(root, "chat")
        out = help_coverage(root)
        self.assertNotIn("## writing", out)
        self.assertIn("## Capabilities without help\n\n- chat\n- writing\n", out)

    def test_coverage_ignores_folders_without_capability_yaml(self):
        root = self._make(
            {"en/editor.md": "---\ntopic: editor\ntitle: Ed\nsurfaces: [editor]\n---\nbody"}
        )
        self._capability(root, "writing")
        self._capability(root, "chat")
        (root / "app" / "capabilities" / "stray").mkdir()
        out = help_coverage(root)
        self.assertNotIn("stray", out)
        self.assertIn("- chat\n", out)


if __name__ == "__main__":
    unittest.main()
