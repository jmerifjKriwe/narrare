"""The LLM boundary: a catalog of entries, picked by configuration.

Adding a provider is one entry here, plus one fetch strategy module when the
vendor speaks a new API shape (spec §4). The fake is a normal entry, not a test
branch: routing, prompt composition, streaming and persistence run the same code
whichever name is configured. ``NARRE_LLM_PROVIDER`` selects it and defaults to
``fake``, so a fresh clone runs without a key.

pydantic-ai is deliberately absent. One streaming completion over a fixed prompt
needs a single async method; an agent layer would add tools, retries and
structured output that nothing in v2 asks for. Revisit this module if tool use or
agent orchestration appears — not before.
"""

from collections.abc import Callable  # noqa: TC003
from os import environ

from app.kernel.llm.contract import PURPOSE_PREFIX, SOURCE_PREFIX, TextProvider
from app.kernel.llm.fake import FakeProvider
from app.kernel.llm.openai_compat import OpenAICompatibleProvider

PROVIDERS: dict[str, Callable[[], TextProvider]] = {
    "fake": FakeProvider,
    "openai-compatible": OpenAICompatibleProvider.from_environment,
}

__all__ = [
    "PROVIDERS",
    "PURPOSE_PREFIX",
    "SOURCE_PREFIX",
    "TextProvider",
    "get_provider",
    "provider_facts",
]


def get_provider() -> TextProvider:
    """FastAPI dependency: the configured provider."""
    name = environ.get("NARRE_LLM_PROVIDER", "fake")
    if name not in PROVIDERS:
        raise RuntimeError(f"unknown LLM provider {name!r}; known: {', '.join(sorted(PROVIDERS))}")
    return PROVIDERS[name]()


def provider_facts() -> tuple[str, str]:
    """The configured entry's ``(kind, model)``, for the audit's columns.

    Read from the same environment :func:`get_provider` reads — never parsed
    back out of ``describe()``, which is a log line, not a contract. The fake
    reports ``("fake", "fake")``; the real entry names the model it sends.
    """
    name = environ.get("NARRE_LLM_PROVIDER", "fake")
    if name not in PROVIDERS:
        raise RuntimeError(f"unknown LLM provider {name!r}; known: {', '.join(sorted(PROVIDERS))}")
    if name == "openai-compatible":
        return ("openai-compatible", environ.get("NARRE_LLM_MODEL", ""))
    return ("fake", "fake")
