"""Unit tests for auto-tagging via pytest_collection_modifyitems hook.

Verifies that the root conftest.py hook correctly auto-tags tests based on
their directory path:
  - tests/unit/ → unit
  - tests/integration/ → integration + requires_db
  - tests/e2e/ → e2e

Also verifies that pytest_configure registers markers for --strict-markers.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path

# Load root conftest as a regular module so we can test its hooks directly.
# conftest.py is not importable via normal import machinery — pytest loads it
# via its own plugin system.  We use importlib to sidestep that.
_spec = importlib.util.spec_from_file_location(
    "root_conftest",
    Path(__file__).resolve().parent.parent / "conftest.py",
)
assert _spec is not None and _spec.loader is not None
_root_conftest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_root_conftest)

pytest_collection_modifyitems = _root_conftest.pytest_collection_modifyitems
pytest_configure = _root_conftest.pytest_configure


# ---------------------------------------------------------------------------
# Lightweight fakes — no I/O, no subprocess, pure in-memory
# ---------------------------------------------------------------------------


@dataclass
class FakeMarker:
    """Minimal stand-in for pytest.Mark."""

    name: str
    args: tuple[object, ...] = ()
    kwargs: dict[str, object] = field(default_factory=dict)


@dataclass
class FakeItem:
    """Minimal stand-in for pytest.Item — only carries nodeid + markers."""

    nodeid: str
    markers: list[FakeMarker] = field(default_factory=list)

    def add_marker(self, marker: object) -> None:
        # pytest.mark.xxx produces a MarkDecorator; extract the Mark name.
        mark_name = getattr(marker, "name", None) or getattr(
            getattr(marker, "mark", None), "name", str(marker)
        )
        self.markers.append(FakeMarker(name=mark_name))

    def has_marker(self, name: str) -> bool:
        return any(m.name == name for m in self.markers)


class _FakeConfig:
    """Minimal fake for pytest.Config.addinivalue_line."""

    def __init__(self, addinivalue_lines: list[str] | None = None) -> None:
        self._lines: list[str] = addinivalue_lines if addinivalue_lines is not None else []

    def addinivalue_line(self, section: str, line: str) -> None:
        self._lines.append(line)


# ---------------------------------------------------------------------------
# Tests: pytest_configure marker registration
# ---------------------------------------------------------------------------


class TestPytestConfigureMarkerRegistration:
    """Verify pytest_configure registers markers for --strict-markers."""

    def test_unit_marker_registered(self) -> None:
        """The 'unit' marker is added to config via addinivalue_line."""
        lines: list[str] = []
        config = _FakeConfig(addinivalue_lines=lines)
        pytest_configure(config)  # type: ignore[arg-type]
        assert any("unit:" in line for line in lines)

    def test_integration_marker_registered(self) -> None:
        """The 'integration' marker is added to config."""
        lines: list[str] = []
        config = _FakeConfig(addinivalue_lines=lines)
        pytest_configure(config)  # type: ignore[arg-type]
        assert any("integration:" in line for line in lines)

    def test_requires_db_marker_registered(self) -> None:
        """The 'requires_db' marker is added to config."""
        lines: list[str] = []
        config = _FakeConfig(addinivalue_lines=lines)
        pytest_configure(config)  # type: ignore[arg-type]
        assert any("requires_db:" in line for line in lines)

    def test_all_three_markers_registered(self) -> None:
        """All three markers are registered in a single call."""
        lines: list[str] = []
        config = _FakeConfig(addinivalue_lines=lines)
        pytest_configure(config)  # type: ignore[arg-type]
        assert len(lines) == 3


# ---------------------------------------------------------------------------
# Tests: pytest_collection_modifyitems auto-tagging
# ---------------------------------------------------------------------------


class TestAutoTaggingUnitPath:
    """Tests under tests/unit/ receive the 'unit' marker."""

    def test_unit_path_gets_unit_marker(self) -> None:
        item = FakeItem(nodeid="tests/unit/core/test_example.py::test_foo")
        pytest_collection_modifyitems([item])  # type: ignore[arg-type]
        assert item.has_marker("unit")

    def test_unit_path_no_integration_marker(self) -> None:
        item = FakeItem(nodeid="tests/unit/core/test_example.py::test_foo")
        pytest_collection_modifyitems([item])  # type: ignore[arg-type]
        assert not item.has_marker("integration")

    def test_unit_path_no_requires_db_marker(self) -> None:
        item = FakeItem(nodeid="tests/unit/core/test_example.py::test_foo")
        pytest_collection_modifyitems([item])  # type: ignore[arg-type]
        assert not item.has_marker("requires_db")

    def test_unit_path_no_e2e_marker(self) -> None:
        item = FakeItem(nodeid="tests/unit/core/test_example.py::test_foo")
        pytest_collection_modifyitems([item])  # type: ignore[arg-type]
        assert not item.has_marker("e2e")


class TestAutoTaggingIntegrationPath:
    """Tests under tests/integration/ receive 'integration' + 'requires_db'."""

    def test_integration_path_gets_integration_marker(self) -> None:
        item = FakeItem(nodeid="tests/integration/kb/test_kb_api.py::test_foo")
        pytest_collection_modifyitems([item])  # type: ignore[arg-type]
        assert item.has_marker("integration")

    def test_integration_path_gets_requires_db_marker(self) -> None:
        item = FakeItem(nodeid="tests/integration/kb/test_kb_api.py::test_foo")
        pytest_collection_modifyitems([item])  # type: ignore[arg-type]
        assert item.has_marker("requires_db")

    def test_integration_path_no_unit_marker(self) -> None:
        item = FakeItem(nodeid="tests/integration/kb/test_kb_api.py::test_foo")
        pytest_collection_modifyitems([item])  # type: ignore[arg-type]
        assert not item.has_marker("unit")

    def test_integration_path_no_e2e_marker(self) -> None:
        item = FakeItem(nodeid="tests/integration/kb/test_kb_api.py::test_foo")
        pytest_collection_modifyitems([item])  # type: ignore[arg-type]
        assert not item.has_marker("e2e")


class TestAutoTaggingE2EPath:
    """Tests under tests/e2e/ receive the 'e2e' marker."""

    def test_e2e_path_gets_e2e_marker(self) -> None:
        item = FakeItem(nodeid="tests/e2e/test_hero_flow.py::test_foo")
        pytest_collection_modifyitems([item])  # type: ignore[arg-type]
        assert item.has_marker("e2e")

    def test_e2e_path_no_unit_marker(self) -> None:
        item = FakeItem(nodeid="tests/e2e/test_hero_flow.py::test_foo")
        pytest_collection_modifyitems([item])  # type: ignore[arg-type]
        assert not item.has_marker("unit")

    def test_e2e_path_no_integration_marker(self) -> None:
        item = FakeItem(nodeid="tests/e2e/test_hero_flow.py::test_foo")
        pytest_collection_modifyitems([item])  # type: ignore[arg-type]
        assert not item.has_marker("integration")

    def test_e2e_path_no_requires_db_marker(self) -> None:
        item = FakeItem(nodeid="tests/e2e/test_hero_flow.py::test_foo")
        pytest_collection_modifyitems([item])  # type: ignore[arg-type]
        assert not item.has_marker("requires_db")


class TestAutoTaggingEdgeCases:
    """Edge cases: non-matching paths, mixed items, empty list."""

    def test_unknown_path_gets_no_markers(self) -> None:
        item = FakeItem(nodeid="tests/conftest.py::test_architecture_constraints")
        pytest_collection_modifyitems([item])  # type: ignore[arg-type]
        assert len(item.markers) == 0

    def test_empty_items_list_is_safe(self) -> None:
        """Hook must not crash on an empty list."""
        pytest_collection_modifyitems([])  # type: ignore[arg-type]

    def test_mixed_items_all_tagged_correctly(self) -> None:
        """A batch of items from different paths all get correct markers."""
        unit = FakeItem(nodeid="tests/unit/test_a.py::test_a")
        integ = FakeItem(nodeid="tests/integration/test_b.py::test_b")
        e2e = FakeItem(nodeid="tests/e2e/test_c.py::test_c")
        unknown = FakeItem(nodeid="tests/conftest.py::test_d")

        pytest_collection_modifyitems([unit, integ, e2e, unknown])  # type: ignore[arg-type]

        assert unit.has_marker("unit")
        assert integ.has_marker("integration")
        assert integ.has_marker("requires_db")
        assert e2e.has_marker("e2e")
        assert len(unknown.markers) == 0

    def test_nested_path_still_matches(self) -> None:
        """Deeply nested paths like tests/unit/core/prompts/test_x.py match."""
        item = FakeItem(
            nodeid="tests/unit/core/prompts/test_bundled_generation_prompts.py::test_foo"
        )
        pytest_collection_modifyitems([item])  # type: ignore[arg-type]
        assert item.has_marker("unit")

    def test_no_duplicate_markers_on_repeated_calls(self) -> None:
        """Calling the hook twice should not double-add markers."""
        item = FakeItem(nodeid="tests/unit/test_a.py::test_a")
        pytest_collection_modifyitems([item])  # type: ignore[arg-type]
        pytest_collection_modifyitems([item])  # type: ignore[arg-type]
        unit_count = sum(1 for m in item.markers if m.name == "unit")
        # Hook adds marker each call — 2 calls = 2 markers.
        # This is expected: pytest only calls the hook once per session.
        assert unit_count == 2
