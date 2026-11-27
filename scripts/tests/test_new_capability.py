"""The scaffolder derives its languages from the registry, not from filenames.

``new_capability`` writes one catalog per language the generator's ``locales()``
returns. A central catalog the registry does not list is the tree
``registry_locales`` refuses, so the scaffolder stops naming it instead of
scaffolding a language the registry never declared.
"""

import json
import re
import sys
from typing import TYPE_CHECKING

import pytest

from scripts import new_capability

if TYPE_CHECKING:
    from pathlib import Path


def _root(tmp_path: Path) -> Path:
    """A repo root whose registry lists en, de and fr, plus an unregistered it."""
    i18n = tmp_path / "i18n"
    i18n.mkdir()
    for code in ("en", "de", "fr"):
        (i18n / f"{code}.json").write_text("{}", encoding="utf-8")
    (i18n / "it.json").write_text("{}", encoding="utf-8")
    registry = i18n / "registry" / "locales.json"
    registry.parent.mkdir()
    registry.write_text(json.dumps({"locales": ["de", "en", "fr"]}) + "\n", encoding="utf-8")
    return tmp_path


def _consistent_root(tmp_path: Path) -> Path:
    """A repo root whose registry and central catalogs agree, source language first."""
    i18n = tmp_path / "i18n"
    i18n.mkdir()
    for code in ("en", "de", "fr"):
        (i18n / f"{code}.json").write_text("{}", encoding="utf-8")
    registry = i18n / "registry" / "locales.json"
    registry.parent.mkdir()
    registry.write_text(json.dumps({"locales": ["en", "de", "fr"]}) + "\n", encoding="utf-8")
    return tmp_path


def test_scaffolder_writes_one_catalog_per_registry_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _consistent_root(tmp_path)
    registry = json.loads((root / "i18n" / "registry" / "locales.json").read_text(encoding="utf-8"))
    declared: list[str] = registry["locales"]
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "argv", ["new_capability", "notes"])

    new_capability.main()

    catalog_dir = root / "app" / "capabilities" / "notes" / "web" / "i18n"
    assert {path.stem for path in catalog_dir.glob("*.json")} == set(declared)
    # `main()` prints the languages it wrote in `locales()` order — the source
    # language first, then the registry's declared order. This fixture declares
    # the source first, so the two orders coincide and the assertion can read
    # the expected value from the registry file.
    out = capsys.readouterr().out
    printed = next(line for line in out.splitlines() if line.startswith("next: translate"))
    assert printed == f"next: translate web/i18n/{{{', '.join(declared)}}}.json, then"


def test_scaffolder_uses_the_registry_not_the_filenames(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "argv", ["new_capability", "notes"])

    # At base the scaffolder globbed i18n/*.json and wrote an it catalog. The
    # registry names three languages, so the tree the generator refuses stops
    # it here, naming the registry and the catalog it does not list; no
    # catalog is written for the unregistered language.
    message = "central catalogs the registry does not list: ['i18n/it.json']"
    with pytest.raises(SystemExit, match=re.escape(message)):
        new_capability.main()

    catalog_dir = root / "app" / "capabilities" / "notes" / "web" / "i18n"
    assert not list(catalog_dir.glob("*.json"))
