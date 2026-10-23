#!/usr/bin/env python3
"""Write every generated view of the capability facts and the language list.

Sources of truth: ``app/capabilities/*/capability.yaml`` — facts only (spec §4) —
and ``i18n/*.json``, whose *filenames* are the set of languages. Nothing declares
a language twice. Seven views, none hand-edited, all committed:

* ``app/generated/capabilities.py`` — the registry ``app/api/main.py``
  cross-checks against the mounted routers at startup;
* ``web/lib/generated/capabilities.ts`` — the nav entries the home page renders,
  with title keys the TypeScript compiler checks against the i18n catalog;
* ``app/generated/locales.py`` — the languages, for anything server-side that
  validates one;
* ``web/lib/generated/catalogs.ts`` — the imports, the ``Locale`` union and the
  catalog map, so a new ``i18n/<code>.json`` needs no TypeScript edit;
* ``web/lib/generated/routes.ts`` — the capability route table the router
  mounts, one import per capability that owns ``web/routes.tsx``, and the one
  composition point of the dock convention: dockRoutes factories are called
  with the exported workspaceRoute, so capabilities never import each other;
* ``web/lib/generated/docks.ts`` — the dock registry the workspace renders its
  dock tabs from, one row per capability exporting ``dockRoutes``: a new dock
  appears by existing, with zero generator changes;
* ``docs/user/INDEX.md`` — one row per capability per locale, with the table's
  own words read from the catalogs.

Adding a language is therefore one file plus ``just generate``. A field no view
reads is deleted from the Facts schema; a view no consumer reads is deleted with
it. ``just generate`` runs this after the facts change.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

# The source language leads the docs and the switcher; the rest follow in a
# stable order so the generated diff does not shuffle when a file appears.
SOURCE_LOCALE = "en"

# Keys the generated views read by name. A catalog missing one stops generation
# instead of rendering an empty table header.
REQUIRED_DOC_KEYS = (
    "locale.name",
    "docs.table.capability",
    "docs.table.path",
    "docs.table.needs",
    "needs.llm",
    "needs.embeddings",
)


@dataclass(frozen=True)
class Facts:
    """One capability's facts, exactly as the yaml holds them."""

    id: str
    title: str
    path: str
    needs: tuple[str, ...]
    nav: bool


@dataclass(frozen=True)
class Dock:
    """One row of the dock registry: a capability's dock as the workspace
    sees it — identity, route and catalog key, nothing else."""

    id: str
    path: str
    title_key: str


def locales(root: Path) -> tuple[str, ...]:
    """Every language the catalog carries, discovered from the files."""
    found = sorted(path.stem for path in (root / "i18n").glob("*.json"))
    if SOURCE_LOCALE not in found:
        raise SystemExit(f"i18n/{SOURCE_LOCALE}.json is missing: it is the type source")
    return tuple([SOURCE_LOCALE] + [locale for locale in found if locale != SOURCE_LOCALE])


def catalogs(root: Path, known: tuple[str, ...]) -> dict[str, dict[str, str]]:
    """Load every catalog and check the keys the generated views use."""
    loaded: dict[str, dict[str, str]] = {}
    for locale in known:
        source = root / "i18n" / f"{locale}.json"
        loaded[locale] = json.loads(source.read_text(encoding="utf-8"))
        missing = [key for key in REQUIRED_DOC_KEYS if key not in loaded[locale]]
        if missing:
            raise SystemExit(f"{source}: missing keys {missing}")
    return loaded


def facts(
    root: Path, known: tuple[str, ...], loaded: dict[str, dict[str, str]]
) -> tuple[Facts, ...]:
    """Load every capability.yaml, validating what the views rely on."""
    entries: list[Facts] = []
    for folder in sorted((root / "app" / "capabilities").iterdir()):
        source = folder / "capability.yaml"
        if not source.exists():
            continue
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
        unknown = set(raw) - {"id", "title", "path", "needs", "nav"}
        if unknown:
            raise SystemExit(f"{source}: unknown fields {sorted(unknown)}; facts only (spec §4)")
        entry = Facts(
            id=raw["id"],
            title=raw["title"],
            path=raw["path"],
            needs=tuple(sorted(raw["needs"])),
            nav=raw["nav"],
        )
        if entry.id != folder.name:
            raise SystemExit(f"{source}: id {entry.id!r} must match the folder name")
        unknown_needs = set(entry.needs) - {"llm", "embeddings"}
        if unknown_needs:
            raise SystemExit(f"{source}: unknown needs {sorted(unknown_needs)}")
        for locale in known:
            if entry.title not in loaded[locale]:
                raise SystemExit(
                    f"{source}: title key {entry.title!r} missing from i18n/{locale}.json"
                )
        entries.append(entry)
    if not entries:
        raise SystemExit("no capability.yaml found under app/capabilities/")
    return tuple(entries)


def python_locales(known: tuple[str, ...]) -> str:
    """The server-side view: what a locale value is validated against."""
    literal = ", ".join(f'"{locale}"' for locale in known)
    trailing = "," if len(known) == 1 else ""
    return (
        '"""Generated by scripts/generate_capabilities.py from i18n/*.json — DO NOT EDIT.\n'
        "\n"
        "The languages the catalog carries, discovered from its files. A new\n"
        "i18n/<code>.json appears here on the next `just generate`.\n"
        '"""\n'
        "\n"
        f"LOCALES: tuple[str, ...] = ({literal}{trailing})\n"
        f'SOURCE_LOCALE = "{SOURCE_LOCALE}"\n'
    )


def typescript_catalogs(known: tuple[str, ...]) -> str:
    """The web-side view: imports, the locale union and the catalog map."""
    imports = "".join(f'import {locale} from "../../../i18n/{locale}.json";\n' for locale in known)
    union = ", ".join(f'"{locale}"' for locale in known)
    mapping = ", ".join(known)
    return (
        "// Generated by scripts/generate_capabilities.py from i18n/*.json — DO NOT EDIT.\n"
        "// Adding a language is i18n/<code>.json plus `just generate`: the union and\n"
        "// the map below are written from the files that exist.\n"
        f"{imports}"
        "\n"
        f"export const locales = [{union}] as const;\n"
        "export type Locale = (typeof locales)[number];\n"
        "\n"
        "// Typed against the source catalog: a key missing in any locale is a build\n"
        "// error at this assignment, not a blank label at runtime.\n"
        f"export const catalogs: Record<Locale, typeof {SOURCE_LOCALE}> = {{ {mapping} }};\n"
    )


def python_registry(entries: tuple[Facts, ...]) -> str:
    """The app-side view: the registry main.py cross-checks at startup."""

    def needs_literal(entry: Facts) -> str:
        # Double quotes because ruff format rewrites single ones, and the
        # trailing comma keeps a one-element tuple a tuple.
        joined = ", ".join(f'"{need}"' for need in entry.needs)
        trailing = "," if len(entry.needs) == 1 else ""
        return f"({joined}{trailing})"

    rows = "".join(
        "    Capability(\n"
        f'        id="{entry.id}",\n'
        f'        title_key="{entry.title}",\n'
        f'        path="{entry.path}",\n'
        f"        needs={needs_literal(entry)},\n"
        f"        in_nav={entry.nav!s},\n"
        "    ),\n"
        for entry in entries
    )
    return (
        '"""Generated by scripts/generate_capabilities.py — DO NOT EDIT.\n'
        "\n"
        "Source: app/capabilities/*/capability.yaml. The app-side view of the capability\n"
        "facts; `app/api/main.py` cross-checks it against the mounted routers and logs\n"
        "one line per capability at startup.\n"
        '"""\n'
        "\n"
        "from dataclasses import dataclass\n"
        "\n"
        "\n"
        "@dataclass(frozen=True)\n"
        "class Capability:\n"
        "    id: str\n"
        "    title_key: str\n"
        "    path: str\n"
        "    needs: tuple[str, ...]\n"
        "    in_nav: bool\n"
        "\n"
        "\n"
        "CAPABILITIES: tuple[Capability, ...] = (\n"
        f"{rows})\n"
    )


def typescript_nav(entries: tuple[Facts, ...]) -> str:
    """The web-side view: the nav entries the home page renders."""
    rows = "".join(
        f'  {{ id: "{entry.id}", path: "{entry.path}", titleKey: "{entry.title}" }},\n'
        for entry in entries
        if entry.nav
    )
    return (
        "// Generated by scripts/generate_capabilities.py from"
        " app/capabilities/*/capability.yaml — DO NOT EDIT.\n"
        "// The web-side view of the capability facts: the home page navigation. The\n"
        "// title keys are checked against the English catalog by the compiler, so a\n"
        "// missing i18n key fails the build.\n"
        'import en from "../../../i18n/en.json";\n'
        "\n"
        "export const nav = [\n"
        f"{rows}] as const satisfies ReadonlyArray<{{\n"
        "  id: string;\n"
        "  path: string;\n"
        "  titleKey: keyof typeof en;\n"
        "}>;\n"
    )


def route_sources(root: Path) -> dict[str, str]:
    """Every capability's routes.tsx source, keyed by capability, sorted."""
    return {
        folder.name: (folder / "web" / "routes.tsx").read_text(encoding="utf-8")
        for folder in sorted((root / "app" / "capabilities").iterdir())
        if (folder / "web" / "routes.tsx").is_file()
    }


def _workspace_path(source: str, capability: str) -> str:
    """The workspace route's path literal, traced through the export's alias."""
    alias = re.search(r"export const workspaceRoute = (\w+)", source)
    declaration = re.search(rf"const {alias.group(1)} = createRoute\(", source) if alias else None
    literal = re.search(r'path: "([^"]+)"', source[declaration.end() :]) if declaration else None
    if literal is None:
        raise SystemExit(
            f"app/capabilities/{capability}/web/routes.tsx: workspaceRoute must alias"
            " a `const <name> = createRoute(…)` whose path literal the scan can"
            " read — the dock registry derives its rows' paths from it"
        )
    return literal.group(1)


def _dock_path(source: str, capability: str) -> str:
    """The one path literal inside the dockRoutes export."""
    block = re.search(r"export const dockRoutes\b.*?\] as const;", source, re.DOTALL)
    literals = re.findall(r'path: "([^"]+)"', block.group(0)) if block else []
    if len(literals) != 1:
        raise SystemExit(
            f"app/capabilities/{capability}/web/routes.tsx: the dock registry"
            f" reads exactly one path literal from the dockRoutes export, found"
            f" {len(literals)} — one dock per capability; extend the registry"
            " contract before exporting several"
        )
    return literals[0]


@dataclass(frozen=True)
class DockScan:
    """The dock convention as one scan of the route sources reads it: the
    registry rows and the one capability whose workspace route hosts them."""

    docks: tuple[Dock, ...]
    host: str | None


def scan_docks(sources: dict[str, str]) -> DockScan:
    """The dock convention, discovered from the route sources.

    Discovery is a substring scan, not a parse — the caveat that keeps this
    honest: a capability counts as a dock when its routes.tsx contains
    ``export const dockRoutes`` and as the host when it contains ``export
    const workspaceRoute``, and the path literals are read as the first
    ``path: "…"`` after those markers. A routes.tsx that drifts from that
    shape fails loudly here (or drifts visibly in ``just generate``) instead
    of generating a wrong table.
    """
    docks = [
        capability for capability, text in sources.items() if "export const dockRoutes" in text
    ]
    hosts = [
        capability for capability, text in sources.items() if "export const workspaceRoute" in text
    ]
    if len(hosts) > 1:
        raise SystemExit(
            f"{len(hosts)} capabilities export workspaceRoute ({hosts}); the"
            " dock convention parents every dock under exactly one workspace"
        )
    if docks and not hosts:
        raise SystemExit(
            f"dockRoutes exported by {docks}, but no capability exports"
            " workspaceRoute to parent them under"
        )
    if not hosts:
        return DockScan(docks=(), host=None)
    workspace = _workspace_path(sources[hosts[0]], hosts[0])
    return DockScan(
        docks=tuple(
            Dock(
                id=capability,
                path=f"{workspace}/{_dock_path(sources[capability], capability)}",
                title_key=f"{capability}.dockTitle",
            )
            for capability in docks
        ),
        host=hosts[0],
    )


def typescript_routes(root: Path) -> str:
    """The web-side view: the capability route table the router mounts."""
    sources = route_sources(root)
    found = tuple(sources)
    # The dock convention, discovered from the sources by the same scan the
    # registry view reads: a capability exports ``dockRoutes`` (factories
    # that parent routes at another capability's workspace) and exactly one
    # exports ``workspaceRoute``. No facts file is involved — the export is
    # the whole contract, and this table is the one place the two sides meet.
    scan = scan_docks(sources)
    docks = tuple(dock.id for dock in scan.docks)
    hosts = [scan.host] if scan.host is not None else []

    def import_names(capability: str) -> str:
        names = f"routes as {capability}"
        if capability in docks:
            names += f", dockRoutes as {capability}Docks"
        if docks and capability in hosts:
            names += ", workspaceRoute"
        return names

    imports = "".join(
        f"import {{ {import_names(capability)} }} from"
        f' "../../../app/capabilities/{capability}/web/routes";\n'
        for capability in found
    )
    dock_consts = "".join(
        f"const {capability}DockRoutes = {capability}Docks.map((dock) => dock(workspaceRoute));\n"
        for capability in docks
    )
    spread = "".join(f"  ...{capability},\n" for capability in found)
    dock_spread = (
        "".join(f"  ...{capability}DockRoutes,\n" for capability in docks) if docks else ""
    )
    dock_note = (
        "  //\n"
        "  // Dock children come after every capability's own routes: the router\n"
        "  // initializes a route from its parent, so the workspace route must be\n"
        "  // in the table before the dock routes parented at it.\n"
        if docks
        else ""
    )
    dock_block = f"{dock_consts}\n" if dock_consts else ""
    return (
        "// Generated by scripts/generate_capabilities.py from"
        " app/capabilities/*/web/routes.tsx — DO NOT EDIT.\n"
        "// The capability route table: the router mounts exactly this. A\n"
        "// capability that owns no routes.tsx is simply absent, and a new one\n"
        "// appears on the next `just generate`.\n"
        "//\n"
        "// as const, no annotation: the tuple of concrete route types carries\n"
        "// each route's literal path into addChildren, which keeps a wrong\n"
        "// `to=` a build error.\n"
        "//\n"
        "// Dock composition: a capability may export dockRoutes — factories\n"
        "// that take the workspace route and return child routes for it — and\n"
        "// exactly one capability exports workspaceRoute. The call below\n"
        "// passes the workspace route into every factory: capabilities never\n"
        "// import each other; this generated table is the one composition\n"
        "// point.\n"
        f"{imports}"
        "\n"
        f"{dock_block}"
        "export const capabilityRoutes = [\n"
        f"{spread}{dock_note}{dock_spread}] as const;\n"
    )


def typescript_docks(root: Path) -> str:
    """The web-side view: the dock registry the workspace renders tabs from."""
    scan = scan_docks(route_sources(root))
    rows = "".join(
        f'  {{ id: "{dock.id}", path: "{dock.path}", titleKey: "{dock.title_key}" }},\n'
        for dock in scan.docks
    )
    table = (
        f"export const docks = [\n{rows}] as const" if rows else "export const docks = [] as const"
    )
    return (
        "// Generated by scripts/generate_capabilities.py from"
        " app/capabilities/*/web/routes.tsx — DO NOT EDIT.\n"
        "// The dock registry: one row per capability that exports dockRoutes,\n"
        "// sorted — the workspace renders one tab per row and navigates to the\n"
        "// row's path. A new dock appears here by adding its dockRoutes, with\n"
        "// zero generator changes.\n"
        "//\n"
        "// as const, no annotation: the literal path carries each row's route\n"
        "// into the tab's `to=` (a drifted row is a build error), and the\n"
        "// title keys are checked against the English catalog by the compiler.\n"
        'import en from "../../../i18n/en.json";\n'
        "\n"
        f"{table} satisfies ReadonlyArray<{{\n"
        "  id: string;\n"
        "  path: string;\n"
        "  titleKey: keyof typeof en;\n"
        "}>;\n"
    )


def docs_index(
    entries: tuple[Facts, ...], known: tuple[str, ...], loaded: dict[str, dict[str, str]]
) -> str:
    """The reader-side view: one row per capability per locale."""
    sections: list[str] = []
    for locale in known:
        catalog = loaded[locale]
        capability = catalog["docs.table.capability"]
        path_column = catalog["docs.table.path"]
        needs_column = catalog["docs.table.needs"]
        rows = "".join(
            f"| {catalog[entry.title]} | {entry.path} | "
            + (", ".join(catalog[f"needs.{need}"] for need in entry.needs) or "—")
            + " |\n"
            for entry in entries
        )
        sections.append(
            f"## {catalog['locale.name']}\n\n| {capability} | {path_column} | {needs_column} |\n"
            "| --- | --- | --- |\n" + rows
        )
    return (
        "<!-- Generated by scripts/generate_capabilities.py from"
        " app/capabilities/*/capability.yaml — DO NOT EDIT. -->\n"
        "<!-- Titles and table words come from i18n/*.json. Regenerate with `just generate`. -->\n"
        "\n"
        "# Narrare — the app's surfaces\n"
        "\n"
        "One row per capability, from each capability's facts file. Long-form user\n"
        "documentation grows around this index, never inside it.\n"
        "\n" + "\n".join(sections)
    )


def main() -> None:
    root = Path(".")
    known = locales(root)
    loaded = catalogs(root, known)
    loaded_facts: tuple[Facts, ...] = facts(root, known, loaded)
    outputs: dict[str, str] = {
        "app/generated/capabilities.py": python_registry(loaded_facts),
        "app/generated/locales.py": python_locales(known),
        "web/lib/generated/capabilities.ts": typescript_nav(loaded_facts),
        "web/lib/generated/catalogs.ts": typescript_catalogs(known),
        "web/lib/generated/routes.ts": typescript_routes(root),
        "web/lib/generated/docks.ts": typescript_docks(root),
        "docs/user/INDEX.md": docs_index(loaded_facts, known, loaded),
    }
    for target, content in outputs.items():
        path = root / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {target}")


if __name__ == "__main__":
    main()
