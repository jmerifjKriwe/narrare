"""The committed capability views are the facts files, rendered.

`just generate` writes three views from `app/capabilities/*/capability.yaml`:
the Python registry `app/api/main.py` cross-checks at startup, the TypeScript
nav data the home page renders, and the user-docs index. A stale view means the
UI or the startup check runs on old facts — the same failure mode the OpenAPI
drift test guards — so forgetting `just generate` must be a red suite, not a
wrong UI.
"""

import json
from pathlib import Path

from scripts.generate_capabilities import docs_index, facts, python_registry, typescript_nav

ROOT = Path(__file__).parents[2]


def test_committed_python_registry_matches_the_facts() -> None:
    committed = (ROOT / "app" / "generated" / "capabilities.py").read_text(encoding="utf-8")
    assert committed == python_registry(facts(ROOT)), (
        "app/generated/capabilities.py is stale: run `just generate` and commit the result"
    )


def test_committed_typescript_nav_matches_the_facts() -> None:
    committed = (ROOT / "web" / "lib" / "generated" / "capabilities.ts").read_text(encoding="utf-8")
    assert committed == typescript_nav(facts(ROOT)), (
        "web/lib/generated/capabilities.ts is stale: run `just generate` and commit the result"
    )


def test_committed_docs_index_matches_the_facts() -> None:
    committed = (ROOT / "docs" / "user" / "INDEX.md").read_text(encoding="utf-8")
    assert committed == docs_index(facts(ROOT), ROOT), (
        "docs/user/INDEX.md is stale: run `just generate` and commit the result"
    )


def test_every_facts_title_key_exists_in_every_catalog() -> None:
    # facts() raises on a missing key; this test names the rule for the reader:
    # a capability's label is user-visible text, and user-visible text exists
    # in en, de and fr or nowhere.
    for locale in ("en", "de", "fr"):
        catalog = json.loads((ROOT / "i18n" / f"{locale}.json").read_text(encoding="utf-8"))
        for capability in facts(ROOT):
            assert capability.title in catalog
