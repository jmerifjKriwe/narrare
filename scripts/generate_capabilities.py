#!/usr/bin/env python3
"""Write every generated view of the capability facts and the language list.

Sources of truth: ``app/capabilities/*/capability.yaml`` — facts only (spec §4) —
``i18n/*.json`` for the shared text, whose *filenames* are the set of languages,
and ``app/capabilities/*/web/i18n/*.json`` for each capability's own text, with
``i18n/overlays/formality/*.json`` carrying sparse formal variants. Nothing
declares a language twice. Fourteen views, none hand-edited, all committed:

* ``app/generated/capabilities.py`` — the registry ``app/api/main.py``
  cross-checks against the mounted routers at startup;
* ``web/lib/generated/capabilities.ts`` — the nav entries the home page renders,
  with title keys the TypeScript compiler checks against the merged catalog;
* ``app/generated/locales.py`` — the languages, for anything server-side that
  validates one;
* ``web/lib/generated/catalogs.ts`` — the imports, the ``Locale`` union and the
  merged catalog map, so a new ``i18n/<code>.json`` or a new capability
  catalog needs no TypeScript edit;
* ``web/lib/generated/overlays.ts`` — the sparse formal variants, one import
  per language that carries an overlay; a new overlay appears on the next
  ``just generate``;
* ``web/lib/generated/routes.ts`` — the capability route table the router
  mounts, one import per capability that owns ``web/routes.tsx``, and the
  composition points of two conventions: dockRoutes factories are called with
  the exported workspaceRoute and settingsRoutes factories with the exported
  settingsRoute, so capabilities never import each other;
* ``web/lib/generated/workspace.ts`` — the shell's workspace-route id, a leaf
  module so chrome imports no route table;
* ``web/lib/generated/docks.ts`` — the dock registry the workspace renders its
  dock tabs from, one row per capability exporting ``dockRoutes``: a new dock
  appears by existing, with zero generator changes;
* ``web/lib/generated/settingsPages.ts`` — the settings registry the settings
  hub renders its cluster list from, one row per capability exporting
  ``settingsRoutes``: a new cluster appears by existing, with zero generator
  changes;
* ``web/lib/generated/commands.ts`` — the command registry the palette
  renders and filters, one import per capability owning
  ``web/commands.ts(x)``, aggregated in the palette's row order;
* ``web/lib/generated/structures.ts`` — the storyboard structure registry
  the switcher offers, one row per structure in
  ``app/capabilities/planning/structures.py``: a new structure appears by
  existing, with zero switcher edits;
* ``web/lib/generated/help.ts`` — the help registry the UI resolves by
  surface, one group per topic under ``app/capabilities/*/web/help/``:
  a new topic appears by existing, with zero generator changes;
* ``docs/user/INDEX.md`` — one row per capability per locale, with the table's
  own words read from the catalogs;
* ``docs/user/help-coverage.md`` — which capabilities ship help, in which
  languages, one table per capability the help scan found.

A capability without a ``web/`` directory has no UI: it contributes no nav
row, no route import, no INDEX row, no catalog import, no dock, command,
settings or help entry. Its facts stay in the backend registry — the routers
still mount it.

Adding a language is therefore one central file plus one file per capability
that owns text, then ``just generate``. A field no view reads is deleted from
the Facts schema; a view no consumer reads is deleted with it. ``just generate``
runs this after the facts change.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

from app.capabilities.planning.structures import STRUCTURES
from app.kernel.interchange import parse_archive
from app.kernel.interchange.demos import DEMOS as KERNEL_DEMOS
from app.kernel.interchange.demos import demo_tree

# The capability whose registry STRUCTURES is: the structures view is that
# capability's UI contribution — the switcher offers its rows — so it emits
# rows only while the capability owns a web/ directory too.
STRUCTURES_OWNER = "planning"

# The source language leads the docs and the switcher; the rest follow in a
# stable order so the generated diff does not shuffle when a file appears.
SOURCE_LOCALE = "en"

# Keys the generated views read by name. A catalog missing one stops generation
# instead of rendering an empty table header.
REQUIRED_DOC_KEYS = (
    "locale.name",
    "docs.table.capability",
    "docs.table.path",
    "docs.table.nav",
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


@dataclass(frozen=True)
class SettingsPage:
    """One row of the settings registry: a capability's settings page as the
    hub sees it — identity, route and catalog key, nothing else."""

    id: str
    path: str
    title_key: str


def locales(root: Path) -> tuple[str, ...]:
    """Every language the catalog carries, discovered from the files."""
    found = sorted(path.stem for path in (root / "i18n").glob("*.json"))
    if SOURCE_LOCALE not in found:
        raise SystemExit(f"i18n/{SOURCE_LOCALE}.json is missing: it is the type source")
    return tuple([SOURCE_LOCALE] + [locale for locale in found if locale != SOURCE_LOCALE])


def catalog_sources(root: Path, known: tuple[str, ...]) -> dict[str, tuple[Path, ...]]:
    """Every file one locale's catalog is merged from.

    The central ``i18n/<locale>.json`` leads — it is the language registry and
    the shared text — and each capability's ``web/i18n/<locale>.json`` follows,
    sorted by capability id. A capability that carries an ``i18n`` directory
    must carry every locale: a half-translated capability would render one
    language from its file and another from nowhere.
    """
    central = root / "i18n"
    capabilities = root / "app" / "capabilities"
    sources: dict[str, list[Path]] = {locale: [central / f"{locale}.json"] for locale in known}
    if capabilities.is_dir():
        for folder in sorted(capabilities.iterdir()):
            i18n = folder / "web" / "i18n"
            if not i18n.is_dir():
                continue
            strangers = sorted(path.stem for path in i18n.glob("*.json") if path.stem not in known)
            if strangers:
                raise SystemExit(
                    f"{i18n}: catalogs for languages the central catalog does"
                    f" not carry: {strangers}"
                )
            for locale in known:
                source = i18n / f"{locale}.json"
                if not source.is_file():
                    raise SystemExit(
                        f"{source} is missing: {folder.name} carries an i18n"
                        f" directory, so it must carry every catalog locale"
                        f" ({', '.join(known)})"
                    )
                sources[locale].append(source)
    return {locale: tuple(paths) for locale, paths in sources.items()}


def load_catalog(source: Path) -> dict[str, str]:
    """One catalog file, checked for the shape and order the merge relies on."""
    loaded = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise SystemExit(f"{source}: a catalog is a JSON object")
    catalog: dict[str, str] = {}
    for key, value in cast("dict[object, object]", loaded).items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise SystemExit(f"{source}: every key and value is a string")
        catalog[key] = value
    keys = list(catalog)
    if keys != sorted(keys):
        raise SystemExit(
            f"{source}: keys are not sorted; one stable order keeps a new key"
            " where it belongs instead of at the end"
        )
    return catalog


def catalogs(root: Path, known: tuple[str, ...]) -> dict[str, dict[str, str]]:
    """Merge every source per locale, refusing a key with two owners."""
    sources = catalog_sources(root, known)
    loaded: dict[str, dict[str, str]] = {}
    for locale in known:
        merged: dict[str, str] = {}
        owner: dict[str, Path] = {}
        for source in sources[locale]:
            for key, value in load_catalog(source).items():
                if key in merged:
                    raise SystemExit(
                        f"{key!r} is defined in both {owner[key]} and {source}; a key has one owner"
                    )
                merged[key] = value
                owner[key] = source
        missing = [key for key in REQUIRED_DOC_KEYS if key not in merged]
        if missing:
            raise SystemExit(f"{root / 'i18n' / f'{locale}.json'}: missing keys {missing}")
        loaded[locale] = merged
    # Every locale carries the source catalog's keys: a missing key would fall
    # through to a blank label, an extra one would be dead copy. The generated
    # TypeScript assignment catches this too, but the generator can name the
    # locale and the keys before the build does.
    source_keys = set(loaded[SOURCE_LOCALE])
    for locale in known:
        if locale == SOURCE_LOCALE:
            continue
        keys = set(loaded[locale])
        missing = sorted(source_keys - keys)
        extra = sorted(keys - source_keys)
        if missing or extra:
            raise SystemExit(
                f"{locale} catalog does not match {SOURCE_LOCALE}: missing {missing}, extra {extra}"
            )
    return loaded


def facts(root: Path) -> tuple[Facts, ...]:
    """Load every capability.yaml, validating what the views rely on.

    The registry reads every capability: the backend mounts a router for
    each one, ``web/`` or not. The facts' title key is the UI rows' concern
    — the views that render it skip a key their catalog does not resolve
    (see ``ui_facts``).
    """
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
        entries.append(entry)
    if not entries:
        raise SystemExit("no capability.yaml found under app/capabilities/")
    return tuple(entries)


def web_ids(root: Path) -> frozenset[str]:
    """The capabilities that own a ``web/`` directory — the ones with a UI.

    This is the one rule the UI views share: a capability without the
    directory contributes no nav row, no INDEX row, no help row, no
    structures rows, while its facts stay in the backend registry.
    """
    capabilities = root / "app" / "capabilities"
    if not capabilities.is_dir():
        return frozenset()
    return frozenset(folder.name for folder in capabilities.iterdir() if (folder / "web").is_dir())


def ui_facts(
    entries: tuple[Facts, ...], root: Path, loaded: dict[str, dict[str, str]]
) -> tuple[Facts, ...]:
    """The facts the UI views render rows for.

    A row needs two things: a capability that owns a ``web/`` directory
    (the one rule, ``web_ids``) and a title key the source catalog
    resolves — a row's words come from the catalog, and an interim page
    whose catalog carries no facts title has no row to render until the
    rebuilt screens bring the title back.
    """
    present = web_ids(root)
    return tuple(
        entry for entry in entries if entry.id in present and entry.title in loaded[SOURCE_LOCALE]
    )


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


def _identifier(value: str) -> str:
    """A locale code or capability id as a TypeScript identifier fragment."""
    return re.sub(r"[^0-9A-Za-z_]", "_", value)


def typescript_catalogs(root: Path, known: tuple[str, ...]) -> str:
    """The web-side view: one merged object per locale, typed from the source."""
    sources = catalog_sources(root, known)
    imports: list[str] = []
    merged: list[str] = []
    mapping: list[str] = []
    for locale in known:
        loc = _identifier(locale)
        aliases: list[str] = []
        for source in sources[locale]:
            if source == root / "i18n" / f"{locale}.json":
                alias = f"{loc}_central"
            else:
                capability = source.parents[2].name
                alias = f"{loc}_{_identifier(capability)}"
            imports.append(
                f'import {alias} from "../../../{source.relative_to(root).as_posix()}";\n'
            )
            aliases.append(alias)
        merged.append(
            f"const {loc}_merged = {{\n" + "".join(f"  ...{alias},\n" for alias in aliases) + "};\n"
        )
        mapping.append(f'  "{locale}": {loc}_merged,\n')
    union = ", ".join(f'"{locale}"' for locale in known)
    source_merged = f"{_identifier(SOURCE_LOCALE)}_merged"
    return (
        "// Generated by scripts/generate_capabilities.py from i18n/*.json and\n"
        "// app/capabilities/*/web/i18n/*.json — DO NOT EDIT.\n"
        "// A capability's text is merged over the shared catalog; a new capability\n"
        "// file appears on the next `just generate`.\n"
        f"{''.join(imports)}"
        "\n"
        f"export const locales = [{union}] as const;\n"
        "export type Locale = (typeof locales)[number];\n"
        "\n"
        f"{''.join(merged)}"
        "\n"
        "// Typed against the source catalog: a key missing in any locale is a build\n"
        "// error at this assignment, not a blank label at runtime.\n"
        f"export const catalogs: Record<Locale, typeof {source_merged}> = {{\n"
        f"{''.join(mapping)}}};\n"
    )


def overlay_sources(
    root: Path, known: tuple[str, ...], loaded: dict[str, dict[str, str]]
) -> dict[str, dict[str, str]]:
    """The sparse formal variants, emitted against the merged catalogs.

    A key absent from an overlay falls through to the base catalog, so the
    overlay is opt-in and a new base string works in both registers until
    someone writes its formal wording. The source locale has no overlay: its
    language has no formality distinction. There is no de/fr key parity —
    French already speaks the neutral register in its base catalog, so a
    parity rule would force it to repeat strings it already has.

    A variant whose base string the merged catalog no longer carries is
    dead copy, not an error: its capability catalog left with the
    capability's ``web/`` directory, and the shared-catalog cleanup removes
    the row from the overlay file in its own task. Skipping it keeps the
    view emitting only live variants without demanding the cleanup first.
    """
    directory = root / "i18n" / "overlays" / "formality"
    if not directory.is_dir():
        return {}
    strangers = sorted(path.stem for path in directory.glob("*.json") if path.stem not in known)
    if strangers:
        raise SystemExit(
            f"{directory}: overlays for languages the catalog does not carry: {strangers}"
        )
    if (directory / f"{SOURCE_LOCALE}.json").exists():
        raise SystemExit(
            f"{directory / f'{SOURCE_LOCALE}.json'}: the source locale has no formality overlay"
        )
    overlays: dict[str, dict[str, str]] = {}
    for locale in known:
        source = directory / f"{locale}.json"
        if not source.is_file():
            continue
        overlay = load_catalog(source)
        overlay = {key: value for key, value in overlay.items() if key in loaded[locale]}
        empty = [key for key, value in overlay.items() if not value.strip()]
        if empty:
            raise SystemExit(f"{source}: empty values {empty}")
        if overlay:
            overlays[locale] = overlay
    return overlays


def typescript_overlays(known: tuple[str, ...], overlays: dict[str, dict[str, str]]) -> str:
    """The web-side view: one sparse overlay import per language that has one.

    A locale whose variants all went dead emits no import at all — an empty
    mapping would be a second, quieter way of saying nothing.
    """
    imports = "".join(
        f"import {_identifier(locale)}_overlay from"
        f' "../../../i18n/overlays/formality/{locale}.json";\n'
        for locale in known
        if overlays.get(locale)
    )
    mapping = "".join(
        f'  "{locale}": {_identifier(locale)}_overlay,\n'
        for locale in known
        if overlays.get(locale)
    )
    return (
        "// Generated by scripts/generate_capabilities.py from\n"
        "// i18n/overlays/formality/*.json — DO NOT EDIT.\n"
        "// Sparse formal variants; a key absent here falls through to the base\n"
        "// catalog. English has no overlay: it has no formality distinction.\n"
        'import type { Locale } from "./catalogs";\n'
        f"{imports}"
        "\n"
        "export const overlays: Partial<Record<Locale, Record<string, string>>> = {\n"
        f"{mapping}"
        "};\n"
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
        f"        needs={needs_literal(entry)},\n"
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
        "    needs: tuple[str, ...]\n"
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
        "// title keys are checked against the merged English catalog by the compiler,\n"
        "// so a missing i18n key fails the build.\n"
        'import { catalogs } from "./catalogs";\n'
        "\n"
        "export const nav = [\n"
        f"{rows}] as const satisfies ReadonlyArray<{{\n"
        "  id: string;\n"
        "  path: string;\n"
        "  titleKey: keyof typeof catalogs.en;\n"
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
    """The workspace route's path literal, traced through the export's alias.

    Raise SystemExit if the alias, createRoute declaration, or path cannot be read.
    """
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
    """The one path literal inside the dockRoutes export.

    Raise SystemExit unless exactly one path is found before ``] as const;``.
    """
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


def _settings_route_path(source: str, capability: str) -> str:
    """The settings route's path literal, traced through the export's alias.

    Raise SystemExit if the alias, createRoute declaration, or path cannot be read.
    """
    alias = re.search(r"export const settingsRoute = (\w+)", source)
    declaration = re.search(rf"const {alias.group(1)} = createRoute\(", source) if alias else None
    literal = re.search(r'path: "([^"]+)"', source[declaration.end() :]) if declaration else None
    if literal is None:
        raise SystemExit(
            f"app/capabilities/{capability}/web/routes.tsx: settingsRoute must alias"
            " a `const <name> = createRoute(…)` whose path literal the scan can"
            " read — the settings registry derives its rows' paths from it"
        )
    return literal.group(1)


def _settings_path(source: str, capability: str) -> str:
    """The one path literal inside the settingsRoutes export.

    Raise SystemExit unless exactly one path is found before ``] as const;``.
    """
    block = re.search(r"export const settingsRoutes\b.*?\] as const;", source, re.DOTALL)
    literals = re.findall(r'path: "([^"]+)"', block.group(0)) if block else []
    if len(literals) != 1:
        raise SystemExit(
            f"app/capabilities/{capability}/web/routes.tsx: the settings"
            f" registry reads exactly one path literal from the settingsRoutes"
            f" export, found {len(literals)} — one settings page per"
            " capability; extend the registry contract before exporting several"
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
    const workspaceRoute``. The host export must alias a createRoute
    declaration with a readable path; each dock export must contain exactly
    one path literal before ``] as const;``. No host and no docks returns
    an empty scan. Raise SystemExit for multiple hosts, docks without a host,
    unreadable paths, or duplicate full dock paths. Other source drift may
    still require inspection of the generated output.
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
    rows = tuple(
        Dock(
            id=capability,
            path=f"{workspace}/{_dock_path(sources[capability], capability)}",
            title_key=f"{capability}.dockTitle",
        )
        for capability in docks
    )
    # Two capabilities' docks resolving to the same full path would render two
    # registry rows behind one route: both tabs navigate identically. The
    # guard names every capability at the path, so the message alone points
    # at the fix.
    owners: dict[str, list[str]] = {}
    for dock in rows:
        owners.setdefault(dock.path, []).append(dock.id)
    for path, names in owners.items():
        if len(names) > 1:
            raise SystemExit(
                f"capabilities {names} resolve their docks to the same path"
                f" ({path}); the dock registry is one row per path"
            )
    return DockScan(docks=rows, host=hosts[0])


@dataclass(frozen=True)
class SettingsScan:
    """The settings convention as one scan of the route sources reads it: the
    registry rows and the one capability whose settings route hosts them."""

    rows: tuple[SettingsPage, ...]
    host: str | None


def scan_settings(sources: dict[str, str]) -> SettingsScan:
    """The settings convention, discovered from the route sources.

    Discovery is a substring scan, not a parse — the caveat that keeps this
    honest: a capability counts as a settings page when its routes.tsx
    contains ``export const settingsRoutes`` and as the host when it
    contains ``export const settingsRoute`` as a whole word — ``settingsRoutes``
    contains that substring, so the bare check would read every contributor
    as a host. The host export must alias a createRoute declaration with a
    readable path; each settings export must contain exactly one path
    literal before ``] as const;``. No host and no rows returns an empty
    scan. Raise SystemExit for multiple hosts, rows without a host,
    unreadable paths, or duplicate full page paths. Other source drift may
    still require inspection of the generated output.
    """
    pages = [
        capability for capability, text in sources.items() if "export const settingsRoutes" in text
    ]
    hosts = [
        capability
        for capability, text in sources.items()
        if re.search(r"export const settingsRoute\b", text)
    ]
    if len(hosts) > 1:
        raise SystemExit(
            f"{len(hosts)} capabilities export settingsRoute ({hosts}); the"
            " settings convention parents every page under exactly one"
            " settings route"
        )
    if pages and not hosts:
        raise SystemExit(
            f"settingsRoutes exported by {pages}, but no capability exports"
            " settingsRoute to parent them under"
        )
    if not hosts:
        return SettingsScan(rows=(), host=None)
    settings_route = _settings_route_path(sources[hosts[0]], hosts[0])
    rows = tuple(
        SettingsPage(
            id=capability,
            path=f"{settings_route}/{_settings_path(sources[capability], capability)}",
            title_key=f"{capability}.heading",
        )
        for capability in pages
    )
    # Two capabilities' pages resolving to the same full path would put two
    # registry rows behind one route: the hub would list two clusters that
    # navigate identically. The guard names every capability at the path,
    # so the message alone points at the fix.
    owners: dict[str, list[str]] = {}
    for page in rows:
        owners.setdefault(page.path, []).append(page.id)
    for path, names in owners.items():
        if len(names) > 1:
            raise SystemExit(
                f"capabilities {names} resolve their settings pages to the"
                f" same path ({path}); the settings registry is one row per"
                " path"
            )
    return SettingsScan(rows=rows, host=hosts[0])


@dataclass(frozen=True)
class HelpTopicLocale:
    """One help topic's text in one language: its title and its raw markdown
    body, exactly as the file holds them."""

    locale: str
    title: str
    body: str  # raw markdown body (without frontmatter)


@dataclass(frozen=True)
class HelpTopic:
    """One help topic as the scan reads it: identity and placement read from
    the source language's frontmatter, plus every locale the topic exists in."""

    capability: str
    slug: str
    surfaces: tuple[str, ...]
    order: int | None
    locales: tuple[str, ...]  # sorted, en first
    locale_data: tuple[HelpTopicLocale, ...]


@dataclass(frozen=True)
class HelpCapability:
    """One capability's help topics, sorted by slug."""

    capability: str
    topics: tuple[HelpTopic, ...]


class HelpScanError(SystemExit):
    """A help scan validation failure; SystemExit so `just generate` stops
    with the message and nothing else."""


def _split_frontmatter(source: Path, text: str) -> tuple[dict[object, object], str]:
    """One topic file's frontmatter mapping and the markdown body after it.

    The block sits between the opening ``---`` and the first closing ``---``
    line; the body is everything after the closing delimiter's newline and
    may be empty. Anything else — no opening delimiter, no closing one, a
    closing delimiter with trailing characters, YAML that is not a mapping —
    is a malformed topic.
    """
    if not text.startswith("---"):
        raise HelpScanError(f"{source}: a help topic starts with a --- frontmatter block")
    closing = text.find("\n---", 3)
    if closing < 0:
        raise HelpScanError(f"{source}: the frontmatter block has no closing ---")
    rest = text[closing + 4 :]
    if rest.startswith("\r\n"):
        rest = rest[2:]
    elif rest.startswith("\n"):
        rest = rest[1:]
    elif rest:
        raise HelpScanError(f"{source}: the closing --- must sit on its own line")
    try:
        loaded = yaml.safe_load(text[3:closing])
    except yaml.YAMLError as error:
        raise HelpScanError(f"{source}: frontmatter is not valid YAML: {error}") from error
    if not isinstance(loaded, dict):
        raise HelpScanError(f"{source}: the frontmatter block is a mapping of fields")
    return cast("dict[object, object]", loaded), rest


def _is_slug(value: str) -> bool:
    """A capability id or topic slug: lowercase letters, digits and
    hyphens, starting with a letter. This is the documented format, and it
    is also what makes the value safe to interpolate into the generated
    TypeScript string literals and import paths without escaping."""
    return bool(re.fullmatch(r"[a-z][a-z0-9-]*", value))


def scan_help(root: Path) -> tuple[HelpCapability, ...]:
    """The help convention, discovered from the capability folders.

    A capability carries help when ``app/capabilities/<id>/web/help/``
    exists. Its locale subdirectories hold the topics, one ``<slug>.md`` per
    topic; the file's presence is the contract, so a new topic or a new
    language appears on the next `just generate` with zero generator
    changes. Unlike the route scans this one reads the files: frontmatter
    must parse as a mapping, ``topic`` must equal the filename stem,
    ``title`` must be non-empty prose, ``surfaces`` a list of surface
    identifiers (the UI owns which exist, so they are not checked against a
    closed set) and ``order`` an optional int — surfaces and order are read
    from the source language's file, which every topic must have. Locale
    subdirectories are checked against ``locales(root)`` so a typo'd code
    stops generation instead of orphaning its prose, and a help directory
    that carries no topic file at all stops instead of registering an empty
    capability. A capability without a help directory is simply absent.
    Raise HelpScanError — a SystemExit — for every one of these.
    """
    help_dirs = {
        folder.name: folder / "web" / "help"
        for folder in sorted((root / "app" / "capabilities").iterdir())
        if (folder / "web" / "help").is_dir()
    }
    if not help_dirs:
        return ()
    for capability in help_dirs:
        if not _is_slug(capability):
            raise HelpScanError(
                f"app/capabilities/{capability}: capability id must be a"
                f" lowercase, hyphenated slug (was {capability!r})"
            )
    known = locales(root)
    capabilities: list[HelpCapability] = []
    for capability, help_dir in help_dirs.items():
        stray_files = sorted(path.name for path in help_dir.iterdir() if not path.is_dir())
        if stray_files:
            raise HelpScanError(
                f"{help_dir}: stray files in the help root must live under a"
                f" locale directory: {stray_files}"
            )
        strangers = sorted(
            path.name for path in help_dir.iterdir() if path.is_dir() and path.name not in known
        )
        if strangers:
            raise HelpScanError(
                f"{help_dir}: help for languages the central catalog does"
                f" not carry: {strangers} (the catalog carries {', '.join(known)})"
            )
        files: dict[str, dict[str, Path]] = {}
        for locale in known:
            for topic_file in sorted((help_dir / locale).glob("*.md")):
                files.setdefault(topic_file.stem, {})[locale] = topic_file
        if not files:
            raise HelpScanError(
                f"{help_dir}: help present but no source language — topics"
                f" live under locale directories ({', '.join(known)}), at"
                f" least {SOURCE_LOCALE}/"
            )
        topics: list[HelpTopic] = []
        for slug in sorted(files):
            if not _is_slug(slug):
                raise HelpScanError(
                    f"{help_dir}: topic slug {slug!r} must be a lowercase,"
                    f" hyphenated slug (a-z, 0-9, -)"
                )
            source = files[slug].get(SOURCE_LOCALE)
            if source is None:
                raise HelpScanError(
                    f"{help_dir}/{SOURCE_LOCALE}/{slug}.md is missing: every"
                    f" topic has an {SOURCE_LOCALE} file — it is the source language"
                )
            present = files[slug]
            ordered = [code for code in known if code in present]
            surfaces: tuple[str, ...] = ()
            order: int | None = None
            locale_data: list[HelpTopicLocale] = []
            for locale in ordered:
                frontmatter, body = _split_frontmatter(
                    present[locale], present[locale].read_text(encoding="utf-8")
                )
                unknown_fields = cast("set[str]", set(frontmatter)) - {
                    "topic",
                    "title",
                    "surfaces",
                    "order",
                }
                if unknown_fields:
                    raise HelpScanError(
                        f"{present[locale]}: unknown frontmatter fields"
                        f" {sorted(unknown_fields)} (allowed: topic, title, surfaces, order)"
                    )
                topic = frontmatter.get("topic")
                if topic != slug:
                    raise HelpScanError(
                        f"{present[locale]}: frontmatter topic {topic!r} must"
                        f" equal the filename stem {slug!r}"
                    )
                title = frontmatter.get("title")
                if not isinstance(title, str) or not title.strip():
                    raise HelpScanError(f"{present[locale]}: title must be a non-empty string")
                raw_surfaces = frontmatter.get("surfaces")
                if not isinstance(raw_surfaces, list) or not all(
                    isinstance(surface, str) for surface in cast("list[object]", raw_surfaces)
                ):
                    raise HelpScanError(
                        f"{present[locale]}: surfaces must be a list of surface identifiers"
                    )
                raw_order = frontmatter.get("order")
                if raw_order is not None and (
                    not isinstance(raw_order, int) or isinstance(raw_order, bool)
                ):
                    raise HelpScanError(f"{present[locale]}: order must be an int")
                if locale == SOURCE_LOCALE:
                    surfaces = tuple(cast("list[str]", raw_surfaces))
                    order = raw_order if isinstance(raw_order, int) else None
                locale_data.append(HelpTopicLocale(locale=locale, title=title, body=body))
            topics.append(
                HelpTopic(
                    capability=capability,
                    slug=slug,
                    surfaces=surfaces,
                    order=order,
                    locales=tuple(ordered),
                    locale_data=tuple(locale_data),
                )
            )
        capabilities.append(HelpCapability(capability=capability, topics=tuple(topics)))
    return tuple(capabilities)


# Topics without an explicit order sort after every ordered topic in their
# surface's list: 1000 sits far enough past any hand-written order that the
# two never interleave by accident.
HELP_ORDER_DEFAULT = 1000


def _ts_string(value: str) -> str:
    """One prose string as a TypeScript double-quoted literal, json-ish
    escaped: backslash and quote first, then the characters a multi-line
    YAML scalar could smuggle into a title."""
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def typescript_help(root: Path) -> str:
    """The web-side view: the help registry the UI resolves by surface.

    One group per topic, in scan order (capability id, then slug), keyed by
    the canonical ``<capability>.<slug>`` id. Each group carries every locale
    the topic exists in as a lazy ``?raw`` import — a topic's markdown body
    is fetched only when a reader asks for it, never bundled eagerly.
    ``helpFor`` does the locale resolution: the requested locale when the
    topic carries it, otherwise the source language with ``fallback`` set —
    a missing translation degrades to English, never to nothing. Groups and
    titles carry only what the scan already validated; the import paths are
    written as full literals because Vite resolves dynamic imports by
    pattern-matching the literal text.
    """
    scan = scan_help(root)
    groups = ""
    for capability in scan:
        for topic in capability.topics:
            entries = "".join(
                f"      {_ts_string(entry.locale)}: {{"
                f" title: {_ts_string(entry.title)},"
                f' load: () => import("../../../app/capabilities/{capability.capability}'
                f'/web/help/{entry.locale}/{topic.slug}.md?raw").then((m) => m.default) }},\n'
                for entry in topic.locale_data
            )
            surfaces = ", ".join(_ts_string(surface) for surface in topic.surfaces)
            order = topic.order if topic.order is not None else HELP_ORDER_DEFAULT
            groups += (
                "  {\n"
                f'    id: "{capability.capability}.{topic.slug}",\n'
                f'    capability: "{capability.capability}",\n'
                f'    topic: "{topic.slug}",\n'
                f"    surfaces: [{surfaces}],\n"
                f"    order: {order},\n"
                "    locales: {\n"
                f"{entries}"
                "    },\n"
                "  },\n"
            )
    table = (
        f"export const helpGroups: readonly HelpGroup[] = [\n{groups}];"
        if groups
        else "export const helpGroups: readonly HelpGroup[] = [];"
    )
    return (
        "// Generated by scripts/generate_capabilities.py from\n"
        "// app/capabilities/*/web/help/ — DO NOT EDIT.\n"
        "// The help registry: one group per topic, keyed by the canonical\n"
        "// <capability>.<slug> id. Bodies are lazy ?raw imports, and helpFor\n"
        "// resolves the requested locale, falling back to the source language\n"
        "// with fallback set where a topic has no translation in it. A new\n"
        "// topic appears here by existing, with zero generator changes.\n"
        "\n"
        "export interface HelpTopic {\n"
        "  id: string;\n"
        "  capability: string;\n"
        "  topic: string;\n"
        "  title: string;\n"
        "  surfaces: readonly string[];\n"
        "  locale: string;\n"
        "  fallback: boolean;\n"
        "  load: () => Promise<string>;\n"
        "}\n"
        "\n"
        "export interface HelpGroup {\n"
        "  id: string;\n"
        "  capability: string;\n"
        "  topic: string;\n"
        "  surfaces: readonly string[];\n"
        "  order: number;\n"
        "  locales: Record<string, { title: string; load: () => Promise<string> }>;\n"
        "}\n"
        "\n"
        f"{table}\n"
        "\n"
        "export function helpFor(surface: string, locale?: string): HelpTopic[] {\n"
        f'  const wanted = locale ?? "{SOURCE_LOCALE}";\n'
        "  return helpGroups\n"
        "    .filter((group) => group.surfaces.includes(surface))\n"
        "    .sort((a, b) => a.order - b.order\n"
        "      || (a.topic < b.topic ? -1 : a.topic > b.topic ? 1 : 0))\n"
        "    .map((group) => {\n"
        "      const localized = group.locales[wanted];\n"
        f'      const picked = localized ?? group.locales["{SOURCE_LOCALE}"];\n'
        "      return {\n"
        "        id: group.id,\n"
        "        capability: group.capability,\n"
        "        topic: group.topic,\n"
        "        title: picked.title,\n"
        "        surfaces: group.surfaces,\n"
        f'        locale: localized ? wanted : "{SOURCE_LOCALE}",\n'
        "        fallback: !localized,\n"
        "        load: picked.load,\n"
        "      };\n"
        "    });\n"
        "}\n"
    )


def help_coverage(root: Path) -> str:
    """The reader-side view: which capabilities ship help, in which languages.

    One ``## <capability>`` section per capability the help scan found, in
    scan order (alphabetical by id); its table is one row per topic (by
    slug) and one column per catalog locale in ``locales()`` order — a
    ``—`` marks a translation the topic does not carry yet. Every folder
    under ``app/capabilities/`` that holds a ``capability.yaml`` but no
    help the scan found closes the report as a plain list, so a reader
    sees at a glance where help is still missing entirely; with every
    capability covered, the list (and its heading) is absent.
    """
    capabilities = tuple(
        folder.name
        for folder in sorted((root / "app" / "capabilities").iterdir())
        if (folder / "capability.yaml").exists()
    )
    scan = scan_help(root)
    helped = {capability.capability for capability in scan}
    known = locales(root)
    columns = " | ".join(known)
    rule = " | ".join(["---"] * (len(known) + 1))
    blocks: list[str] = []
    for capability in scan:
        rows = "".join(
            f"| {topic.slug} | "
            + " | ".join("✓" if locale in topic.locales else "—" for locale in known)
            + " |\n"
            for topic in capability.topics
        )
        blocks.append(f"## {capability.capability}\n\n| Topic | {columns} |\n| {rule} |\n{rows}")
    # The debt list counts capabilities with a UI only: a capability whose
    # web/ directory is gone owes no help — it is absent from this report
    # entirely, not listed as missing.
    present = web_ids(root)
    missing = [name for name in capabilities if name not in helped and name in present]
    if missing:
        bullets = "".join(f"- {name}\n" for name in missing)
        blocks.append(f"## Capabilities without help\n\n{bullets}")
    return (
        "<!-- Generated by scripts/generate_capabilities.py from"
        " app/capabilities/*/web/help/ — DO NOT EDIT. -->\n"
        "<!-- A — marks a translation the topic does not carry yet."
        " Regenerate with `just generate`. -->\n"
        "\n"
        "# Help coverage\n"
        "\n"
        "One row per capability that ships help; capabilities without help are"
        " listed at the bottom.\n"
        "\n" + "\n".join(blocks)
    )


def workspace_route_id(sources: dict[str, str]) -> str | None:
    """The TanStack route id of the one capability that owns the workspace."""
    host = next(
        (name for name, text in sources.items() if "export const workspaceRoute" in text),
        None,
    )
    if host is None:
        return None
    source = sources[host]
    match = re.search(r'export const workspaceRouteId = "([^"]+)"', source)
    if match is None:
        raise SystemExit(
            f"app/capabilities/{host}/web/routes.tsx: the workspace route must"
            " export `workspaceRouteId` beside `workspaceRoute` — the shell's"
            " breakpoint reads the route id, and a path literal is not the"
            " same fact"
        )
    return match.group(1)


def typescript_workspace(root: Path) -> str:
    """The shell's workspace-route id, a leaf module so chrome imports no route table."""
    route_id = workspace_route_id(route_sources(root))
    value = "null" if route_id is None else f'"{route_id}"'
    return (
        "// Generated by scripts/generate_capabilities.py from"
        " app/capabilities/*/web/routes.tsx — DO NOT EDIT.\n"
        "// The workspace route id the shell compares against; a capability\n"
        "// that owns no workspace route leaves this null.\n"
        f"export const workspaceRouteId: string | null = {value};\n"
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
    # The settings convention, discovered by the same scan the registry view
    # reads: a capability exports ``settingsRoutes`` (factories that parent
    # pages at the one settings route) and exactly one exports
    # ``settingsRoute`` — the dock convention one level down in the URL
    # space. Nothing contributes until a capability exports, so the table
    # comes out unchanged until then.
    settings_found = scan_settings(sources)
    settings = tuple(page.id for page in settings_found.rows)
    settings_hosts = [settings_found.host] if settings_found.host is not None else []

    def import_names(capability: str) -> str:
        """Name the route exports this capability contributes to the composed table."""
        names = f"routes as {capability}"
        if capability in docks:
            names += f", dockRoutes as {capability}Docks"
        if docks and capability in hosts:
            names += ", workspaceRoute"
        if capability in settings:
            names += f", settingsRoutes as {capability}Settings"
        if settings and capability in settings_hosts:
            names += ", settingsRoute"
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
    settings_consts = "".join(
        f"const {capability}SettingsRoutes ="
        f" {capability}Settings.map((page) => page(settingsRoute));\n"
        for capability in settings
    )
    spread = "".join(f"  ...{capability},\n" for capability in found)
    dock_spread = (
        "".join(f"  ...{capability}DockRoutes,\n" for capability in docks) if docks else ""
    )
    settings_spread = (
        "".join(f"  ...{capability}SettingsRoutes,\n" for capability in settings)
        if settings
        else ""
    )
    dock_note = (
        "  //\n"
        "  // Dock children come after every capability's own routes: the router\n"
        "  // initializes a route from its parent, so the workspace route must be\n"
        "  // in the table before the dock routes parented at it.\n"
        if docks
        else ""
    )
    settings_note = (
        "  //\n"
        "  // Settings children come after every capability's own routes: the\n"
        "  // router initializes a route from its parent, so the settings route\n"
        "  // must be in the table before the settings routes parented at it.\n"
        if settings
        else ""
    )
    dock_block = f"{dock_consts}\n" if dock_consts else ""
    settings_block = f"{settings_consts}\n" if settings_consts else ""
    settings_header = (
        "//\n"
        "// Settings composition: a capability may export settingsRoutes —\n"
        "// factories that take the settings route and return child routes\n"
        "// for it — and exactly one capability exports settingsRoute,\n"
        "// mirroring the dock convention one level down in the URL space.\n"
        if settings
        else ""
    )
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
        f"{settings_header}"
        f"{imports}"
        "\n"
        f"{dock_block}{settings_block}"
        "export const capabilityRoutes = [\n"
        f"{spread}{dock_note}{dock_spread}{settings_note}{settings_spread}] as const;\n"
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
        "// title keys are checked against the merged English catalog by the compiler.\n"
        'import { catalogs } from "./catalogs";\n'
        "\n"
        f"{table} satisfies ReadonlyArray<{{\n"
        "  id: string;\n"
        "  path: string;\n"
        "  titleKey: keyof typeof catalogs.en;\n"
        "}>;\n"
    )


def typescript_settings_pages(root: Path) -> str:
    """The web-side view: the settings registry the settings hub renders its
    cluster list from."""
    scan = scan_settings(route_sources(root))
    rows = "".join(
        f'  {{ id: "{page.id}", path: "{page.path}", titleKey: "{page.title_key}" }},\n'
        for page in scan.rows
    )
    table = (
        f"export const settingsPages = [\n{rows}] as const"
        if rows
        else "export const settingsPages = [] as const"
    )
    return (
        "// Generated by scripts/generate_capabilities.py from"
        " app/capabilities/*/web/routes.tsx — DO NOT EDIT.\n"
        "// The settings registry: one row per capability that exports\n"
        "// settingsRoutes, sorted — the settings hub renders one cluster per\n"
        "// row and navigates to the row's path. A new cluster appears here by\n"
        "// adding its settingsRoutes, with zero generator changes.\n"
        "//\n"
        "// as const, no annotation: the literal path carries each row's route\n"
        "// into the cluster's `to=` (a drifted row is a build error), and the\n"
        "// title keys are checked against the merged English catalog by the compiler.\n"
        'import { catalogs } from "./catalogs";\n'
        "\n"
        f"{table} satisfies ReadonlyArray<{{\n"
        "  id: string;\n"
        "  path: string;\n"
        "  titleKey: keyof typeof catalogs.en;\n"
        "}>;\n"
    )


# The palette's row order: a deliberate arrangement, not the folder sort.
# Writing leads (the editor's own commands first), then the app-wide
# surfaces. A command module outside this order stops generation instead of
# silently sliding to the end of the aggregation.
COMMAND_ORDER = ("writing", "settings", "prompts", "knowledge", "planning")


def scan_commands(root: Path) -> tuple[str, ...]:
    """The commands convention, discovered from the capability folders.

    The file's presence is the contract — ``app/capabilities/<id>/web/
    commands.ts(x)``, the same convention as ``web/routes.tsx`` — and, like
    the dock scan, discovery reads no contents: a commands file that never
    exports ``commands`` is not caught here, it surfaces as a build error at
    the generated import instead of a silently wrong registry row. Raise
    SystemExit for a capability holding both ``commands.ts`` and
    ``commands.tsx`` (the generated import is extension-less, so which one
    defines the commands would be ambiguous) and for a module outside
    ``COMMAND_ORDER`` — the palette's row order is an arrangement someone
    decided, and the generator does not extend it on its own.
    """
    found: set[str] = set()
    for folder in sorted((root / "app" / "capabilities").iterdir()):
        ts = folder / "web" / "commands.ts"
        tsx = folder / "web" / "commands.tsx"
        if ts.is_file() and tsx.is_file():
            raise SystemExit(
                f"app/capabilities/{folder.name}/web has commands.ts and"
                " commands.tsx; the generated import is extension-less, so"
                " which one defines the capability's commands is ambiguous"
                " — keep one"
            )
        if ts.is_file() or tsx.is_file():
            found.add(folder.name)
    strangers = sorted(found - set(COMMAND_ORDER))
    if strangers:
        raise SystemExit(
            f"{strangers} own command modules but sit outside the palette's"
            f" row order {list(COMMAND_ORDER)} — the order is a deliberate"
            " arrangement, so generation stops instead of appending:"
            " extend COMMAND_ORDER in scripts/generate_capabilities.py"
        )
    return tuple(capability for capability in COMMAND_ORDER if capability in found)


def typescript_commands(root: Path) -> str:
    """The web-side view: the command registry the palette renders and filters."""
    found = scan_commands(root)
    imports = "".join(
        f"import {{ commands as {capability}Commands }} from"
        f' "../../../app/capabilities/{capability}/web/commands";\n'
        for capability in found
    )
    spread = "".join(f"  ...{capability}Commands,\n" for capability in found)
    if not found:
        # No capability owns a commands module: the registry comes out empty
        # and carries no Command import either — the type's home module is
        # shell code that exists only while a palette reads it.
        return (
            "// Generated by scripts/generate_capabilities.py from"
            " app/capabilities/*/web/commands.ts(x) — DO NOT EDIT.\n"
            "// The command registry: one import per capability that owns a\n"
            "// commands module, aggregated in the palette's pinned row order\n"
            "// (COMMAND_ORDER in scripts/generate_capabilities.py). A new\n"
            "// command appears by existing; a capability outside the pinned\n"
            "// order stops generation instead of appending to it.\n"
            "\n"
            "export const commands = [] as const;\n"
        )
    table = f"export const commands = [\n{spread}] as const"
    return (
        "// Generated by scripts/generate_capabilities.py from"
        " app/capabilities/*/web/commands.ts(x) — DO NOT EDIT.\n"
        "// The command registry: one import per capability that owns a\n"
        "// commands module, aggregated in the palette's pinned row order\n"
        "// (writing, settings, prompts, knowledge, planning — COMMAND_ORDER in\n"
        "// scripts/generate_capabilities.py). A new command appears by\n"
        "// existing; a capability outside the pinned order stops generation\n"
        "// instead of appending to it.\n"
        "//\n"
        "// as const, no annotation: the rows keep their literal shape, and\n"
        "// the satisfies checks every row against Command — a titleKey\n"
        "// missing from the English catalog is a build error here.\n"
        'import type { Command } from "../commands";\n'
        "\n"
        f"{imports}\n"
        f"{table} satisfies ReadonlyArray<Command>;\n"
    )


def typescript_structures(root: Path, loaded: dict[str, dict[str, str]]) -> str:
    """The web-side view: the storyboard structure registry the switcher offers.

    The registry is the storyboard capability's UI contribution, so the
    one rule applies through ``STRUCTURES_OWNER``: rows are emitted only
    while that capability owns a ``web/`` directory. Without it the
    switcher is gone and the table comes out empty; the backend registry
    ``STRUCTURES`` is untouched either way.
    """
    rows = ""
    if STRUCTURES_OWNER in web_ids(root):
        for structure_id in sorted(STRUCTURES):
            title_key = f"storyboard.structure.{structure_id}"
            if title_key not in loaded[SOURCE_LOCALE]:
                raise SystemExit(
                    f"app/capabilities/planning/structures.py: structure {structure_id!r}"
                    f" has no {title_key!r} in the merged {SOURCE_LOCALE} catalog"
                )
        rows = "".join(
            f'  {{ id: "{structure_id}", titleKey: "storyboard.structure.{structure_id}" }},\n'
            for structure_id in sorted(STRUCTURES)
        )
    table = (
        f"export const structures = [\n{rows}] as const"
        if rows
        else "export const structures = [] as const"
    )
    return (
        "// Generated by scripts/generate_capabilities.py from"
        " app/capabilities/planning/structures.py — DO NOT EDIT.\n"
        "// The storyboard structure registry: one row per structure in the\n"
        "// backend registry, sorted — the switcher offers one option per row.\n"
        "// A new structure appears here by existing, with zero switcher edits.\n"
        "//\n"
        "// as const, no annotation: the title keys are checked against the\n"
        "// merged English catalog by the compiler, so a missing i18n key\n"
        "// fails the build.\n"
        'import { catalogs } from "./catalogs";\n'
        "\n"
        f"{table} satisfies ReadonlyArray<{{\n"
        "  id: string;\n"
        "  titleKey: keyof typeof catalogs.en;\n"
        "}>;\n"
    )


def docs_index(
    entries: tuple[Facts, ...],
    known: tuple[str, ...],
    loaded: dict[str, dict[str, str]],
    root: Path,
) -> str:
    """The reader-side view: one row per UI capability per locale.

    The rows come from ``ui_facts``: a capability without a ``web/``
    directory has no row, and neither has an interim page whose facts
    title the catalog does not resolve — the table waits for the rebuilt
    screens to carry a title key again.
    """
    entries = ui_facts(entries, root, loaded)
    sections: list[str] = []
    for locale in known:
        catalog = loaded[locale]
        capability = catalog["docs.table.capability"]
        path_column = catalog["docs.table.path"]
        nav_column = catalog["docs.table.nav"]
        needs_column = catalog["docs.table.needs"]
        rows = "".join(
            f"| {catalog[entry.title]} | {entry.path} | "
            + ("✓" if entry.nav else "—")
            + " | "
            + (", ".join(catalog[f"needs.{need}"] for need in entry.needs) or "—")
            + " |\n"
            for entry in entries
        )
        sections.append(
            f"## {catalog['locale.name']}\n\n"
            f"| {capability} | {path_column} | {nav_column} | {needs_column} |\n"
            "| --- | --- | --- | --- |\n" + rows
        )
    return (
        "<!-- Generated by scripts/generate_capabilities.py from"
        " app/capabilities/*/capability.yaml — DO NOT EDIT. -->\n"
        "<!-- Titles and table words come from the merged catalogs."
        " Regenerate with `just generate`. -->\n"
        "\n"
        "# Narrare — the app's surfaces\n"
        "\n"
        "One row per capability with a UI, from each capability's facts file. Long-form user\n"
        "documentation grows around this index, never inside it.\n"
        "\n" + "\n".join(sections)
    )


def typescript_demos(root: Path) -> str:
    rows: list[str] = []
    for info in KERNEL_DEMOS:
        archive = parse_archive(demo_tree(info.slug))
        rows.append(
            "  { "
            f"slug: {_ts_string(info.slug)}, "
            f"title: {_ts_string(info.title)}, "
            f"language: {_ts_string(info.language)}, "
            f"genre: {_ts_string(archive.genre or '')}, "
            f"blurb: {_ts_string(archive.blurb or '')}, "
            f"chapters: {len(archive.chapters)}, "
            f"entities: {len(archive.entities)} "
            "},"
        )
    body = "\n".join(rows)
    return (
        "// Generated by scripts/generate_capabilities.py from"
        " app/kernel/interchange/demos.py and the bundled archives — DO NOT EDIT.\n"
        "// The setup page's demo picker reads this; a demo added to the corpus\n"
        "// appears here on the next `just generate`.\n"
        "\n"
        "export const demos = [\n"
        f"{body}\n"
        "] as const;\n"
    )


def main() -> None:
    """Validate capability inputs and overwrite the fourteen views from the current directory.

    Validation may raise SystemExit; file and parse errors propagate. Parent
    directories are created as needed when writing the views.
    """
    root = Path(".")
    known = locales(root)
    loaded = catalogs(root, known)
    overlays = overlay_sources(root, known, loaded)
    loaded_facts: tuple[Facts, ...] = facts(root)
    outputs: dict[str, str] = {
        "app/generated/capabilities.py": python_registry(loaded_facts),
        "app/generated/locales.py": python_locales(known),
        "web/lib/generated/capabilities.ts": typescript_nav(ui_facts(loaded_facts, root, loaded)),
        "web/lib/generated/catalogs.ts": typescript_catalogs(root, known),
        "web/lib/generated/overlays.ts": typescript_overlays(known, overlays),
        "web/lib/generated/routes.ts": typescript_routes(root),
        "web/lib/generated/workspace.ts": typescript_workspace(root),
        "web/lib/generated/docks.ts": typescript_docks(root),
        "web/lib/generated/settingsPages.ts": typescript_settings_pages(root),
        "web/lib/generated/commands.ts": typescript_commands(root),
        "web/lib/generated/structures.ts": typescript_structures(root, loaded),
        "web/lib/generated/help.ts": typescript_help(root),
        "web/lib/generated/demos.ts": typescript_demos(root),
        "docs/user/INDEX.md": docs_index(loaded_facts, known, loaded, root),
        "docs/user/help-coverage.md": help_coverage(root),
    }
    for target, content in outputs.items():
        path = root / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {target}")


if __name__ == "__main__":
    main()
