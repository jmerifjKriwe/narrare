"""The committed generated views are the facts files and the catalogs, rendered.

`just generate` writes five views: the Python registry `app/api/main.py`
cross-checks at startup, the locale list the server validates against, the
TypeScript nav data, the TypeScript catalog map and the user-docs index. A stale
view means the UI or the startup check runs on old facts — the same failure mode
the OpenAPI drift test guards — so forgetting `just generate` must be a red
suite, not a wrong UI.
"""

import json
from pathlib import Path

from scripts.generate_capabilities import (
    Facts,
    catalogs,
    docs_index,
    facts,
    locales,
    python_locales,
    python_registry,
    typescript_catalogs,
    typescript_nav,
)

ROOT = Path(__file__).parents[2]


def _views() -> tuple[tuple[str, ...], dict[str, dict[str, str]], tuple[Facts, ...]]:
    known = locales(ROOT)
    loaded = catalogs(ROOT, known)
    return known, loaded, facts(ROOT, known, loaded)


def _committed(*parts: str) -> str:
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def test_committed_python_registry_matches_the_facts() -> None:
    _, _, loaded_facts = _views()
    assert _committed("app", "generated", "capabilities.py") == python_registry(loaded_facts), (
        "app/generated/capabilities.py is stale: run `just generate` and commit the result"
    )


def test_committed_locale_list_matches_the_catalogs() -> None:
    known, _, _ = _views()
    assert _committed("app", "generated", "locales.py") == python_locales(known), (
        "app/generated/locales.py is stale: run `just generate` and commit the result"
    )


def test_committed_typescript_nav_matches_the_facts() -> None:
    _, _, loaded_facts = _views()
    assert _committed("web", "lib", "generated", "capabilities.ts") == typescript_nav(
        loaded_facts
    ), "web/lib/generated/capabilities.ts is stale: run `just generate` and commit the result"


def test_committed_typescript_catalogs_match_the_catalog_files() -> None:
    # The map and the Locale union are generated from i18n/*.json: a language
    # added without `just generate` would exist on disk and not in the build.
    known, _, _ = _views()
    assert _committed("web", "lib", "generated", "catalogs.ts") == typescript_catalogs(known), (
        "web/lib/generated/catalogs.ts is stale: run `just generate` and commit the result"
    )


def test_committed_docs_index_matches_the_facts() -> None:
    known, loaded, loaded_facts = _views()
    assert _committed("docs", "user", "INDEX.md") == docs_index(loaded_facts, known, loaded), (
        "docs/user/INDEX.md is stale: run `just generate` and commit the result"
    )


def test_every_facts_title_key_exists_in_every_catalog() -> None:
    # facts() raises on a missing key; this test names the rule for the reader:
    # a capability's label is user-visible text, and user-visible text exists
    # in en, de and fr or nowhere.
    known, _, loaded_facts = _views()
    for locale in known:
        catalog = json.loads((ROOT / "i18n" / f"{locale}.json").read_text(encoding="utf-8"))
        for capability in loaded_facts:
            assert capability.title in catalog
