"""Tests for RULE-10 target derivation in ``scripts/_coverage_model.py``.

RULE-10 (docs/_shared/CONSTRAINTS.md): "Minimum coverage for `core/`
modules: **90%**. Minimum coverage for `apps/api/` modules: **80%**."
On top of that, the project holds the ``core/llm/`` and ``core/prompts/``
trees to a stricter 95% minimum (tests/AGENTS.md coverage table).

Targets are DERIVED from the package's source-root classification via
``rule10_target``; ``RULE10_OVERRIDES`` only holds entries that genuinely
differ from the derived default. Regression background (C4 investigation
2026-08-17): the former static ``RULE10_TARGETS`` dict silently held
unmapped core packages (``llm.intents``, ``context.integration_contracts``,
``agents.capabilities``) to the api floor of 80.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

# Ensure scripts/ is on sys.path for the ``_coverage_model`` import.
_SCRIPTS = str(Path(__file__).resolve().parent.parent.parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import _coverage_model  # noqa: E402  # type: ignore[import-untyped]
from _coverage_model import (  # noqa: E402  # type: ignore[import-untyped]
    parse_coverage_xml,
    rule10_target,
)


def _map_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    core_tops: tuple[str, ...] = (),
    api_tops: tuple[str, ...] = (),
) -> None:
    """Point the model's source roots at per-test tmp directories.

    Creates one sub-directory per given top-level package name under a
    synthetic core/api root and monkeypatches ``_CORE_ROOT``/``_API_ROOT``.
    """
    core_root = tmp_path / "core"
    api_root = tmp_path / "api"
    core_root.mkdir()
    api_root.mkdir()
    for top in core_tops:
        (core_root / top).mkdir()
    for top in api_tops:
        (api_root / top).mkdir()
    monkeypatch.setattr(_coverage_model, "_CORE_ROOT", core_root)
    monkeypatch.setattr(_coverage_model, "_API_ROOT", api_root)


def _write_coverage_xml(tmp_path: Path, packages: dict[str, float]) -> Path:
    """Write a minimal coverage.xml with one <package> per entry."""
    lines = ["<coverage>", "<packages>"]
    for name, rate in packages.items():
        lines.append(f'<package name="{name}" line-rate="{rate}"/>')
    lines.extend(["</packages>", "</coverage>"])
    path = tmp_path / "coverage.xml"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


class TestDerivedTargets:
    """``rule10_target`` derives the per-root policy, no static lookup."""

    def test_core_package_derives_90(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _map_roots(monkeypatch, tmp_path, core_tops=("widgets",))
        assert rule10_target("widgets") == 90
        assert rule10_target("widgets.sub") == 90

    def test_core_llm_tree_derives_95(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _map_roots(monkeypatch, tmp_path, core_tops=("llm",))
        assert rule10_target("llm") == 95
        assert rule10_target("llm.intents") == 95
        assert rule10_target("llm._providers") == 95

    def test_core_prompts_tree_derives_95_even_when_shared(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """``prompts`` exists under BOTH roots; the flattened coverage entry
        merges core/prompts (95-tier) with api/prompts code — it must stay
        at 95, not fall to the shared floor of 80."""
        _map_roots(monkeypatch, tmp_path, core_tops=("prompts",), api_tops=("prompts",))
        assert _coverage_model.classify_package("prompts") == "shared"
        assert rule10_target("prompts") == 95

    def test_api_only_package_named_llm_derives_80(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The 95 tier requires the core tree — an api-only ``llm`` is api."""
        _map_roots(monkeypatch, tmp_path, api_tops=("llm",))
        assert rule10_target("llm") == 80

    def test_api_package_derives_80(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _map_roots(monkeypatch, tmp_path, api_tops=("billing",))
        assert rule10_target("billing") == 80
        assert rule10_target("billing.invoices") == 80

    def test_shared_package_derives_80(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _map_roots(monkeypatch, tmp_path, core_tops=("common",), api_tops=("common",))
        assert rule10_target("common") == 80

    def test_unknown_package_derives_80(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _map_roots(monkeypatch, tmp_path)
        assert rule10_target("ghost") == 80


class TestParseCoverageXmlUsesDerivation:
    """``parse_coverage_xml`` must not fall back to a flat 80 default."""

    def test_unmapped_core_package_gets_derived_target(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _map_roots(monkeypatch, tmp_path, core_tops=("widgets",))
        xml = _write_coverage_xml(tmp_path, {"widgets": 0.85})
        report = parse_coverage_xml(xml, baselines={})
        assert report.modules[0].target == 90

    def test_override_entry_wins_over_derivation(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _map_roots(monkeypatch, tmp_path, core_tops=("widgets",))
        monkeypatch.setattr(_coverage_model, "RULE10_OVERRIDES", {"widgets": 85})
        xml = _write_coverage_xml(tmp_path, {"widgets": 0.85})
        report = parse_coverage_xml(xml, baselines={})
        assert report.modules[0].target == 85


class TestOverrideTableHygiene:
    """The override table must stay minimal — genuine exceptions only."""

    def test_every_override_differs_from_derived_default(self) -> None:
        for name, target in _coverage_model.RULE10_OVERRIDES.items():
            assert target != rule10_target(name), (
                f"RULE10_OVERRIDES entry {name!r}: {target} equals the derived "
                "default — redundant overrides must be removed (derivation wins)."
            )


class TestKnownMisclassifiedPackages:
    """The packages that motivated the derivation fix (real repo roots)."""

    def test_llm_intents_gets_95(self) -> None:
        assert rule10_target("llm.intents") == 95

    def test_context_integration_contracts_gets_90(self) -> None:
        assert rule10_target("context.integration_contracts") == 90

    def test_agents_capabilities_gets_90(self) -> None:
        assert rule10_target("agents.capabilities") == 90
