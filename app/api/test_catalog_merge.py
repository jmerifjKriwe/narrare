"""The catalog merge: central shared text plus each capability's own file.

The language set comes from `i18n/registry/locales.json`; a capability that
carries an `i18n` directory must carry every one of those languages. The
merge refuses an unsorted file and a key defined twice, naming the files, so
the failure points at the edit rather than at a blank label later.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import pytest

from scripts.generate_capabilities import (
    catalog_sources,
    catalogs,
    lazy_catalog_outputs,
    locales,
    overlay_sources,
    registry_locales,
    typescript_catalogs,
    typescript_overlays,
)

if TYPE_CHECKING:
    from pathlib import Path

REQUIRED = {
    "locale.name": "English",
    "docs.table.capability": "Capability",
    "docs.table.nav": "Navigation",
    "docs.table.path": "Path",
    "docs.table.needs": "Needs",
    "needs.llm": "LLM",
    "needs.embeddings": "Embeddings",
}


def write_catalog(path: Path, extra: dict[str, str], *, required: bool = True) -> None:
    """Write a sorted catalog; the shared one carries the generated views' keys."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {**(REQUIRED if required else {}), **extra}
    path.write_text(json.dumps(dict(sorted(data.items())), indent=2) + "\n", encoding="utf-8")


def write_registry(path: Path, languages: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"locales": languages}) + "\n", encoding="utf-8")


def test_the_registry_orders_the_languages_and_the_source_leads_the_views(tmp_path: Path) -> None:
    write_registry(tmp_path / "i18n/registry/locales.json", ["de", "en", "fr"])
    for code in ("de", "en", "fr"):
        write_catalog(tmp_path / f"i18n/{code}.json", {"app.title": code})

    assert registry_locales(tmp_path) == ("de", "en", "fr")
    assert locales(tmp_path) == ("en", "de", "fr")
    typescript = typescript_catalogs(tmp_path, ("en", "de", "fr"), ("de", "en", "fr"))
    assert 'export const locales = ["en", "de", "fr"] as const;' in typescript
    assert 'export const localeOrder = ["de", "en", "fr"] as const' in typescript


@pytest.mark.parametrize(
    "code",
    [
        "en_US",
        "x",
        "de-",
        "zh hans",
        f"de-{'a' * 9}",
        "de-" + "-".join(["abcdefgh"] * 8),
    ],
)
def test_a_malformed_registry_code_stops_generation(tmp_path: Path, code: str) -> None:
    write_registry(tmp_path / "i18n/registry/locales.json", ["en", code])
    # Both catalogs exist so parity cannot raise: only the tag check can.
    write_catalog(tmp_path / "i18n/en.json", {"app.title": "en"})
    write_catalog(tmp_path / f"i18n/{code}.json", {"app.title": code})
    with pytest.raises(SystemExit, match=re.escape(code[:10])):
        locales(tmp_path)


def test_a_registry_without_the_source_locale_stops_generation(tmp_path: Path) -> None:
    write_registry(tmp_path / "i18n/registry/locales.json", ["de", "fr"])
    with pytest.raises(SystemExit, match="source locale"):
        locales(tmp_path)


def test_a_duplicate_registry_entry_stops_generation(tmp_path: Path) -> None:
    write_registry(tmp_path / "i18n/registry/locales.json", ["de", "en", "de"])
    with pytest.raises(SystemExit, match="twice"):
        locales(tmp_path)


def test_a_registry_entry_without_a_catalog_stops_generation(tmp_path: Path) -> None:
    write_registry(tmp_path / "i18n/registry/locales.json", ["de", "en", "fr"])
    for code in ("de", "en"):
        write_catalog(tmp_path / f"i18n/{code}.json", {"app.title": code})
    with pytest.raises(SystemExit, match=re.escape("i18n/fr.json")):
        locales(tmp_path)


def test_a_catalog_outside_the_registry_stops_generation(tmp_path: Path) -> None:
    write_registry(tmp_path / "i18n/registry/locales.json", ["de", "en"])
    for code in ("de", "en", "fr"):
        write_catalog(tmp_path / f"i18n/{code}.json", {"app.title": code})
    with pytest.raises(SystemExit, match=re.escape("i18n/fr.json")):
        locales(tmp_path)


def test_a_missing_registry_file_stops_generation(tmp_path: Path) -> None:
    source = tmp_path / "i18n/registry/locales.json"
    with pytest.raises(SystemExit, match=re.escape(f"{source} is missing")):
        registry_locales(tmp_path)


def test_a_registry_that_is_not_json_stops_generation(tmp_path: Path) -> None:
    source = tmp_path / "i18n/registry/locales.json"
    source.parent.mkdir(parents=True)
    source.write_text("{not json\n", encoding="utf-8")
    with pytest.raises(SystemExit, match=re.escape(f"{source}: not valid JSON")):
        registry_locales(tmp_path)


@pytest.mark.parametrize(
    "payload",
    ("[]\n", '{"languages": ["en"]}\n', '{"locales": ["en"], "extra": true}\n'),
    ids=("a-list", "another-key", "a-second-key"),
)
def test_a_registry_that_is_not_one_object_with_one_key_stops_generation(
    tmp_path: Path, payload: str
) -> None:
    source = tmp_path / "i18n/registry/locales.json"
    source.parent.mkdir(parents=True)
    source.write_text(payload, encoding="utf-8")
    message = f"{source}: the registry is one object with one `locales` list"
    with pytest.raises(SystemExit, match=re.escape(message)):
        registry_locales(tmp_path)


def test_a_registry_whose_locales_is_not_a_list_stops_generation(tmp_path: Path) -> None:
    source = tmp_path / "i18n/registry/locales.json"
    source.parent.mkdir(parents=True)
    source.write_text('{"locales": "en"}\n', encoding="utf-8")
    message = f"{source}: `locales` is a list of language codes"
    with pytest.raises(SystemExit, match=re.escape(message)):
        registry_locales(tmp_path)


def test_a_registry_with_a_non_string_code_stops_generation(tmp_path: Path) -> None:
    source = tmp_path / "i18n/registry/locales.json"
    source.parent.mkdir(parents=True)
    source.write_text('{"locales": ["en", 3]}\n', encoding="utf-8")
    message = f"{source}: `locales` is a list of language codes"
    with pytest.raises(SystemExit, match=re.escape(message)):
        registry_locales(tmp_path)


def test_catalogs_merge_the_central_and_capability_files(tmp_path: Path) -> None:
    write_catalog(tmp_path / "i18n/en.json", {"app.title": "App"})
    write_catalog(
        tmp_path / "app/capabilities/demo/web/i18n/en.json",
        {"demo.heading": "Demo"},
        required=False,
    )

    merged = catalogs(tmp_path, ("en",))

    assert merged["en"]["app.title"] == "App"
    assert merged["en"]["demo.heading"] == "Demo"
    assert merged["en"]["locale.name"] == "English"


def test_every_locale_carries_the_same_keys(tmp_path: Path) -> None:
    write_catalog(tmp_path / "i18n/en.json", {"app.title": "App"})
    write_catalog(tmp_path / "i18n/de.json", {"app.extra": "Extra"})

    with pytest.raises(SystemExit) as raised:
        catalogs(tmp_path, ("en", "de"))

    message = str(raised.value)
    assert "de" in message
    assert "app.title" in message
    assert "app.extra" in message


def test_an_unsorted_catalog_is_refused_naming_the_file(tmp_path: Path) -> None:
    source = tmp_path / "i18n/en.json"
    source.parent.mkdir()
    source.write_text('{"b": "B", "a": "A"}\n', encoding="utf-8")

    with pytest.raises(SystemExit, match=f"{re.escape(str(source))}.*sorted"):
        catalogs(tmp_path, ("en",))


def test_a_key_defined_twice_is_refused_naming_both_files(tmp_path: Path) -> None:
    central = tmp_path / "i18n/en.json"
    capability = tmp_path / "app/capabilities/demo/web/i18n/en.json"
    write_catalog(central, {"demo.heading": "Central"})
    write_catalog(capability, {"demo.heading": "Capability"}, required=False)

    with pytest.raises(
        SystemExit,
        match=f"{re.escape(str(central))}.*{re.escape(str(capability))}"
        f"|{re.escape(str(capability))}.*{re.escape(str(central))}",
    ):
        catalogs(tmp_path, ("en",))


def test_a_capability_with_an_i18n_dir_carries_every_locale(tmp_path: Path) -> None:
    write_catalog(tmp_path / "i18n/en.json", {"app.title": "App"})
    write_catalog(tmp_path / "i18n/de.json", {"app.title": "App"})
    write_catalog(
        tmp_path / "app/capabilities/demo/web/i18n/en.json",
        {"demo.heading": "Demo"},
        required=False,
    )

    with pytest.raises(SystemExit, match=re.escape("de.json")):
        catalog_sources(tmp_path, ("en", "de"))


def test_a_capability_catalog_for_an_unknown_language_is_refused(
    tmp_path: Path,
) -> None:
    write_catalog(tmp_path / "i18n/en.json", {"app.title": "App"})
    write_catalog(
        tmp_path / "app/capabilities/demo/web/i18n/en.json",
        {"demo.heading": "Demo"},
        required=False,
    )
    write_catalog(
        tmp_path / "app/capabilities/demo/web/i18n/es.json",
        {"demo.heading": "Demostración"},
        required=False,
    )

    with pytest.raises(SystemExit, match="es"):
        catalog_sources(tmp_path, ("en",))


def test_a_hyphenated_locale_becomes_a_valid_identifier(tmp_path: Path) -> None:
    write_catalog(tmp_path / "i18n/en.json", {"app.title": "App"})
    write_catalog(tmp_path / "i18n/pt-BR.json", {"app.title": "App"})
    write_catalog(
        tmp_path / "app/capabilities/demo/web/i18n/en.json",
        {"demo.heading": "Demo"},
        required=False,
    )
    write_catalog(
        tmp_path / "app/capabilities/demo/web/i18n/pt-BR.json",
        {"demo.heading": "Demo"},
        required=False,
    )

    generated = typescript_catalogs(tmp_path, ("en", "pt-BR"))

    # Only the source is eager now; the hyphenated code keeps its valid
    # identifier in the loader map, and its merged catalog is a lazy module.
    assert 'import pt_BR_central from "../../../i18n/pt-BR.json";' not in generated
    assert "pt_BR_merged" not in generated
    assert '"pt-BR": () => import("./catalogs/pt_BR"),' in generated
    eager = 'export const catalogs = { en: en_merged } as const satisfies Record<"en", Catalog>;'
    assert eager in generated


def test_every_other_language_is_one_lazy_module(tmp_path: Path) -> None:
    for code in ("en", "de", "pt-BR"):
        write_catalog(tmp_path / f"i18n/{code}.json", {"locale.name": code, "app.title": code})
    outputs = lazy_catalog_outputs(tmp_path, ("en", "de", "pt-BR"))
    assert set(outputs) == {
        "web/lib/generated/catalogs/de.ts",
        "web/lib/generated/catalogs/pt_BR.ts",
    }
    module = outputs["web/lib/generated/catalogs/pt_BR.ts"]
    assert 'export const locale = "pt-BR" as const;' in module
    assert "export default pt_BR_merged satisfies Catalog;" in module


def test_the_loader_map_names_every_other_language_once(tmp_path: Path) -> None:
    for code in ("en", "de", "pt-BR"):
        write_catalog(tmp_path / f"i18n/{code}.json", {"app.title": code})
    typescript = typescript_catalogs(tmp_path, ("en", "de", "pt-BR"), ("de", "en", "pt-BR"))
    assert 'de: () => import("./catalogs/de"),' in typescript
    assert '"pt-BR": () => import("./catalogs/pt_BR"),' in typescript
    assert 'import("./catalogs/en")' not in typescript


def test_an_overlay_key_whose_base_is_gone_stops_generation(tmp_path: Path) -> None:
    # A variant whose base string the merged catalog does not carry is a
    # typo or dead copy — it would fall through to the base silently, so
    # the scan stops generation naming the keys instead. The demolition
    # interim skipped them while the shared-catalog cleanup was pending;
    # the cleanup landed, and the raise returned with the first suite.
    write_catalog(tmp_path / "i18n/en.json", {"app.title": "App"})
    write_catalog(tmp_path / "i18n/de.json", {"app.title": "App"})
    write_catalog(
        tmp_path / "i18n/overlays/formality/de.json",
        {"unknown.key": "Nicht im Katalog"},
        required=False,
    )

    with pytest.raises(SystemExit, match="keys not in the de catalog"):
        overlay_sources(tmp_path, ("en", "de"), catalogs(tmp_path, ("en", "de")))


def test_an_empty_overlay_file_emits_no_entry(tmp_path: Path) -> None:
    # An overlay file with no variants is not an error and not an import:
    # the locale simply carries no formal register yet.
    write_catalog(tmp_path / "i18n/en.json", {"app.title": "App"})
    write_catalog(tmp_path / "i18n/de.json", {"app.title": "App"})
    write_catalog(tmp_path / "i18n/overlays/formality/de.json", {}, required=False)

    overlays = overlay_sources(tmp_path, ("en", "de"), catalogs(tmp_path, ("en", "de")))
    assert overlays == {}


def test_a_live_overlay_key_survives_the_scan(tmp_path: Path) -> None:
    # The check names dead keys, not live ones: a variant whose base the
    # merged catalog still resolves stays in the overlay.
    write_catalog(tmp_path / "i18n/en.json", {"app.title": "App"})
    write_catalog(tmp_path / "i18n/de.json", {"app.title": "App"})
    write_catalog(
        tmp_path / "i18n/overlays/formality/de.json",
        {"app.title": "Sehr geehrte Anwendung"},
        required=False,
    )

    overlays = overlay_sources(tmp_path, ("en", "de"), catalogs(tmp_path, ("en", "de")))
    assert overlays["de"] == {"app.title": "Sehr geehrte Anwendung"}


def test_an_english_overlay_is_refused(tmp_path: Path) -> None:
    write_catalog(tmp_path / "i18n/en.json", {"app.title": "App"})
    write_catalog(
        tmp_path / "i18n/overlays/formality/en.json",
        {"app.title": "App"},
        required=False,
    )

    with pytest.raises(SystemExit, match="source locale"):
        overlay_sources(tmp_path, ("en",), catalogs(tmp_path, ("en",)))


def test_an_overlay_for_an_unknown_language_is_refused(tmp_path: Path) -> None:
    write_catalog(tmp_path / "i18n/en.json", {"app.title": "App"})
    write_catalog(
        tmp_path / "i18n/overlays/formality/es.json",
        {"app.title": "App"},
        required=False,
    )

    with pytest.raises(SystemExit, match="es"):
        overlay_sources(tmp_path, ("en",), catalogs(tmp_path, ("en",)))


def test_the_overlay_generator_emits_a_sparse_map(tmp_path: Path) -> None:
    write_catalog(tmp_path / "i18n/en.json", {"app.title": "App"})
    write_catalog(tmp_path / "i18n/de.json", {"app.title": "App"})
    write_catalog(
        tmp_path / "i18n/overlays/formality/de.json",
        {"app.title": "Anwendung"},
        required=False,
    )
    overlays = overlay_sources(tmp_path, ("en", "de"), catalogs(tmp_path, ("en", "de")))

    generated = typescript_overlays(("en", "de"), overlays)

    assert 'import de_overlay from "../../../i18n/overlays/formality/de.json";' in generated
    assert '  "de": de_overlay,' in generated
    assert '"en"' not in generated
