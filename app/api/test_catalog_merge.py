"""The catalog merge: central shared text plus each capability's own file.

The language set is still discovered from `i18n/*.json`; a capability that
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
    overlay_sources,
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

    assert 'import pt_BR_central from "../../../i18n/pt-BR.json";' in generated
    assert "const pt_BR_merged = {\n  ...pt_BR_central,\n  ...pt_BR_demo,\n};" in generated
    assert '  "pt-BR": pt_BR_merged,' in generated


def test_an_overlay_key_must_exist_in_the_catalog(tmp_path: Path) -> None:
    write_catalog(tmp_path / "i18n/en.json", {"app.title": "App"})
    write_catalog(tmp_path / "i18n/de.json", {"app.title": "App"})
    write_catalog(
        tmp_path / "i18n/overlays/formality/de.json",
        {"unknown.key": "Nicht im Katalog"},
        required=False,
    )

    with pytest.raises(SystemExit, match=re.escape("unknown.key")):
        overlay_sources(tmp_path, ("en", "de"), catalogs(tmp_path, ("en", "de")))


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
