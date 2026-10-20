from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from scripts.scaffold_feature import EXISTING_ID_EXIT, scaffold_feature

if TYPE_CHECKING:
    from pathlib import Path

LAYERS = ("core", "api", "web")


def test_scaffolds_feature_doc_tests_contract_and_report_stub(tmp_path: Path) -> None:
    written = scaffold_feature("FIND-099", LAYERS, tmp_path)
    rel = {p.relative_to(tmp_path).as_posix() for p in written}
    assert any(p.startswith("docs/features/") and p.endswith("FIND-099.md") for p in rel)
    assert any(p.startswith("tests/unit/core/") for p in rel)
    assert any(p.startswith("tests/unit/api/") for p in rel)
    assert any(
        p.startswith("packages/core/narrare_core/") and p.endswith("contracts.py") for p in rel
    )
    assert any(p.startswith("docs/superpowers/plans/reports/") for p in rel)


def test_never_generates_service_router_or_component_files(tmp_path: Path) -> None:
    written = {p.name for p in scaffold_feature("FIND-099", LAYERS, tmp_path)}
    assert not written & {"service.py", "router.py", "repository.py"}


def test_project_language_is_english(tmp_path: Path) -> None:
    for path in scaffold_feature("FIND-099", LAYERS, tmp_path):
        assert "TODO" not in path.read_text(encoding="utf-8")


def test_refuses_a_feature_id_that_already_exists(tmp_path: Path) -> None:
    scaffold_feature("FIND-099", ("core",), tmp_path)
    with pytest.raises(SystemExit) as exc:
        scaffold_feature("FIND-099", ("core",), tmp_path)
    assert exc.value.code == EXISTING_ID_EXIT


def test_core_only_layer_writes_no_api_or_web_skeleton(tmp_path: Path) -> None:
    written = scaffold_feature("FIND-100", ("core",), tmp_path)
    rel = {p.relative_to(tmp_path).as_posix() for p in written}
    assert any(p.startswith("tests/unit/core/") for p in rel)
    assert not any(p.startswith("tests/unit/api/") for p in rel)
    assert not any(p.startswith("tests/unit/web/") for p in rel)


def test_api_only_layer_writes_no_contract_stub(tmp_path: Path) -> None:
    written = scaffold_feature("FIND-101", ("api",), tmp_path)
    rel = {p.relative_to(tmp_path).as_posix() for p in written}
    assert any(p.startswith("tests/unit/api/") for p in rel)
    assert not any(p.endswith("contracts.py") for p in rel)
    assert not any(p.startswith("packages/core/") for p in rel)
