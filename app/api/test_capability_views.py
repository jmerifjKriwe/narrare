"""The committed generated views are the facts files and the catalogs, rendered.

`just generate` writes seven views: the Python registry `app/api/main.py`
cross-checks at startup, the locale list the server validates against, the
TypeScript nav data, the TypeScript catalog map, the TypeScript route table,
the TypeScript dock registry and the user-docs index. A stale view means the
UI or the startup check runs on old facts — the same failure mode the OpenAPI
drift test guards — so forgetting `just generate` must be a red suite, not a
wrong UI.
"""

import json
from pathlib import Path

import pytest

from scripts.generate_capabilities import (
    Facts,
    catalogs,
    docs_index,
    facts,
    locales,
    python_locales,
    python_registry,
    scan_docks,
    typescript_catalogs,
    typescript_docks,
    typescript_nav,
    typescript_routes,
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


def test_committed_typescript_routes_match_the_route_sources() -> None:
    # The route table and the dock registry are generated from the route
    # sources, not the facts files: a capability that renames an export or
    # repaths a dock changes them, and a committed table that missed the
    # change is a router mounting capabilities that no longer exist as
    # written.
    assert _committed("web", "lib", "generated", "routes.ts") == typescript_routes(ROOT), (
        "web/lib/generated/routes.ts is stale: run `just generate` and commit the result"
    )


def test_committed_typescript_docks_match_the_route_sources() -> None:
    assert _committed("web", "lib", "generated", "docks.ts") == typescript_docks(ROOT), (
        "web/lib/generated/docks.ts is stale: run `just generate` and commit the result"
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


def test_two_docks_at_one_path_stop_the_scan_naming_both_capabilities() -> None:
    # The scan reads the shape of routes.tsx, so the fake sources are that
    # shape in miniature: a host whose workspaceRoute path the docks parent
    # under, and one path literal per dockRoutes export.
    host = (
        'const novel = createRoute({ path: "/novels/$id" });\n'
        "export const workspaceRoute = novel;\n"
    )

    def dock_source(path: str) -> str:
        return f'export const dockRoutes = [() => createRoute({{ path: "{path}" }})] as const;'

    # Distinct paths scan cleanly — both docks become registry rows — so the
    # failing case below fails for the missing guard, not for inputs the
    # scan would not even recognize as docks.
    scan = scan_docks(
        {"chat": dock_source("chat"), "notes": dock_source("notizen"), "writing": host}
    )
    assert [dock.id for dock in scan.docks] == ["chat", "notes"]
    assert scan.host == "writing"

    # The same path twice is two registry rows behind one route: both tabs
    # would navigate identically. Generation stops naming every capability
    # at that path instead of writing the duplicate table.
    same_path = {"chat": dock_source("chat"), "notes": dock_source("chat"), "writing": host}
    with pytest.raises(SystemExit, match="same path") as failure:
        scan_docks(same_path)
    # The assertion matches the capability list the message names. The
    # shared path contains "chat" on its own, so a bare substring check
    # would pass on the path alone and prove nothing about the naming.
    assert "['chat', 'notes']" in str(failure.value)
