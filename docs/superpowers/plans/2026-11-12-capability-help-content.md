# Capability Help Content — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the container and discovery mechanism for per-capability help content: scan `app/capabilities/*/web/help/`, validate topic files, and generate `web/lib/generated/help.ts` (registry with lazy loaders and locale fallback) plus a coverage report. Prove it end-to-end with one pilot topic.

**Architecture:** Extend `scripts/generate_capabilities.py` with a directory-based help scan (mirroring the optional-export → generated-registry pattern of Docks/Commands), frontmatter validation, and two new generated views (`help.ts`, `help-coverage.md`). Add `scripts/tests/test_generate_help.py` (unittest) for the scan/validation logic. Add one pilot help file under `app/capabilities/writing/web/help/en/` to exercise the full path. No changes to `capability.yaml`, no new required artifacts, no backend, no UI renderer.

**Tech Stack:** Python 3.14 (generator), PyYAML (frontmatter), TypeScript (generated registry), Vite dynamic `?raw` imports (lazy body loading), unittest (script tests).

**Spec:** `docs/superpowers/specs/2026-11-12-capability-help-content-design.md`

## Global Constraints

- One capability is one folder under `app/capabilities/<name>/`; help lives inside it.
- `capability.yaml` is untouched — help is optional and additive (no §8 trigger).
- User-visible text in en/de/fr; `en` is the source language for help.
- English in code, tests, and developer documentation.
- Generated files are committed and drift-checked via `just check-generated`.
- Actions/commands pinned per repo convention; no new third-party deps without approval (PyYAML and `python-frontmatter`-style parsing must use stdlib + existing deps — PyYAML is already a dependency).

## Review Focus

The five input classes / failure modes most likely to bite a person using this software, most likely first:

1. A help directory exists but has no `en/` source-language topic — must fail generation loudly, not emit a registry with a dangling fallback.
2. A topic's `topic` frontmatter disagrees with its filename stem — must fail, otherwise the registry's canonical id drifts from the file on disk.
3. `surfaces` is not a list of strings (e.g. a single string, or numbers) — must fail; the UI's `helpFor(surface)` would otherwise silently never match.
4. A locale directory mirrors only some of a capability's topics — the coverage report must show the gap; the registry must still build and fall back to `en` for missing ones.
5. Generated `help.ts` not regenerated after help files change — `just check-generated` must catch the drift (verified by the pilot + a deliberate stale check).

---

## File Structure

**Created:**
- `scripts/tests/test_generate_help.py` — unittest for scan/validation/coverage logic.
- `web/lib/generated/help.ts` — generated registry (new output).
- `docs/user/help-coverage.md` — generated coverage report (new output).
- `app/capabilities/writing/web/help/en/editor.md` — pilot topic.

**Modified:**
- `scripts/generate_capabilities.py` — add help scan, validation, `typescript_help`, `help_coverage` functions; register outputs in `main()`.

**Not touched:** `capability.yaml`, i18n catalogs, `affected.py`, CI workflows, backend.

---

### Task 1: Help scan + validation (Python)

**Files:**
- Modify: `scripts/generate_capabilities.py` (add `HelpTopic` dataclass, `scan_help` function)
- Create: `scripts/tests/test_generate_help.py`

**Interfaces:**
- Produces: `scan_help(root) -> tuple[HelpScan, ...]` where `HelpScan` holds per-capability, per-topic, per-locale data; raises `SystemExit` on validation failures (consistent with existing functions).

- [ ] **Step 1: Write the failing tests**

Create `scripts/tests/test_generate_help.py`:

```python
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.generate_capabilities import scan_help, HelpScanError


class HelpScanTests(unittest.TestCase):
    def _make(self, files: dict[str, str]) -> Path:
        root = Path(tempfile.mkdtemp())
        base = root / "app" / "capabilities" / "writing" / "web" / "help"
        for rel, body in files.items():
            path = base / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        return root

    def test_empty_help_dir_is_error(self):
        root = self._make({})
        # create the help dir but leave it empty
        (root / "app" / "capabilities" / "writing" / "web" / "help").mkdir(parents=True, exist_ok=True)
        with self.assertRaises(SystemExit):
            scan_help(root)

    def test_missing_source_language_is_error(self):
        root = self._make({"de/editor.md": "---\ntopic: editor\ntitle: Ed\ntitle: x\nsurfaces: []\n---\nbody"})
        # only de, no en
        with self.assertRaises(SystemExit):
            scan_help(root)

    def test_topic_mismatch_is_error(self):
        root = self._make({"en/editor.md": "---\ntopic: other\ntitle: Ed\nsurfaces: []\n---\nbody"})
        with self.assertRaises(SystemExit):
            scan_help(root)

    def test_surfaces_must_be_list_of_strings(self):
        root = self._make({"en/editor.md": "---\ntopic: editor\ntitle: Ed\nsurfaces: editor\n---\nbody"})
        with self.assertRaises(SystemExit):
            scan_help(root)

    def test_valid_minimal_scan(self):
        root = self._make({"en/editor.md": "---\ntopic: editor\ntitle: Ed\nsurfaces: [editor]\n---\nbody"})
        result = scan_help(root)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].capability, "writing")
        self.assertEqual(result[0].topics[0].slug, "editor")
        self.assertEqual(result[0].topics[0].locales, ("en",))

    def test_optional_locale_discovered(self):
        root = self._make({
            "en/editor.md": "---\ntopic: editor\ntitle: Ed\nsurfaces: [editor]\n---\nbody",
            "de/editor.md": "---\ntopic: editor\ntitle: Editor\ntitle: Editor\nsurfaces: [editor]\n---\nbody",
        })
        result = scan_help(root)
        self.assertEqual(sorted(result[0].topics[0].locales), ["de", "en"])

    def test_capability_without_help_dir_absent(self):
        root = Path(tempfile.mkdtemp())
        (root / "app" / "capabilities" / "writing").mkdir(parents=True, exist_ok=True)
        result = scan_help(root)
        self.assertEqual(result, ())


if __name__ == "__main__":
    unittest.main()
```

Note: fix the duplicate `title` lines in the test snippets above before writing — they are copy-paste errors. Write clean versions.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest scripts.tests.test_generate_help -v` (adjust path) — or `cd /home/kiesow/projects/narrare && python -m unittest discover -s scripts/tests`. Expected: FAIL (scan_help not defined).

- [ ] **Step 3: Implement `scan_help` in `scripts/generate_capabilities.py`**

Add after the existing dataclasses:

```python
@dataclass(frozen=True)
class HelpTopicLocale:
    locale: str
    title: str
    body: str  # raw markdown body (without frontmatter)


@dataclass(frozen=True)
class HelpTopic:
    capability: str
    slug: str
    surfaces: tuple[str, ...]
    order: int | None
    locales: tuple[str, ...]  # sorted, en first
    locale_data: tuple[HelpTopicLocale, ...]


@dataclass(frozen=True)
class HelpCapability:
    capability: str
    topics: tuple[HelpTopic, ...]


class HelpScanError(SystemExit):
    pass
```

Implement `scan_help(root)`:
- Iterate `root/app/capabilities/*/web/help/` directories.
- For each capability with a help dir:
  - If dir exists but has no topic files → raise SystemExit ("help present but no source language").
  - Collect locale subdirs. For each locale, collect `*.md` files.
  - Validate locale codes against `locales(root)` (strangers → error).
  - For each topic slug (union of stems across locales):
    - Require `en/<slug>.md` exists (source language).
    - Parse frontmatter (use PyYAML `yaml.safe_load` on the frontmatter block between `---` delimiters).
    - Validate `topic == slug` (frontmatter topic must match filename stem).
    - Validate `title` is a non-empty string.
    - Validate `surfaces` is a list of strings.
    - `order` optional int.
    - Body = everything after the closing `---`.
  - Collect locales present for this slug.
  - Build `HelpTopic`.
- Return tuple of `HelpCapability`, sorted by capability id.

Frontmatter parsing: split on `\n---\n` (first occurrence after leading `---`). Handle `---\n...\n---\n`. Use a small helper; raise SystemExit on malformed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest discover -s scripts/tests`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_capabilities.py scripts/tests/test_generate_help.py
git commit -m "feat(help): add per-capability help scan and validation"
```

---

### Task 2: Generate `web/lib/generated/help.ts`

**Files:**
- Modify: `scripts/generate_capabilities.py` (add `typescript_help` function)
- Modify: `scripts/tests/test_generate_help.py` (add registry output tests)

**Interfaces:**
- Consumes: `scan_help(root)` output.
- Produces: `web/lib/generated/help.ts` string with `HelpGroup`, `HelpTopic`, `helpFor(surface, locale?)`.

- [ ] **Step 1: Write the failing test**

Add to test file:

```python
def test_typescript_help_contains_pilot_topic(self):
    root = self._make({"en/editor.md": "---\ntopic: editor\ntitle: Ed\nsurfaces: [editor]\n---\nbody"})
    # also need i18n for locales() — reuse a minimal setup helper
    ...
```

Note: `locales()` and `catalogs()` require i18n files. The test must create a minimal `i18n/en.json` (and de/fr? no — locales() only needs en present; but catalogs() requires de/fr match). For help.ts generation we only need `scan_help` + locales. Let me make `typescript_help(root)` call `scan_help` and `locales(root)` internally, and the test provides a minimal i18n dir with just en. But catalogs() isn't called by typescript_help. Good — keep typescript_help independent of catalogs.

Test:

```python
def test_typescript_help_contains_topic(self):
    root = self._make({"en/editor.md": "---\ntopic: editor\ntitle: Ed\nsurfaces: [editor]\norder: 5\n---\nbody"})
    (root / "i18n").mkdir(parents=True, exist_ok=True)
    (root / "i18n" / "en.json").write_text("{}", encoding="utf-8")
    out = typescript_help(root)
    self.assertIn("writing.editor", out)
    self.assertIn("helpFor", out)
    self.assertIn("editor.md?raw", out)
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement `typescript_help(root)`**

Generate:

```ts
// Generated by scripts/generate_capabilities.py from
// app/capabilities/*/web/help/ — DO NOT EDIT.
export interface HelpTopic { id: string; capability: string; topic: string; title: string; surfaces: readonly string[]; locale: string; fallback: boolean; load: () => Promise<string>; }

export interface HelpGroup { id: string; capability: string; topic: string; surfaces: readonly string[]; order: number; locales: Record<string, { title: string; load: () => Promise<string> }>; }

export const helpGroups: readonly HelpGroup[] = [ ... ];

export function helpFor(surface: string, locale?: string): HelpTopic[] { ... }
```

Each group lists locale entries with dynamic imports:
```ts
locales: {
  "en": { title: "Ed", load: () => import("../../../app/capabilities/writing/web/help/en/editor.md?raw").then(m => m.default) },
}
```

`helpFor` resolves: for each group whose surfaces includes surface, for the requested locale if present use it (fallback false), else use en (fallback true). Sort by order then slug.

- [ ] **Step 4: Run tests to verify they pass**

- [ ] **Step 5: Commit**

---

### Task 3: Generate coverage report

**Files:**
- Modify: `scripts/generate_capabilities.py` (add `help_coverage(root, known_locales)` function)
- Modify: `scripts/tests/test_generate_help.py` (add test)

**Interfaces:**
- Produces: `docs/user/help-coverage.md` string.

- [ ] **Step 1: Write the failing test**

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement `help_coverage(root)`**

Markdown:

```markdown
<!-- Generated by scripts/generate_capabilities.py — DO NOT EDIT. -->
# Help coverage

One row per capability that ships help; capabilities without help are listed at the bottom.

## writing

| Topic | en | de | fr |
| --- | --- | --- | --- |
| editor | ✓ | — | — |

## Capabilities without help

- chat
- knowledge
- ...
```

- [ ] **Step 4: Run tests to verify they pass**

- [ ] **Step 5: Commit**

---

### Task 4: Wire into `main()` and verify drift check

**Files:**
- Modify: `scripts/generate_capabilities.py` (`main()` outputs dict)

- [ ] **Step 1: Add outputs**

```python
"web/lib/generated/help.ts": typescript_help(root),
"docs/user/help-coverage.md": help_coverage(root),
```

- [ ] **Step 2: Run `just generate`**

Expected: writes the two new files; no errors.

- [ ] **Step 3: Run `just check-generated`**

Expected: PASS (committed files match regenerated).

- [ ] **Step 4: Commit generated files**

```bash
git add web/lib/generated/help.ts docs/user/help-coverage.md scripts/generate_capabilities.py
git commit -m "feat(help): generate help registry and coverage report"
```

---

### Task 5: Pilot help content in `writing` capability

**Files:**
- Create: `app/capabilities/writing/web/help/en/editor.md`

- [ ] **Step 1: Create the pilot topic**

```markdown
---
topic: editor
title: The Writing Editor
surfaces: [editor]
order: 10
---

## The Writing Editor

Narrare's editor is built around one principle: your writing comes first.

**Autosave.** Your work is saved automatically; the interval is configurable in Settings (default 30 seconds). A small indicator shows save status.

**Chapter navigation.** The left rail lists chapters in order; click to switch, drag to reorder.

**Word count.** Live word count and estimated reading time sit at the bottom of the editor.

**Keyboard shortcuts.** `Cmd/Ctrl+S` force save, `Cmd/Ctrl+K` command palette, `Cmd/Ctrl+\` toggle sidebars, `Cmd/Ctrl+Shift+F` focus mode.
```

- [ ] **Step 2: Regenerate and verify**

Run: `just generate`. Expected: help.ts now contains `writing.editor`; coverage shows writing/editor with en ✓.

- [ ] **Step 3: Run `just check-generated`**

Expected: PASS.

- [ ] **Step 4: Run `pnpm --dir web typecheck`**

Expected: PASS — generated help.ts type-checks (lazy import paths resolve).

- [ ] **Step 5: Commit**

```bash
git add app/capabilities/writing/web/help/ web/lib/generated/help.ts docs/user/help-coverage.md
git commit -m "feat(help): pilot help topic for the writing editor"
```

---

### Task 6: Drift check verification (deliberate stale)

**Files:** none (verification only)

- [ ] **Step 1: Temporarily edit the pilot topic body**

Append a line to `app/capabilities/writing/web/help/en/editor.md`.

- [ ] **Step 2: Run `just check-generated` without regenerating**

Expected: FAIL (drift detected) — confirms the check catches stale help.

- [ ] **Step 3: Revert the edit and regenerate**

```bash
git checkout -- app/capabilities/writing/web/help/en/editor.md
just generate
```

Expected: clean working tree (no diff) after regeneration.

---

## Self-review checklist (run before handoff)

1. **Spec coverage:** scan + validation (Task 1), help.ts generation (Task 2), coverage report (Task 3), main() wiring (Task 4), pilot (Task 5), drift check (Task 6). All spec sections covered. ✓
2. **Step scan:** each step is one action with a checkable result. ✓
3. **Type consistency:** `HelpTopic`, `HelpGroup`, `helpFor` names used consistently across Task 2 tests and implementation. ✓
4. **Review Focus:** all five items have corresponding tests (missing source lang → Task 1 test; topic mismatch → Task 1 test; surfaces type → Task 1 test; partial locale → Task 1 + Task 3; drift → Task 6). ✓
5. **Proportion:** plan is longer than the spec, but most length is test code and generated-output shape; implementation steps are signatures + one-line approaches. Acceptable. ✓