"""Architecture tests for ADR-031 Core observability migration.

ADR-031 selects OpenTelemetry-only tracing for Narrare. Core keeps
Prometheus-compatible metrics via ``narrare_core.llm.metrics`` and must not
retain the former Langfuse LLM tracing adapter as a runtime dependency or
public LLM export.
"""

from __future__ import annotations

import ast
import tomllib
from importlib.util import find_spec
from pathlib import Path

import narrare_core.llm as llm

REPO_ROOT = Path(__file__).resolve().parents[4]
CORE_PACKAGE_ROOT = REPO_ROOT / "packages" / "core"
CORE_SOURCE_ROOT = CORE_PACKAGE_ROOT / "narrare_core"


class TestCoreObservabilityMigration:
    """Core no longer exposes or imports the Langfuse adapter."""

    def test_llm_package_does_not_export_llm_observability(self) -> None:
        """The public LLM runtime API does not expose the removed Langfuse adapter."""
        assert not hasattr(llm, "LLMObservability")
        assert "LLMObservability" not in llm.__all__

    def test_llm_observability_module_is_removed(self) -> None:
        """The former Langfuse adapter module is absent rather than dormant."""
        assert find_spec("narrare_core.llm.observability") is None

    def test_core_package_does_not_depend_on_langfuse(self) -> None:
        """The core package metadata has no Langfuse runtime dependency."""
        pyproject = tomllib.loads((CORE_PACKAGE_ROOT / "pyproject.toml").read_text())
        dependencies = pyproject["project"]["dependencies"]

        assert all(not dependency.lower().startswith("langfuse") for dependency in dependencies)

    def test_core_python_sources_do_not_import_langfuse(self) -> None:
        """No core Python source imports Langfuse after ADR-031 migration."""
        offending_imports: list[str] = []

        for source_path in sorted(CORE_SOURCE_ROOT.rglob("*.py")):
            tree = ast.parse(source_path.read_text(), filename=str(source_path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "langfuse" or alias.name.startswith("langfuse."):
                            offending_imports.append(f"{source_path}:{node.lineno}")
                elif isinstance(node, ast.ImportFrom):
                    module_name = node.module or ""
                    if module_name == "langfuse" or module_name.startswith("langfuse."):
                        offending_imports.append(f"{source_path}:{node.lineno}")

        assert offending_imports == []
