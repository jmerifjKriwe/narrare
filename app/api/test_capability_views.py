"""The committed generated views are the facts files and the catalogs, rendered.

`just generate` writes eleven views: the Python registry `app/api/main.py`
cross-checks at startup, the locale list the server validates against, the
TypeScript nav data, the TypeScript catalog map, the TypeScript overlay map,
the TypeScript route table, the TypeScript workspace-route id, the TypeScript
dock registry, the TypeScript settings registry, the TypeScript command
registry and the user-docs index.
A stale view means the
UI or the startup check runs on old facts — the same failure mode the OpenAPI
drift test guards — so forgetting `just generate` must be a red suite, not a
wrong UI.
"""

import json
from pathlib import Path

import pytest

from scripts.generate_capabilities import (
    REQUIRED_DOC_KEYS,
    SOURCE_LOCALE,
    Facts,
    catalogs,
    docs_index,
    facts,
    locales,
    overlay_sources,
    python_locales,
    python_registry,
    registry_locales,
    scan_commands,
    scan_docks,
    scan_settings,
    typescript_catalogs,
    typescript_commands,
    typescript_docks,
    typescript_error_codes,
    typescript_nav,
    typescript_overlays,
    typescript_routes,
    typescript_settings_pages,
    typescript_workspace,
    ui_facts,
    web_ids,
    workspace_route_id,
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
        ui_facts(loaded_facts, ROOT)
    ), "web/lib/generated/capabilities.ts is stale: run `just generate` and commit the result"


def test_committed_typescript_catalogs_match_the_catalog_files() -> None:
    # The map and the Locale union are generated from i18n/*.json: a language
    # added without `just generate` would exist on disk and not in the build.
    known, _, _ = _views()
    committed = _committed("web", "lib", "generated", "catalogs.ts")
    assert committed == typescript_catalogs(ROOT, known, registry_locales(ROOT)), (
        "web/lib/generated/catalogs.ts is stale: run `just generate` and commit the result"
    )
    assert "export const localeOrder = [" in committed


def test_committed_typescript_overlays_match_the_overlay_files() -> None:
    known, loaded, _ = _views()
    overlays = overlay_sources(ROOT, known, loaded)
    assert _committed("web", "lib", "generated", "overlays.ts") == typescript_overlays(
        known, overlays
    ), "web/lib/generated/overlays.ts is stale: run `just generate` and commit the result"


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


def test_committed_typescript_commands_match_the_command_modules() -> None:
    # The command registry is generated from the command modules' presence,
    # not the route sources: a capability that adds, renames or removes a
    # commands file changes it, and a committed registry that missed the
    # change is a palette running on rows that no longer exist as written.
    assert _committed("web", "lib", "generated", "commands.ts") == typescript_commands(ROOT), (
        "web/lib/generated/commands.ts is stale: run `just generate` and commit the result"
    )


def test_committed_typescript_error_codes_match_the_kernel() -> None:
    assert _committed("web", "lib", "generated", "errorCodes.ts") == typescript_error_codes(), (
        "web/lib/generated/errorCodes.ts is stale: run `just generate` and commit the result"
    )


def test_committed_docs_index_matches_the_facts() -> None:
    known, loaded, loaded_facts = _views()
    assert _committed("docs", "user", "INDEX.md") == docs_index(
        loaded_facts, known, loaded, ROOT
    ), "docs/user/INDEX.md is stale: run `just generate` and commit the result"


def test_ui_rows_are_exactly_the_web_owning_capabilities() -> None:
    # The one rule ui_facts carries, named for the reader: a capability
    # without a web/ directory contributes no nav or INDEX row — its facts
    # stay in the backend registry, which still carries every capability.
    # The title every row renders is facts()'s guarantee: a web-owning
    # capability whose key resolves nowhere stops generation instead of
    # losing its row quietly.
    _, loaded, loaded_facts = _views()
    rows = ui_facts(loaded_facts, ROOT)
    assert {row.id for row in rows} == set(web_ids(ROOT))
    for capability in rows:
        assert capability.title is not None
        assert capability.title in loaded[SOURCE_LOCALE]


def _facts_tree(
    tmp_path: Path,
    *,
    title: str | None,
    owns_web: bool,
    fields: str = "path: /demo\nneeds: []\nnav: true",
    catalog_keys: tuple[str, ...] = (),
) -> Path:
    """A miniature repo: one capability, one locale, the facts' title as given.

    `fields` is the yaml below the id and title, so a test can leave a field
    out; `catalog_keys` are extra words the locale already resolves, for a
    web-owning capability whose title must. A `None` title writes no title
    line at all — the shape a capability without ``web/`` may use.
    """
    catalog = {key: key for key in REQUIRED_DOC_KEYS + catalog_keys}
    (tmp_path / "i18n").mkdir()
    (tmp_path / "i18n" / "en.json").write_text(
        json.dumps(dict(sorted(catalog.items()))), encoding="utf-8"
    )
    registry = tmp_path / "i18n" / "registry" / "locales.json"
    registry.parent.mkdir()
    registry.write_text(json.dumps({"locales": ["en"]}) + "\n", encoding="utf-8")
    folder = tmp_path / "app" / "capabilities" / "demo"
    folder.mkdir(parents=True)
    lines = ["id: demo"]
    if title is not None:
        lines.append(f"title: {title}")
    lines.append(fields)
    (folder / "capability.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if owns_web:
        (folder / "web").mkdir()
    return tmp_path


def test_a_web_owning_capability_with_a_typoed_title_stops_generation(tmp_path: Path) -> None:
    # The pre-W0 raise, restored for the capabilities that render rows: a
    # title key the merged catalog does not resolve is a typo, and it stops
    # generation naming the file and the key — not a row quietly dropped
    # from the nav and the INDEX while the keyof check sees nothing.
    root = _facts_tree(tmp_path, title="demo.typo", owns_web=True)
    known = locales(root)
    loaded = catalogs(root, known)
    with pytest.raises(SystemExit, match=r"title key 'demo\.typo' missing"):
        facts(root, known, loaded)


def test_a_web_owning_capability_without_a_title_stops_generation(tmp_path: Path) -> None:
    # A capability that owns web/ renders a nav row and an INDEX row, both
    # keyed by its title; no key means no words, so generation stops naming
    # the file instead of writing a row that renders blank.
    root = _facts_tree(tmp_path, title=None, owns_web=True)
    known = locales(root)
    loaded = catalogs(root, known)
    with pytest.raises(SystemExit, match="must declare a title key"):
        facts(root, known, loaded)


def test_a_web_less_capability_needs_only_its_id_and_needs(tmp_path: Path) -> None:
    # No UI row reads a title for a capability without web/, so the field is
    # absent rather than validated: chat's shape, and the registry keeps it.
    root = _facts_tree(tmp_path, title=None, owns_web=False, fields="needs: []")
    known = locales(root)
    loaded = catalogs(root, known)
    entries = facts(root, known, loaded)
    assert [(entry.id, entry.title, entry.path, entry.nav) for entry in entries] == [
        ("demo", None, None, False)
    ]
    assert ui_facts(entries, root) == ()


def test_a_capability_without_web_keeps_facts_the_catalog_does_not_resolve(
    tmp_path: Path,
) -> None:
    # The registry reads every capability, web/ or not: a capability whose
    # UI is gone keeps its facts — its catalog left with the web/
    # directory, and only the UI rows need the title.
    root = _facts_tree(tmp_path, title="demo.gone", owns_web=False)
    known = locales(root)
    loaded = catalogs(root, known)
    entries = facts(root, known, loaded)
    assert [entry.id for entry in entries] == ["demo"]
    assert ui_facts(entries, root) == ()


@pytest.mark.parametrize(
    "fields",
    ["needs: []", 'path: ""\nneeds: []'],
    ids=["absent", "empty"],
)
def test_a_capability_with_neither_path_nor_nav_still_generates(
    tmp_path: Path, fields: str
) -> None:
    # Chat states sessions and endpoints but owns no screen: its panel lives
    # on another capability's page, so a route path and a nav entry would
    # promise a surface that does not exist. facts() reads the absent field
    # and the empty one alike as no path, and the absent nav as false.
    root = _facts_tree(tmp_path, title="demo.gone", owns_web=False, fields=fields)
    known = locales(root)
    loaded = catalogs(root, known)
    entries = facts(root, known, loaded)
    assert [(entry.id, entry.path, entry.nav) for entry in entries] == [("demo", None, False)]


def test_an_absent_path_never_reaches_a_view_as_none(tmp_path: Path) -> None:
    # The home page navigates by path and the INDEX prints one per row: a
    # nav flag alone cannot carry a nav row, so the entry is skipped rather
    # than rendered at the string "None"; the INDEX has a dash for the path
    # it does not have.
    root = _facts_tree(
        tmp_path,
        title="demo.heading",
        owns_web=True,
        fields="needs: []\nnav: true",
        catalog_keys=("demo.heading",),
    )
    known = locales(root)
    loaded = catalogs(root, known)
    entries = facts(root, known, loaded)
    assert [(entry.id, entry.path, entry.nav) for entry in entries] == [("demo", None, True)]
    assert 'id: "demo"' not in typescript_nav(entries)
    index = docs_index(entries, known, loaded, root)
    assert "| demo.heading | — | ✓ | — |" in index
    assert "None" not in index


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
    assert scan.rows[0].title_key == "prompts.heading"
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
    assert '  { id: "prompts", path: "/settings/prompts", titleKey: "prompts.heading" },\n' in pages
    assert "export const settingsPages = [\n" in pages
    assert "] as const satisfies ReadonlyArray<{" in pages
    assert "titleKey: keyof typeof catalogs.en;" in pages


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
        "export const workspaceRoute = workspace;\n"
        'export const workspaceRouteId = "/novels/$id";',
    }
    root = _routes_repo(tmp_path, sources)
    pages = typescript_settings_pages(root)
    assert "export const settingsPages = [] as const satisfies ReadonlyArray<{" in pages
    assert "{ id:" not in pages
    table = typescript_routes(root)
    assert "settings" not in table.lower()


# The commands convention in miniature: the file's presence is the whole
# contract, so these fixtures are only files in the right place — nothing is
# parsed from their contents, the way nothing is parsed from routes.tsx's
# mere existence.
_COMMAND_MODULE = 'export const commands = [{ id: "x", titleKey: "x.title" }] as const;'


def _commands_repo(tmp_path: Path, capabilities: tuple[str, ...]) -> Path:
    """A miniature repo whose command modules belong to exactly `capabilities`."""
    capabilities_dir = tmp_path / "app" / "capabilities"
    capabilities_dir.mkdir(parents=True)
    for capability in capabilities:
        folder = capabilities_dir / capability / "web"
        folder.mkdir(parents=True)
        (folder / "commands.ts").write_text(_COMMAND_MODULE, encoding="utf-8")
    return tmp_path


def test_commands_view_imports_and_aggregates_the_modules_in_palette_order(
    tmp_path: Path,
) -> None:
    view = typescript_commands(
        _commands_repo(tmp_path, ("writing", "knowledge", "prompts", "settings"))
    )
    assert (
        "import { commands as writingCommands }"
        ' from "../../../app/capabilities/writing/web/commands";\n' in view
    )
    assert (
        "import { commands as settingsCommands }"
        ' from "../../../app/capabilities/settings/web/commands";\n' in view
    )
    assert (
        "import { commands as promptsCommands }"
        ' from "../../../app/capabilities/prompts/web/commands";\n' in view
    )
    # The palette's row order is a deliberate arrangement, not the folder
    # sort: writing leads when it appears, and the rest follow that pinned
    # order. A capability absent here contributes nothing to import.
    assert view.index("  ...writingCommands,\n") < view.index("  ...settingsCommands,\n")
    assert view.index("  ...settingsCommands,\n") < view.index("  ...promptsCommands,\n")
    assert view.index("  ...promptsCommands,\n") < view.index("  ...knowledgeCommands,\n")
    # Writing leads the pinned order and now contributes its module too.
    assert "export const commands = [\n" in view
    assert "] as const satisfies ReadonlyArray<Command>;" in view


def test_no_command_modules_leave_an_empty_aggregation(tmp_path: Path) -> None:
    # The pre-convention shape: no commands anywhere. The view is the empty
    # registry and carries no capability import — and, with the type's home
    # module gone from the shell, no Command import either.
    view = typescript_commands(_commands_repo(tmp_path, ()))
    assert "export const commands = [] as const;" in view
    assert "Command" not in view
    assert 'from "../../../app/capabilities' not in view


def test_a_module_outside_the_pinned_order_stops_the_scan(tmp_path: Path) -> None:
    # A capability the generator has not placed in the palette's row order
    # stops generation instead of silently sliding to the end of the
    # aggregation: the order is a product arrangement, and the message names
    # both the stranger and the fix.
    with pytest.raises(SystemExit, match="outside the palette") as failure:
        scan_commands(_commands_repo(tmp_path, ("chat",)))
    assert "'chat'" in str(failure.value)


def test_both_command_file_extensions_stop_the_scan(tmp_path: Path) -> None:
    # The generated import is extension-less; with commands.ts and
    # commands.tsx both present, which one defines the capability's commands
    # is ambiguous. Generation stops naming the folder instead of importing
    # one at random.
    folder = tmp_path / "app" / "capabilities" / "chat" / "web"
    folder.mkdir(parents=True)
    (folder / "commands.ts").write_text(_COMMAND_MODULE, encoding="utf-8")
    (folder / "commands.tsx").write_text(_COMMAND_MODULE, encoding="utf-8")
    with pytest.raises(SystemExit, match=r"commands\.ts and commands\.tsx"):
        scan_commands(tmp_path)


def test_workspace_route_id_must_be_exported() -> None:
    sources = {
        "writing": 'const workspace = createRoute({ path: "/novels/$id" });\n'
        "export const workspaceRoute = workspace;"
    }
    with pytest.raises(SystemExit, match="workspaceRouteId"):
        workspace_route_id(sources)


def test_workspace_view_is_null_without_a_host(tmp_path: Path) -> None:
    root = _routes_repo(tmp_path, {"chat": "export const routes = [] as const;"})
    assert "= null" in typescript_workspace(root)
