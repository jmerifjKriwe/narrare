"""The committed generated views are the facts files and the catalogs, rendered.

`just generate` writes eight views: the Python registry `app/api/main.py`
cross-checks at startup, the locale list the server validates against, the
TypeScript nav data, the TypeScript catalog map, the TypeScript route table,
the TypeScript dock registry, the TypeScript settings registry and the
user-docs index. A stale view means the
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
    scan_settings,
    typescript_catalogs,
    typescript_docks,
    typescript_nav,
    typescript_routes,
    typescript_settings_pages,
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


def test_committed_typescript_settings_pages_match_the_route_sources() -> None:
    assert _committed("web", "lib", "generated", "settingsPages.ts") == typescript_settings_pages(
        ROOT
    ), "web/lib/generated/settingsPages.ts is stale: run `just generate` and commit the result"


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


# The settings convention in miniature, the same shape the dock test builds:
# one host whose settingsRoute path the pages parent under, and one path
# literal per settingsRoutes export. `settingsRoutes` contains
# `settingsRoute` as a substring, so the host detection must read the export
# as a whole word — these fixtures keep that edge in the suite.
def _settings_host(path: str) -> str:
    return (
        f'const settings = createRoute({{ path: "{path}" }});\n'
        "export const settingsRoute = settings;\n"
    )


def _settings_pages(path: str) -> str:
    return f'export const settingsRoutes = [() => createRoute({{ path: "{path}" }})] as const;'


def _routes_repo(tmp_path: Path, sources: dict[str, str]) -> Path:
    """A miniature repo whose route sources are exactly `sources`."""
    for capability, text in sources.items():
        folder = tmp_path / "app" / "capabilities" / capability / "web"
        folder.mkdir(parents=True)
        (folder / "routes.tsx").write_text(text, encoding="utf-8")
    return tmp_path


def test_settings_host_and_contributor_scan_to_one_page_row() -> None:
    scan = scan_settings(
        {"prompts": _settings_pages("prompts"), "settings": _settings_host("/settings")}
    )
    assert [page.id for page in scan.rows] == ["prompts"]
    assert scan.rows[0].path == "/settings/prompts"
    assert scan.rows[0].title_key == "prompts.settingsTitle"
    assert scan.host == "settings"


def test_two_settings_hosts_stop_the_scan_naming_both() -> None:
    # Two hosts would parent one capability's page at two routes at once.
    # Generation stops naming both instead of writing the ambiguous table.
    with pytest.raises(SystemExit, match="export settingsRoute") as failure:
        scan_settings(
            {
                "settings": _settings_host("/settings"),
                "writing": _settings_host("/writing"),
            }
        )
    assert "['settings', 'writing']" in str(failure.value)


def test_settings_pages_without_a_host_stop_the_scan() -> None:
    with pytest.raises(SystemExit, match="settingsRoute to parent them under"):
        scan_settings({"prompts": _settings_pages("prompts")})


def test_unreadable_settings_route_path_stops_the_scan() -> None:
    # The registry derives its rows' paths from the host's path literal; an
    # export the scan cannot read through must stop generation, not emit
    # rows rooted nowhere.
    with pytest.raises(SystemExit, match="settingsRoute must alias"):
        scan_settings({"settings": "export const settingsRoute = settingsRoute;\n"})


def test_settings_pages_with_not_exactly_one_path_stop_the_scan() -> None:
    two = (
        "export const settingsRoutes = [\n"
        '  () => createRoute({ path: "prompts" }),\n'
        '  () => createRoute({ path: "more" }),\n'
        "] as const;"
    )
    with pytest.raises(SystemExit, match="exactly one path literal") as failure:
        scan_settings({"prompts": two, "settings": _settings_host("/settings")})
    assert "found 2" in str(failure.value)


def test_two_settings_pages_at_one_path_stop_the_scan_naming_both_capabilities() -> None:
    scan = scan_settings(
        {
            "chat": _settings_pages("chat"),
            "notes": _settings_pages("notizen"),
            "settings": _settings_host("/settings"),
        }
    )
    assert [page.id for page in scan.rows] == ["chat", "notes"]
    assert scan.host == "settings"

    # The same full path twice is two registry rows behind one route: the
    # hub would list two clusters navigating identically. Generation stops
    # naming every capability at that path instead of writing the duplicate
    # table.
    same = {
        "chat": _settings_pages("chat"),
        "notes": _settings_pages("chat"),
        "settings": _settings_host("/settings"),
    }
    with pytest.raises(SystemExit, match="same path") as failure:
        scan_settings(same)
    assert "['chat', 'notes']" in str(failure.value)


def test_settings_pages_table_renders_the_rows_like_the_dock_registry(
    tmp_path: Path,
) -> None:
    pages = typescript_settings_pages(
        _routes_repo(
            tmp_path,
            {
                "prompts": _settings_pages("prompts"),
                "settings": _settings_host("/settings"),
            },
        )
    )
    assert (
        '  { id: "prompts", path: "/settings/prompts", titleKey: "prompts.settingsTitle" },\n'
        in pages
    )
    assert "export const settingsPages = [\n" in pages
    assert "] as const satisfies ReadonlyArray<{" in pages
    assert "titleKey: keyof typeof en;" in pages


def test_routes_table_wires_settings_factories_after_the_settings_route(
    tmp_path: Path,
) -> None:
    table = typescript_routes(
        _routes_repo(
            tmp_path,
            {
                "prompts": _settings_pages("prompts"),
                "settings": _settings_host("/settings"),
            },
        )
    )
    assert (
        "import { routes as prompts, settingsRoutes as promptsSettings }"
        ' from "../../../app/capabilities/prompts/web/routes";\n' in table
    )
    assert (
        "import { routes as settings, settingsRoute }"
        ' from "../../../app/capabilities/settings/web/routes";\n' in table
    )
    assert (
        "const promptsSettingsRoutes = promptsSettings.map((page) => page(settingsRoute));\n"
        in table
    )
    # The parent precedes the children: the settings capability's own routes
    # sit in the main spread, the factory results after the same
    # parent-before-child note the dock block carries.
    assert table.index("  ...settings,\n") < table.index("  // Settings children come after")
    assert "  ...promptsSettingsRoutes,\n" in table


def test_no_settings_exports_leave_an_empty_registry_and_no_route_block(
    tmp_path: Path,
) -> None:
    # Today's shape: docks and plain routes, no settings export anywhere.
    # The settings view is the empty registry and the composed table carries
    # no settings wiring — the no-contributor output is what the generator
    # wrote before the convention existed, byte for byte.
    sources = {
        "chat": 'export const routes = [createRoute({ path: "/chat" })] as const;\n'
        'export const dockRoutes = [() => createRoute({ path: "chat" })] as const;',
        "writing": "export const routes = [] as const;\n"
        'const workspace = createRoute({ path: "/novels/$id" });\n'
        "export const workspaceRoute = workspace;",
    }
    root = _routes_repo(tmp_path, sources)
    pages = typescript_settings_pages(root)
    assert "export const settingsPages = [] as const satisfies ReadonlyArray<{" in pages
    assert "{ id:" not in pages
    table = typescript_routes(root)
    assert "settings" not in table.lower()
