"""Regression test: KB routers must not hardcode provider/model names.

If the KB dependency injection functions hardcode provider_name or model_id,
users configured with a different LLM provider may get internal server errors.
"""

from __future__ import annotations

import inspect

# Functions to inspect for hardcoded provider/model strings.
# These are the DI factories in narrare/kb/dependencies.py that wire up
# services with model configurations.
_DI_FUNCTIONS = [
    "narrare.kb.dependencies.get_kb_service",
    "narrare.kb.dependencies.get_extraction_service",
    "narrare.kb.dependencies.get_kb_session_service",
    "narrare.kb.dependencies.get_kb_improve_service",
    "narrare.kb.dependencies.get_worldbuilding_service",
    "narrare.kb.dependencies.get_graph_service",
    "narrare.kb.dependencies.get_consistency_service",
]


def _get_source(func_path: str) -> str:
    """Import a function by fully-qualified name and return its source."""
    import importlib

    module_path, func_name = func_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    func = getattr(module, func_name)
    return inspect.getsource(func)


class TestKBRouterNoHardcodedProviders:
    """KB DI functions must use config resolution, not hardcoded providers."""

    def test_kb_service_no_hardcoded_anthropic(self) -> None:
        source = _get_source("narrare.kb.dependencies.get_kb_service")
        assert '"anthropic"' not in source, (
            "get_kb_service hardcodes 'anthropic' — provider should come from config"
        )

    def test_kb_service_no_hardcoded_claude_model(self) -> None:
        source = _get_source("narrare.kb.dependencies.get_kb_service")
        assert '"claude' not in source, (
            "get_kb_service hardcodes a claude model — model should come from config"
        )

    def test_extraction_service_no_hardcoded_anthropic(self) -> None:
        source = _get_source("narrare.kb.dependencies.get_extraction_service")
        assert '"anthropic"' not in source, "get_extraction_service hardcodes 'anthropic'"

    def test_extraction_service_no_openai_hardcode(self) -> None:
        source = _get_source("narrare.kb.dependencies.get_extraction_service")
        assert '"openai"' not in source, "get_extraction_service hardcodes 'openai'"

    def test_session_service_no_hardcoded_provider(self) -> None:
        source = _get_source("narrare.kb.dependencies.get_kb_session_service")
        assert '"anthropic"' not in source, "get_kb_session_service hardcodes 'anthropic'"
        assert '"openai"' not in source, "get_kb_session_service hardcodes 'openai'"

    def test_improve_service_no_hardcoded_provider(self) -> None:
        source = _get_source("narrare.kb.dependencies.get_kb_improve_service")
        assert '"anthropic"' not in source, "get_kb_improve_service hardcodes 'anthropic'"
        assert '"openai"' not in source, "get_kb_improve_service hardcodes 'openai'"

    def test_consistency_service_no_hardcoded_provider(self) -> None:
        source = _get_source("narrare.kb.dependencies.get_consistency_service")
        assert '"anthropic"' not in source
        assert '"openai"' not in source
