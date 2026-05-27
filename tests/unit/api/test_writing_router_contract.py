"""Regression test: Writing routers must not hardcode provider/model names.

Writing deps (get_writing_service, get_extend_service, get_rewrite_service,
get_suggest_service) resolve model config through ModelRoutingResolver and
must not hardcode provider names like "anthropic" or model IDs.
"""

from __future__ import annotations

import inspect

_DI_FUNCTIONS = [
    "narrare.writing.deps.get_writing_service",
    "narrare.writing.deps.get_extend_service",
    "narrare.writing.deps.get_rewrite_service",
    "narrare.writing.deps.get_suggest_service",
]


def _get_source(func_path: str) -> str:
    import importlib

    module_path, func_name = func_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    func = getattr(module, func_name)
    return inspect.getsource(func)


class TestWritingRouterNoHardcodedProviders:
    """Writing DI functions must use config resolution, not hardcoded providers."""

    def test_writing_service_no_hardcoded_anthropic(self) -> None:
        source = _get_source("narrare.writing.deps.get_writing_service")
        assert '"anthropic"' not in source, "get_writing_service hardcodes 'anthropic'"

    def test_writing_service_no_hardcoded_openai(self) -> None:
        source = _get_source("narrare.writing.deps.get_writing_service")
        assert '"openai"' not in source, "get_writing_service hardcodes 'openai'"

    def test_writing_service_no_hardcoded_claude_model(self) -> None:
        source = _get_source("narrare.writing.deps.get_writing_service")
        assert '"claude' not in source, "get_writing_service hardcodes a claude model ID"

    def test_writing_service_no_hardcoded_gpt_model(self) -> None:
        source = _get_source("narrare.writing.deps.get_writing_service")
        assert '"gpt-' not in source, "get_writing_service hardcodes a GPT model ID"

    def test_extend_service_no_hardcoded_provider(self) -> None:
        source = _get_source("narrare.writing.deps.get_extend_service")
        assert '"anthropic"' not in source
        assert '"openai"' not in source

    def test_rewrite_service_no_hardcoded_provider(self) -> None:
        source = _get_source("narrare.writing.deps.get_rewrite_service")
        assert '"anthropic"' not in source
        assert '"openai"' not in source

    def test_suggest_service_no_hardcoded_provider(self) -> None:
        source = _get_source("narrare.writing.deps.get_suggest_service")
        assert '"anthropic"' not in source
        assert '"openai"' not in source
